"""
SCRIPT: generate_city_geometry.py
FUNÇÃO: Gera a geometria vetorial real de uma cidade (Fase 4, P2.2) — ruas, quarteirões,
        lotes, edifícios nomeados e muralha — em `database/cidades/<slug>.geojson`.

CONCEITO CENTRAL (Seção 2.1 do plano): a cidade é SUB-PIXEL na escala do mundo (1 px de
mundo = 15,81 km — escala_pixel_area_km2 é ÁREA, o lado do pixel é sqrt(250) = 15,81 km;
ver D1 do docs/DIAGNOSTICO_V3.md). A geometria é gerada num sistema de coordenadas LOCAL
próprio (origem no centro da cidade, unidade = metro), determinístico a partir do nome da
cidade (`zlib.crc32`, nunca `hash()`), e só convertida pra pixel de mundo no fim:

    desloc_px = desloc_m / (sqrt(escala_pixel_area_km2) * 1000)

ARQUITETURA (docs/ESPEC_DESENHO_CIDADE.md F4, 2026-09-11): a MALHA (ruas, quadras, praça,
portões, contorno) é responsabilidade do MODELO de cidade escolhido para cada cidade
(`cartographer/cities/modelos/` — `radial.py` é o traçado de hoje, movido pra lá). Este
arquivo continua sendo o ponto de entrada e o dono da EMISSÃO: converte a `Malha` que o
modelo devolve em GeoJSON (inset de quadra, subdivisão em lotes, footprint de edifício,
distribuição dirigida de notáveis e comércio de bairro, muralha, índice) — trabalho
idêntico pra qualquer modelo, nunca copiado num modelo específico (Seção 5.5).
"""
import os
import sys
import json
import math
import random
import collections
from dataclasses import dataclass, field
from datetime import datetime

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

import numpy as np
from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.escala import zoom_min_por_camada
from cartographer.cities.modelos import SitioCidade, MODELOS, escolher_modelo
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"
OUTPUT_DIR = "database/cidades"


@dataclass
class _AlocacaoDeLotes:
    """Índices auxiliares da distribuição de edifícios (F2/F3, R-D05 do
    PLANO_REFATORACAO.md): que lote pertence a que quarteirão, que quarteirão pertence a
    que zona, e que lote já foi tomado. Existe pra `_distribuir_edificios` parar de ser
    um método de ~110 linhas com uma closure (`tem_vaga`) referenciando uma variável
    (`ocupados`) definida depois dela."""
    lotes_por_quarteirao: dict
    quarteiroes_por_zona: dict
    ocupados: dict = field(default_factory=dict)

    def tem_vaga(self, quadra) -> bool:
        return any(p not in self.ocupados for p in self.lotes_por_quarteirao[quadra.id])


class GeradorCidade:
    """Dono da EMISSÃO — pega a `Malha` que `modelo.construir_malha()` devolve e faz todo
    o trabalho compartilhado (Seção 5.5): inset de quadra, subdivisão em lotes, footprint,
    distribuição dirigida (F2/F3), muralha, emissão de feature, índice. Nenhum modelo
    reimplementa nada disto."""

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

        # D2/Caminho B: terreno já amostrado uma vez por `SitioCidade.medir()` — nenhum
        # modelo nem o gerador chamam `obter_cartografo()` diretamente.
        self.terreno = sitio.terreno
        self._grad_x = sitio.grad_x
        self._grad_y = sitio.grad_y

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

    # ------------------------------------------------------------------
    # D2/Caminho B (DIAGNOSTICO_V3 Seção 13.5 Passo 5): leitura do terreno local, sobre
    # a grade 64x64 amostrada por `SitioCidade.medir()`. Coordenadas de entrada são metros
    # locais (mesma origem no centro da cidade usada pelo resto da geometria).
    # ------------------------------------------------------------------
    def _indice_terreno(self, x_m, y_m):
        n = self.terreno.shape[0]
        lado_m = 2.0 * self.raio_m
        fx = (x_m + self.raio_m) / lado_m
        fy = (y_m + self.raio_m) / lado_m
        ix = int(np.clip(fx * n, 0, n - 1))
        iy = int(np.clip(fy * n, 0, n - 1))
        return iy, ix

    def _altitude_local(self, x_m, y_m):
        if self.terreno is None:
            return None
        iy, ix = self._indice_terreno(x_m, y_m)
        return float(self.terreno[iy, ix])

    def _declividade_local(self, x_m, y_m):
        """Magnitude do gradiente de altitude no ponto, em unidade de altitude por metro
        — usado pra rejeitar lote íngreme demais (edifício)."""
        if self.terreno is None:
            return 0.0
        iy, ix = self._indice_terreno(x_m, y_m)
        m_por_celula = (2.0 * self.raio_m) / self.terreno.shape[0]
        return float(math.hypot(self._grad_x[iy, ix], self._grad_y[iy, ix]) / m_por_celula)

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
    # Inset de quadra + subdivisão em lotes — geometria pura, compartilhada por
    # QUALQUER modelo (Seção 5.5). "O que NÃO é gancho" da Seção 4.3.
    # ------------------------------------------------------------------
    @staticmethod
    def _area_sinalizada(quad):
        """Shoelace COM sinal — positivo/negativo conforme a orientação (horário vs.
        anti-horário). `_area_quad` é o valor absoluto disto; usada pra detectar quad
        invertido depois do inset (`_encolher_quad`)."""
        area = 0.0
        n = len(quad)
        for i in range(n):
            x1, y1 = quad[i]
            x2, y2 = quad[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return area / 2.0

    @classmethod
    def _area_quad(cls, quad):
        """Fórmula do shoelace — área de um polígono simples (aqui sempre convexo o
        bastante pra não importar orientação)."""
        return abs(cls._area_sinalizada(quad))

    @staticmethod
    def _segmentos_cruzam(a, b, c, d):
        """Interseção própria de dois segmentos, por teste de orientação. Colinearidade
        conta como não-cruzamento: o caso degenerado já é pego pelo piso de área."""
        def orientacao(p, q, r):
            v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
        o1, o2 = orientacao(a, b, c), orientacao(a, b, d)
        o3, o4 = orientacao(c, d, a), orientacao(c, d, b)
        return o1 != o2 and o3 != o4

    @classmethod
    def _e_quad_simples(cls, quad):
        """Um quadrilátero é simples se os dois pares de arestas OPOSTAS não se cruzam
        (0-2 e 1-3). Arestas adjacentes sempre se tocam no vértice — não são cruzamento."""
        return not (cls._segmentos_cruzam(quad[0], quad[1], quad[2], quad[3])
                    or cls._segmentos_cruzam(quad[1], quad[2], quad[3], quad[0]))

    @staticmethod
    def _interseccao_retas(p1, d1, p2, d2):
        """Interseção de duas retas em forma ponto + t*direção (sistema 2x2). `None` se
        as retas forem paralelas (determinante ~0) — cabe ao chamador decidir o fallback."""
        x1, y1 = p1
        dx1, dy1 = d1
        x2, y2 = p2
        dx2, dy2 = d2
        denom = dx1 * dy2 - dy1 * dx2
        if abs(denom) < 1e-9:
            return None
        t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom
        return (x1 + dx1 * t, y1 + dy1 * t)

    def _encolher_quad(self, quad, distancias):
        """Desloca cada aresta do quad para DENTRO por distancias[k] e reintercepta.
        `quad` tem 4 vértices em sentido consistente; `distancias[k]` é o recuo da aresta
        k (de quad[k] para quad[k+1]), em metros. Retorna o quad encolhido, ou None se ele
        degenerar (quadra estreita demais pra caber a rua, ou polígono invertido)."""
        if len(quad) != 4 or not self._e_quad_simples(quad):
            return None  # G02: quad de entrada já inválido (bug de modelo) morre aqui
        n = len(quad)
        cx = sum(p[0] for p in quad) / n
        cy = sum(p[1] for p in quad) / n
        orientacao_original = self._area_sinalizada(quad)

        arestas = []  # (ponto_deslocado, direcao_normalizada) por aresta k
        for k in range(n):
            p0, p1 = quad[k], quad[(k + 1) % n]
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            comprimento = math.hypot(dx, dy)
            if comprimento < 1e-9:
                return None
            dx, dy = dx / comprimento, dy / comprimento
            # Normal a 90° da aresta — testada contra o centroide, nunca presumida.
            nx, ny = -dy, dx
            mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
            if (cx - mx) * nx + (cy - my) * ny < 0:
                nx, ny = -nx, -ny
            dist = distancias[k]
            arestas.append(((p0[0] + nx * dist, p0[1] + ny * dist), (dx, dy)))

        novo = []
        for k in range(n):
            p_prev, d_prev = arestas[(k - 1) % n]
            p_cur, d_cur = arestas[k]
            pt = self._interseccao_retas(p_prev, d_prev, p_cur, d_cur)
            if pt is None:
                pt = ((p_prev[0] + p_cur[0]) / 2.0, (p_prev[1] + p_cur[1]) / 2.0)
            novo.append(pt)

        # Degeneração geométrica: um inset que "virou do avesso" (recuo maior que o quad
        # aguenta) produz um quad com orientação oposta à original, ou área ~0 — descarta
        # em vez de emitir polígono invertido. `_encolher_quad` é geometria pura: o piso
        # de área específico de cada uso fica por conta do chamador.
        if self._area_quad(novo) < 1e-6:
            return None
        if self._area_sinalizada(novo) * orientacao_original <= 0:
            return None
        if not self._e_quad_simples(novo):
            return None  # G02: vértice muito obtuso pode manter a área/orientação e
            # ainda assim virar gravata-borboleta depois do recuo (Seção 1.1/G02).
        return novo

    def _distancia_faixa_dominio(self, classe):
        largura = self.via_largura_por_classe.get(classe, self.via_largura_por_classe.get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    def _area_alvo_lote(self, banda):
        """E2 (Seção 5.2): alvo de área do lote cresce com a banda (centro denso, borda
        folgada) e leva o fator por cidade que o MODELO sorteou (`lote_fator_cidade`),
        pra duas cidades do mesmo tamanho não serem idênticas."""
        return self.lote_area_base * (self.lote_fator_por_banda ** (banda - 1)) * self.modelo.lote_fator_cidade

    def _subdividir_lote(self, quad, area_alvo, profundidade=0):
        """Corta o quadrilátero ao meio pelo lado mais longo, recursivamente, até a área
        ficar perto do alvo (a malha só produz quads, nunca formas mais complexas)."""
        area = self._area_quad(quad)
        if area <= area_alvo * 1.6 or profundidade >= self.lote_profundidade_max:
            return [quad]

        # Acha o lado mais longo e corta pelo meio dele e do seu oposto. Fórmula em
        # índice modular relativo a `i0` (não por posição ordenada — um `sorted([i0,i1])`
        # aqui quebra a correspondência entre m0/m1 e os vértices quando `i0` não é 0 ou
        # 1, produzindo um quad "em zigue-zague").
        n = len(quad)  # sempre 4
        comprimentos = [math.dist(quad[i], quad[(i + 1) % n]) for i in range(n)]
        i0 = comprimentos.index(max(comprimentos))

        def meio(a, b):
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

        m0 = meio(quad[i0], quad[(i0 + 1) % n])
        m1 = meio(quad[(i0 + 2) % n], quad[(i0 + 3) % n])

        parte1 = [m0, quad[(i0 + 1) % n], quad[(i0 + 2) % n], m1]
        parte2 = [m1, quad[(i0 + 3) % n], quad[i0 % n], m0]

        return (self._subdividir_lote(parte1, area_alvo, profundidade + 1) +
                self._subdividir_lote(parte2, area_alvo, profundidade + 1))

    def _gerar_quarteiroes_e_lotes(self, malha):
        """Pega os quads CRUS que o modelo devolveu (`malha.quadras`) e faz o inset pela
        faixa de domínio (E1) + subdivisão em lotes (E2) — idêntico pra qualquer modelo."""
        self._lotes = []  # lista de (lote_poligono, Quadra)
        for quadra in malha.quadras:
            distancias = [self._distancia_faixa_dominio(c) for c in quadra.classes_aresta]
            quad_urbanizavel = self._encolher_quad(quadra.vertices, distancias)
            if quad_urbanizavel is None or self._area_quad(quad_urbanizavel) < self.quadra_area_minima:
                continue  # quadra degenerada, ou pequena demais pra urbanizar

            quarteirao_id_str = self._quarteirao_id_str(quadra.id)
            self._add_feature("Polygon", quad_urbanizavel + [quad_urbanizavel[0]], "quarteirao",
                              {"bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str})

            area_alvo = self._area_alvo_lote(quadra.banda)
            for lote in self._subdividir_lote(quad_urbanizavel, area_alvo):
                if not self._e_quad_simples(lote):
                    continue  # G02: quarteirão côncavo pode gerar um corte que auto-intersecta
                self._add_feature("Polygon", lote + [lote[0]], "lote",
                                  {"bairro": quadra.bairro, "banda": quadra.banda, "quarteirao_id": quarteirao_id_str})
                self._lotes.append((lote, quadra))

    # ------------------------------------------------------------------
    # F2/F3 — distribuição dirigida de marcos + comércio de bairro.
    # ------------------------------------------------------------------
    _ZONAS_ORDEM = ["nucleo", "centro", "meio", "borda"]

    def _zona_de_fallback(self, zona, zonas_disponiveis):
        """F2.2: se a zona pedida não existir nesta cidade (cidade pequena com poucos
        anéis), cai pra zona válida mais próxima em vez de descartar a encomenda."""
        if zona in zonas_disponiveis:
            return zona
        if zona not in self._ZONAS_ORDEM:
            return next(iter(zonas_disponiveis), None)
        idx = self._ZONAS_ORDEM.index(zona)
        for delta in range(1, len(self._ZONAS_ORDEM)):
            for cand_idx in (idx - delta, idx + delta):
                if 0 <= cand_idx < len(self._ZONAS_ORDEM):
                    cand = self._ZONAS_ORDEM[cand_idx]
                    if cand in zonas_disponiveis:
                        return cand
        return None

    def _footprint_edificio(self, lote):
        """E3 (Seção 5.3): footprint poligonal dentro do lote — recuo da divisa (mesmo
        inset da E1) e depois um segundo encolhimento em torno do centroide pela RAIZ da
        taxa de ocupação (a área escala com o quadrado do fator linear). `jitter` varia a
        taxa por construção pra a quadra não virar um tabuleiro perfeito."""
        recuado = self._encolher_quad(lote, [self.edificacao_recuo] * 4)
        if recuado is None:
            return None
        jitter = self.rng.uniform(-self.edificacao_jitter, self.edificacao_jitter)
        taxa_efetiva = min(self.edificacao_taxa_ocupacao_max, max(self.edificacao_taxa_ocupacao_min, self.edificacao_taxa_ocupacao + jitter))
        fator_linear = math.sqrt(taxa_efetiva)
        cx = sum(p[0] for p in recuado) / len(recuado)
        cy = sum(p[1] for p in recuado) / len(recuado)
        return [(cx + (x - cx) * fator_linear, cy + (y - cy) * fator_linear) for x, y in recuado]

    def _distribuir_edificios(self, malha):
        """Distribuição dirigida (F2, Seção 5.2): decide primeiro QUANTOS de cada tipo a
        cidade tem e EM QUE QUADRA cada um vai (via `modelo.zona_de`/`encomendas`/
        `escolher_quadra` — não por ordem de lista, causa raiz do bug 3.2); depois roda o
        comércio de bairro (F3, densidade, teto próprio); só então preenche o resto com
        Residência. Um edifício por lote — Polygon (footprint dentro do lote).

        Quebrado em 4 fases (R-D05 do PLANO_REFATORACAO.md) — cada uma um método
        privado, com o estado compartilhado (`_AlocacaoDeLotes`) passado explicitamente,
        não uma closure fechando sobre uma variável definida mais abaixo no corpo."""
        alocacao = self._indexar_lotes()
        self._alocar_marcos(alocacao)
        self._alocar_comercio_de_bairro(alocacao)
        self._emitir_edificios(alocacao)

    def _indexar_lotes(self) -> _AlocacaoDeLotes:
        quarteiroes_por_zona = collections.defaultdict(list)
        lotes_por_quarteirao = collections.defaultdict(list)
        zona_ja_vista = {}
        for pos, (lote, quadra) in enumerate(self._lotes):
            if quadra.id not in zona_ja_vista:
                zona_ja_vista[quadra.id] = self.modelo.zona_de(quadra)
                quarteiroes_por_zona[zona_ja_vista[quadra.id]].append(quadra)
            lotes_por_quarteirao[quadra.id].append(pos)
        for lista in quarteiroes_por_zona.values():
            self.rng.shuffle(lista)
        return _AlocacaoDeLotes(lotes_por_quarteirao=lotes_por_quarteirao,
                                 quarteiroes_por_zona=quarteiroes_por_zona)

    def _alocar_marcos(self, alocacao: _AlocacaoDeLotes) -> None:
        """F2: encomendas do catálogo de marcos, por zona + rodízio."""
        notaveis_max = cfg_get(self.cfg, "cidade_geo_notaveis_max_por_quarteirao")
        encomendas = self.modelo.encomendas()
        zonas_disponiveis = {z for z, qs in alocacao.quarteiroes_por_zona.items() if qs}
        rodizio_marco = collections.Counter()
        notaveis_em_marco = collections.Counter()
        descartadas = 0

        for entrada, zona in encomendas:
            zona_resolvida = self._zona_de_fallback(zona, zonas_disponiveis) if zonas_disponiveis else None
            if zona_resolvida is None:
                descartadas += 1
                continue
            candidatas = alocacao.quarteiroes_por_zona[zona_resolvida]
            quadra = self.modelo.escolher_quadra(zona_resolvida, candidatas, notaveis_max,
                                                  alocacao.tem_vaga, rodizio_marco, notaveis_em_marco)
            if quadra is None:
                descartadas += 1
                continue
            livres = [p for p in alocacao.lotes_por_quarteirao[quadra.id] if p not in alocacao.ocupados]
            alocacao.ocupados[self.rng.choice(livres)] = entrada

        if descartadas:
            print(f"  ⚠️  {self.nome}: {descartadas} encomenda(s) de marco descartada(s) "
                  f"por falta de lugar")

    def _alocar_comercio_de_bairro(self, alocacao: _AlocacaoDeLotes) -> None:
        """F3: densidade, sobre TODOS os quarteirões (não por zona), com teto próprio.
        Roda depois dos marcos (mesmo `ocupados`), então marco nunca perde lugar pra
        uma quitanda. Nunca reduz a fração residencial abaixo do piso configurado."""
        candidatos_bairro = self.modelo.catalogo_comercio_bairro()
        teto_bairro = cfg_get(self.cfg, "cidade_geo_comercio_bairro_max_por_quarteirao")
        fracao_residencial_min = cfg_get(self.cfg, "cidade_geo_fracao_residencial_min")
        n_lotes = len(self._lotes)
        orcamento_bairro = max(0, int(n_lotes * (1.0 - fracao_residencial_min)) - len(alocacao.ocupados))
        if orcamento_bairro <= 0:
            return

        vistas = set()
        todos_quarteiroes = []
        for _, quadra in self._lotes:
            if quadra.id not in vistas:
                vistas.add(quadra.id)
                todos_quarteiroes.append(quadra)
        self.rng.shuffle(todos_quarteiroes)

        encomendas_bairro = []
        for entrada in candidatos_bairro:
            encomendas_bairro.extend([entrada] * (n_lotes // entrada["um_a_cada_n_lotes"]))
        self.rng.shuffle(encomendas_bairro)

        rodizio_bairro = collections.Counter()
        notaveis_em_bairro = collections.Counter()
        for entrada in encomendas_bairro[:orcamento_bairro]:
            quadra = self.modelo.escolher_quadra("_bairro", todos_quarteiroes, teto_bairro,
                                                  alocacao.tem_vaga, rodizio_bairro, notaveis_em_bairro)
            if quadra is None:
                continue
            livres = [p for p in alocacao.lotes_por_quarteirao[quadra.id] if p not in alocacao.ocupados]
            alocacao.ocupados[self.rng.choice(livres)] = entrada

    def _emitir_edificios(self, alocacao: _AlocacaoDeLotes) -> None:
        """Passada final: o resto. Lote com atribuição (marco ou comércio de bairro) usa
        a entrada atribuída; lote sem atribuição vira Residência."""
        residencia_padrao = cfg_get(self.cfg, "cidade_geo_residencia_padrao")
        entrada_padrao = cfg_get(self.cfg, "cidade_geo_catalogo_entrada_padrao")
        idx_edificio = 0

        for pos, (lote, quadra) in enumerate(self._lotes):
            cx = sum(p[0] for p in lote) / len(lote)
            cy = sum(p[1] for p in lote) / len(lote)

            if self.terreno is not None and self._declividade_local(cx, cy) > self._declividade_max:
                continue  # lote íngreme demais — chão vazio, edifício nenhum

            footprint = self._footprint_edificio(lote)
            if footprint is None:
                continue  # lote estreito demais pro recuo — idem

            entrada = alocacao.ocupados.get(pos)
            if entrada is None:
                nome_tipo, categoria = "Residência", "residencia"
                capacidade, salario = residencia_padrao["capacidade"], residencia_padrao["salario_base"]
            else:
                nome_tipo = entrada["tipo_local"]
                categoria = entrada["categoria"]
                capacidade = entrada.get("capacidade", entrada_padrao["capacidade"])
                salario = entrada.get("salario_base", entrada_padrao["salario_base"])

            idx_edificio += 1
            slug_id = f"{self.nome.lower().replace(' ', '_')}_{idx_edificio:03d}"
            nome_completo = (f"{nome_tipo} de {self.nome}" if nome_tipo != "Residência"
                              else f"Residência {idx_edificio:03d} — {quadra.bairro}")

            altitude_local = self._altitude_local(cx, cy)
            self._add_feature("Polygon", footprint + [footprint[0]], "edificio", {
                "id": slug_id,
                "nome": nome_completo,
                "categoria": categoria,
                "tipo_local": nome_tipo,
                "capacidade": capacidade,
                "salario_base": salario,
                "bairro": quadra.bairro,
                "quarteirao_id": self._quarteirao_id_str(quadra.id),
                "dono_npc_id": "",
                # D2/Caminho B: abre a porta pra Fase 5 gerar narrativa coerente ("a forja
                # fica na parte alta da cidade").
                "altitude": round(altitude_local, 6) if altitude_local is not None else None,
            })

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


def gerar_geometria_para_manifesto(nome_filtro=None):
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ Manifesto não encontrado em {MANIFEST_PATH}.")
        sys.exit(1)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # E5: índice por cidade (database/cidades/_indice.json — extensão .json, não
    # .geojson, pra `_listar_arquivos_geojson_cidades` não confundir com uma "cidade"
    # fantasma). Regeração de UMA cidade (nome_filtro) faz merge com o índice existente
    # em vez de sobrescrever as outras 14.
    indice_path = os.path.join(OUTPUT_DIR, "_indice.json")
    indice_por_slug = {}
    if nome_filtro and os.path.exists(indice_path):
        with open(indice_path, "r", encoding="utf-8") as f:
            indice_por_slug = {c["slug"]: c for c in json.load(f).get("cidades", [])}

    total = 0
    sem_nucleo_urbanizavel = []  # F1.2: cidades onde a praça toma o núcleo inteiro
    for cont in manifest.get("continentes", []):
        for cidade in cont.get("cidades", []):
            if nome_filtro and cidade["nome"].lower() != nome_filtro.lower():
                continue
            if "x_global" not in cidade or "y_global" not in cidade:
                continue

            # F4.5/F8.2: sítio medido primeiro (posição/geografia/clima) — o modelo é
            # escolhido por tipo+seed (lista de possibilidades + sorteio ponderado, rng
            # DERIVADO pra não deslocar a sequência do rng principal — Seção 10 item 1),
            # e só depois instanciado com o sítio e o rng principal prontos.
            sitio = SitioCidade.medir(cidade, cont["nome"], CARTOGRAPHER_CONFIG)
            nome_modelo = escolher_modelo(sitio, CARTOGRAPHER_CONFIG)
            rng = random.Random(sitio.seed)
            modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng)

            gerador = GeradorCidade(modelo)
            geojson = gerador.gerar()
            slug = cidade["nome"].lower().replace(" ", "_")
            caminho = os.path.join(OUTPUT_DIR, f"{slug}.geojson")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False, indent=2)
            indice_por_slug[slug] = gerador.indice(slug)
            n_edificios = sum(1 for feat in geojson["features"] if feat["properties"].get("camada") == "edificio")
            print(f"  🏰 {cidade['nome']:<24} -> {caminho} ({n_edificios} edifícios)")
            if modelo.malha.raio_nucleo == 0.0:
                sem_nucleo_urbanizavel.append(cidade["nome"])
            total += 1

    with open(indice_path, "w", encoding="utf-8") as f:
        json.dump({
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "cidades": list(indice_por_slug.values()),
        }, f, ensure_ascii=False, indent=2)

    if sem_nucleo_urbanizavel:
        print(f"  ℹ️  {len(sem_nucleo_urbanizavel)} cidade(s) com núcleo cívico não-urbanizável "
              f"(praça toma o disco inteiro — F1.2): {', '.join(sem_nucleo_urbanizavel)}")
    print(f"✅ [GEOMETRIA-CIDADE] {total} cidade(s) geradas. Índice: {indice_path}")


if __name__ == "__main__":
    nome_filtro = sys.argv[1] if len(sys.argv) > 1 else None
    gerar_geometria_para_manifesto(nome_filtro)
