"""
`GeradorCidade` — dono da EMISSÃO (Q02, docs/PLANO_CIDADE_VIVA.md: pacote separado por
assunto, era `generate_city_geometry.py`, 638 linhas, acima do limite de 400 do
ARQUITETURA.md). Pega a `Malha` que `modelo.construir_malha()` devolve e faz todo o
trabalho compartilhado (ESPEC_DESENHO_CIDADE.md Seção 5.5): inset de quadra, subdivisão
em lotes, footprint, distribuição dirigida (F2/F3, em `distribuicao.py`), muralha,
emissão de feature, índice. Nenhum modelo reimplementa nada disto.
"""
import math

from cartographer.cities.escala import zoom_min_por_camada
from config import cfg_get

from . import quad
from .distribuicao import DistribuicaoMixin


class GeradorCidade(DistribuicaoMixin):
    """Dono da EMISSÃO — ver docstring do módulo. `DistribuicaoMixin` (distribuicao.py)
    contrai F2/F3; esta classe cuida de transformar coordenadas, emitir a malha crua,
    fazer o inset de quadra + lotes, e montar a muralha/índice."""

    def __init__(self, modelo):
        self.modelo = modelo
        self.rng = modelo.rng
        sitio = modelo.sitio
        self.sitio = sitio
        self.nome = sitio.nome
        self.tamanho = sitio.tamanho
        self.tipo = sitio.tipo
        self.continente_nome = sitio.continente
        self.cx_mundo = sitio.x_mundo
        self.cy_mundo = sitio.y_mundo
        self.seed = sitio.seed
        self.cfg = modelo.cfg
        self.metros_por_px = sitio.metros_por_px
        # Todo modelo expõe seu próprio "quão grande é a cidade" — pro zoom_min e pra
        # área-alvo de lote (via `modelo.lote_fator_cidade`, lido em `_area_alvo_lote`).
        self.raio_m = modelo.raio_m

        self.lote_area_base = cfg_get(self.cfg, "cidade_geo_lote_area_base_m2")
        self.lote_fator_por_banda = cfg_get(self.cfg, "cidade_geo_lote_fator_por_banda")
        self.lote_profundidade_max = cfg_get(self.cfg, "cidade_geo_lote_profundidade_max")
        self.quadra_area_minima = cfg_get(self.cfg, "cidade_geo_quadra_area_minima_m2")
        self.recuo_rua = cfg_get(self.cfg, "cidade_geo_recuo_rua_m")
        self.via_largura_por_classe = cfg_get(self.cfg, "cidade_via_largura_m_por_classe")
        self.edificacao_recuo = cfg_get(self.cfg, "cidade_geo_edificacao_recuo_m")
        self.edificacao_taxa_ocupacao = cfg_get(self.cfg, "cidade_geo_edificacao_taxa_ocupacao")
        self.edificacao_jitter = cfg_get(self.cfg, "cidade_geo_edificacao_jitter")
        self.edificacao_taxa_ocupacao_min = cfg_get(self.cfg, "cidade_geo_edificacao_taxa_ocupacao_min")
        self.edificacao_taxa_ocupacao_max = cfg_get(self.cfg, "cidade_geo_edificacao_taxa_ocupacao_max")
        self._declividade_max = cfg_get(self.cfg, "cidade_geo_declividade_max")

        self.zoom_min_camada = zoom_min_por_camada(self.cfg, self.raio_m)

        self.features = []

    # ------------------------------------------------------------------
    # Transform local(m) -> mundo(px) — Seção 2.1/2.3 do plano
    # ------------------------------------------------------------------
    def _mundo(self, x_m, y_m):
        return (self.cx_mundo + x_m / self.metros_por_px,
                self.cy_mundo + y_m / self.metros_por_px)

    def _geojson_coord(self, x_m, y_m):
        """[lng, lat] = [x_mundo, -y_mundo] — mesma conversão de pixelParaLatLng (Seção 2.3),
        o Leaflet plota direto sem transformar nada no frontend."""
        x_mundo, y_mundo = self._mundo(x_m, y_m)
        return [round(x_mundo, 6), round(-y_mundo, 6)]

    def _add_feature(self, geom_type, coords_m, camada, props=None):
        if geom_type == "Point":
            coords = self._geojson_coord(*coords_m)
        else:
            coords = [self._geojson_coord(*p) for p in coords_m]
            if geom_type == "Polygon":
                coords = [coords]
        p = {"camada": camada, "zoom_min": self.zoom_min_camada.get(camada, 8)}
        if props:
            p.update(props)
        self.features.append({"type": "Feature", "geometry": {"type": geom_type, "coordinates": coords}, "properties": p})

    @staticmethod
    def _polar(raio, angulo):
        return (raio * math.cos(angulo), raio * math.sin(angulo))

    @staticmethod
    def _quarteirao_id_str(quadra_id):
        """`(banda, setor)` vira `"banda_setor"` — formato estável já usado antes do F4
        (F2.1); outros modelos podem devolver um `id` que já é string/int."""
        if isinstance(quadra_id, tuple):
            return "_".join(str(p) for p in quadra_id)
        return str(quadra_id)

    # ------------------------------------------------------------------
    # Emissão da malha que o modelo devolveu — F4.5.
    # ------------------------------------------------------------------
    def _emitir_ruas(self, malha):
        for rua in malha.ruas:
            self._add_feature("LineString", rua.pontos, "rua",
                              {"tipo_via": rua.tipo_via, "classe_via": rua.classe_via, "indice": rua.indice})

    def _emitir_portoes(self, malha):
        for x, y, nome in malha.portoes:
            self._add_feature("Point", (x, y), "portao", {"nome": nome})

    def _emitir_praca(self, malha):
        cx, cy = malha.centro_praca
        circulo = []
        for k in range(16):
            dx, dy = self._polar(malha.raio_praca, 2 * math.pi * k / 16)
            circulo.append((cx + dx, cy + dy))
        self._add_feature("Polygon", circulo + [circulo[0]], "praca", {"nome": f"Praça Central de {self.nome}"})

    # ------------------------------------------------------------------
    # Inset de quadra + subdivisão em lotes — geometria pura (quad.py), compartilhada
    # por QUALQUER modelo (Seção 5.5). "O que NÃO é gancho" da Seção 4.3.
    # ------------------------------------------------------------------
    def _distancia_faixa_dominio(self, classe):
        largura = self.via_largura_por_classe.get(classe, self.via_largura_por_classe.get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    def _gerar_quarteiroes_e_lotes(self, malha):
        """Pega os quads CRUS que o modelo devolveu (`malha.quadras`) e faz o inset pela
        faixa de domínio (E1) + subdivisão em lotes (E2) — idêntico pra qualquer modelo."""
        self._lotes = []  # lista de (lote_poligono, Quadra)
        for quadra in malha.quadras:
            distancias = [self._distancia_faixa_dominio(c) for c in quadra.classes_aresta]
            quad_urbanizavel = quad.encolher_quad(quadra.vertices, distancias)
            if quad_urbanizavel is None or quad.area_quad(quad_urbanizavel) < self.quadra_area_minima:
                continue  # quadra degenerada, ou pequena demais pra urbanizar

            quarteirao_id_str = self._quarteirao_id_str(quadra.id)
            self._add_feature("Polygon", quad_urbanizavel + [quad_urbanizavel[0]], "quarteirao",
                              {"bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str})

            area_alvo = self._area_alvo_lote(quadra.banda)
            for lote in quad.subdividir_lote_recursivo(quad_urbanizavel, area_alvo, self.lote_profundidade_max):
                if not quad.e_quad_simples(lote):
                    continue  # G02: quarteirão côncavo pode gerar um corte que auto-intersecta
                self._add_feature("Polygon", lote + [lote[0]], "lote",
                                  {"bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str})
                self._lotes.append((lote, quadra))

    # ------------------------------------------------------------------
    def _gerar_muralha(self, malha):
        if not self.modelo.precisa_muralha():
            return
        self._add_feature("LineString", malha.contorno + [malha.contorno[0]], "muralha",
                          {"nome": f"Muralha de {self.nome}"})
        for k, ponto in enumerate(malha.torres):
            self._add_feature("Point", ponto, "torre", {"nome": f"Torre {k + 1}"})

    # ------------------------------------------------------------------
    def gerar(self):
        malha = self.modelo.construir_malha()
        self.modelo.malha = malha  # zona_de (gancho 2) precisa de num_bandas
        self._emitir_ruas(malha)
        self._emitir_portoes(malha)
        self._emitir_praca(malha)
        self._gerar_quarteiroes_e_lotes(malha)
        self._distribuir_edificios(malha)
        self._gerar_muralha(malha)
        return {"type": "FeatureCollection", "features": self.features, "properties": {
            "cidade": self.nome, "continente": self.continente_nome, "tamanho": self.tamanho,
            "tipo": self.tipo, "seed": self.seed, "raio_m": self.raio_m,
            "x_global": self.cx_mundo, "y_global": self.cy_mundo,
            # F8.3: grava o modelo e o essencial do sítio — barato, e é o que permite
            # responder "por que esta cidade ficou assim?" sem reinstanciar o gerador.
            "modelo": self.modelo.nome,
            "bioma_dominante": self.sitio.bioma_dominante,
            "temperatura_media": round(self.sitio.temperatura_media, 4),
            "umidade_media": round(self.sitio.umidade_media, 4),
        }}

    def indice(self, slug):
        """E5 (Seção 5.5/6): bbox da cidade em px de MUNDO + contagem/zoom_min por camada,
        pro `web/rotas/features.py` descartar a cidade inteira sem abrir o arquivo quando
        ela não intersecta o bbox pedido, ou quando nenhuma camada visível já acendeu
        naquele zoom."""
        xs, ys = [], []
        camadas = {}
        for feat in self.features:
            props = feat["properties"]
            camada = props["camada"]
            info = camadas.setdefault(camada, {"n": 0, "zoom_min": props.get("zoom_min", 0)})
            info["n"] += 1
            coords = feat["geometry"]["coordinates"]
            for lng, lat in self._achatar_coords(coords):
                xs.append(lng)
                ys.append(-lat)
        bbox = {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)} if xs else None
        return {
            "slug": slug, "nome": self.nome, "tamanho": self.tamanho, "modelo": self.modelo.nome,
            "raio_m": self.raio_m, "bbox": bbox, "camadas": camadas,
        }

    @staticmethod
    def _achatar_coords(coords):
        """Percorre coordinates de qualquer geometry (Point/LineString/Polygon) até o par
        [lng,lat] mais interno — mesma lógica de `achatar` em web/cache_mapa.py."""
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            yield coords
        else:
            for c in coords:
                yield from GeradorCidade._achatar_coords(c)
