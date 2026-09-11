"""
SCRIPT: generate_city_geometry.py
FUNÇÃO: Gera a geometria vetorial real de uma cidade (Fase 4, P2.2) — ruas, quarteirões,
        lotes, edifícios nomeados e muralha — em `database/cidades/<slug>.geojson`.

CONCEITO CENTRAL (Seção 2.1 do plano): a cidade é SUB-PIXEL na escala do mundo (1 px de
mundo ≈ 250 km). Não existe informação de terreno real nessa escala — então a geometria
NÃO é derivada do terreno do mundo, é gerada num sistema de coordenadas LOCAL próprio
(origem no centro da cidade, unidade = metro), determinístico a partir do nome da cidade
(`zlib.crc32`, nunca `hash()`), e só convertida pra pixel de mundo no fim:

    desloc_px = desloc_m / (escala_pixel_area_km2 * 1000)

Isso é MENOS do que o catálogo aspiracional da Seção 4.3 do plano (~80 categorias, regras
de coerência por bioma/rio/adjacência a água) — implementado aqui um SUBCONJUNTO curado
(~30 tipos_local, config `cidade_geo_catalogo_edificios`) cobrindo governo/fé/saber/
comércio/artesanato/hospedagem/produção primária. Ampliar é editar o catálogo em
config.json, não este arquivo.

USO:
    venv/bin/python cartographer/cities/generate_city_geometry.py            # todas as cidades do manifesto
    venv/bin/python cartographer/cities/generate_city_geometry.py "Nome"     # só uma
"""
import os
import sys
import json
import math
import random
import zlib

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

import numpy as np
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"
OUTPUT_DIR = "database/cidades"


class GeradorCidade:
    def __init__(self, cidade: dict, continente_nome: str, config: dict):
        self.cidade = cidade
        self.continente_nome = continente_nome
        self.cfg = config
        self.nome = cidade["nome"]
        self.tamanho = cidade.get("tamanho", "pequeno").lower()
        self.tipo = cidade.get("tipo", "").lower()
        self.cx_mundo = float(cidade["x_global"])
        self.cy_mundo = float(cidade["y_global"])

        # Determinístico — zlib.crc32, nunca hash() (aleatorizado por processo, mesmo
        # achado já pago em city_roi_zoom.py/city_manager_ai.py).
        self.seed = zlib.crc32(self.nome.encode("utf-8"))
        self.rng = random.Random(self.seed)
        self.np_rng = np.random.default_rng(self.seed)

        self.raio_m = cfg_get(config, "cidade_geo_raio_m_por_tamanho").get(self.tamanho, 500)
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(self.tamanho, 2)
        self.num_aneis = cfg_get(config, "cidade_geo_num_aneis_por_tamanho").get(self.tamanho, 2)
        self.irreg = cfg_get(config, "cidade_geo_irregularidade_via")
        self.lote_area_alvo = cfg_get(config, "cidade_geo_lote_area_alvo_m2")
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")
        self.praca_raio = cfg_get(config, "cidade_geo_praca_raio_m")
        self.fracao_residencial_base = cfg_get(config, "cidade_geo_fracao_residencial")
        self.escala_pixel_area_km2 = cfg_get(config, "escala_pixel_area_km2")

        self.num_setores = max(6, self.num_portoes * 2)
        self.features = []
        self._contagem_catalogo = {}  # tipo_local -> quantos já colocados

    # ------------------------------------------------------------------
    # Transform local(m) -> mundo(px) — Seção 2.1/2.3 do plano
    # ------------------------------------------------------------------
    def _mundo(self, x_m, y_m):
        metros_por_px = self.escala_pixel_area_km2 * 1000.0
        return self.cx_mundo + x_m / metros_por_px, self.cy_mundo + y_m / metros_por_px

    def _geojson_coord(self, x_m, y_m):
        """[lng, lat] = [x_mundo, -y_mundo] — mesma conversão de pixelParaLatLng (Seção 2.3),
        o Leaflet plota direto sem transformar nada no frontend."""
        x_mundo, y_mundo = self._mundo(x_m, y_m)
        return [round(x_mundo, 6), round(-y_mundo, 6)]

    # A cidade é sub-pixel na escala do mundo (Seção 2.1: cidade "grande" tem ~0,007 px
    # de mundo de diâmetro) — sem isso, a geometria inteira (ruas, edifícios) apareceria
    # amontoada em qualquer zoom baixo. `zoom_min` calculado pra cada camada só aparecer
    # quando 1 tile (256px) já cobre uma fração comparável ao tamanho real da cidade —
    # medido: em z11 a cidade ocupa ~6% de um tile (dá pra ver que "tem algo ali"); em
    # z13 ~23%; em z14 ~46% (bom pra andar pelas ruas). `tile_zoom_maximo_ui` (config)
    # precisa alcançar isso — foi subido de 7 pra 16 junto com esta mudança.
    ZOOM_MIN_POR_CAMADA = {
        "muralha": 11, "torre": 11, "portao": 11, "praca": 11,
        "rua": 12, "quarteirao": 12,
        "lote": 14, "edificio": 13,
    }

    def _add_feature(self, geom_type, coords_m, camada, props=None):
        if geom_type == "Point":
            coords = self._geojson_coord(*coords_m)
        else:
            coords = [self._geojson_coord(*p) for p in coords_m]
            if geom_type == "Polygon":
                coords = [coords]
        p = {"camada": camada, "zoom_min": self.ZOOM_MIN_POR_CAMADA.get(camada, 8)}
        if props:
            p.update(props)
        self.features.append({"type": "Feature", "geometry": {"type": geom_type, "coordinates": coords}, "properties": p})

    @staticmethod
    def _polar(raio, angulo):
        return (raio * math.cos(angulo), raio * math.sin(angulo))

    # ------------------------------------------------------------------
    # 4.2.2/4.2.3 — Núcleo, portões e malha viária (radiais + anéis, organica/medieval)
    # ------------------------------------------------------------------
    def _construir_malha(self):
        angulos = [2 * math.pi * i / self.num_setores for i in range(self.num_setores)]
        raios_base = [self.raio_m * (j + 1) / (self.num_aneis + 1) for j in range(self.num_aneis)]

        # Perturbação organica: array fixo (não depende de ordem de chamada de RNG),
        # reaproveitado tanto pelos anéis quanto pelos quarteirões — garante que rua e
        # quarteirão compartilhem exatamente o mesmo vértice (sem buraco nem sobreposição).
        perturb = self.np_rng.uniform(-1.0, 1.0, size=(self.num_aneis + 1, self.num_setores))

        # vertices[j][i] = (x_m, y_m) do anel j (0..num_aneis-1 = interiores, num_aneis = borda)
        vertices = []
        for j in range(self.num_aneis):
            raio_linha = []
            for i in range(self.num_setores):
                r = raios_base[j] * (1.0 + self.irreg * perturb[j, i])
                raio_linha.append(self._polar(r, angulos[i]))
            vertices.append(raio_linha)
        borda = []
        for i in range(self.num_setores):
            r = self.raio_m * (1.0 + self.irreg * 0.5 * perturb[self.num_aneis, i])
            borda.append(self._polar(r, angulos[i]))
        vertices.append(borda)

        # Ruas: cada anel (loop fechado) + cada radial (centro -> borda)
        for j, linha in enumerate(vertices):
            self._add_feature("LineString", linha + [linha[0]], "rua", {"tipo_via": "anel", "indice": j})
        for i in range(self.num_setores):
            pontos = [(0.0, 0.0)] + [vertices[j][i] for j in range(self.num_aneis + 1)]
            self._add_feature("LineString", pontos, "rua", {"tipo_via": "radial", "indice": i})

        # Portões: subconjunto dos setores, evenly spaced, na borda externa
        passo = max(1, self.num_setores // self.num_portoes)
        indices_portao = [(k * passo) % self.num_setores for k in range(self.num_portoes)]
        for i in indices_portao:
            self._add_feature("Point", borda[i], "portao", {"nome": f"Portão de {self.nome} #{i}"})

        # Praça central — círculo decorativo; NENHUM lote/edifício entra na banda 0
        # (reservada pra praça), então não há checagem de sobreposição a fazer.
        circulo = [self._polar(self.praca_raio, 2 * math.pi * k / 16) for k in range(16)]
        self._add_feature("Polygon", circulo + [circulo[0]], "praca", {"nome": f"Praça Central de {self.nome}"})

        self._vertices = vertices
        self._angulos = angulos

    # ------------------------------------------------------------------
    # 4.2.4/4.2.5 — Quarteirões e lotes (subdivisão recursiva pelo lado maior)
    # ------------------------------------------------------------------
    @staticmethod
    def _area_quad(quad):
        """Fórmula do shoelace — área de um polígono simples (aqui sempre convexo o
        bastante pra não importar orientação)."""
        area = 0.0
        n = len(quad)
        for i in range(n):
            x1, y1 = quad[i]
            x2, y2 = quad[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    def _subdividir_lote(self, quad, profundidade=0, max_profundidade=5):
        """Corta o quadrilátero ao meio pelo lado mais longo, recursivamente, até a área
        ficar perto do alvo — é a "subdivisão recursiva pelo lado maior" da Seção 4.2.5,
        aplicada a um quad em vez de um polígono arbitrário (a malha radial+anel só
        produz quads, nunca formas mais complexas)."""
        area = self._area_quad(quad)
        if area <= self.lote_area_alvo * 1.6 or profundidade >= max_profundidade:
            return [quad]

        # Acha o lado mais longo e corta pelo meio dele e do seu oposto. Fórmula em
        # índice modular relativo a `i0` (não por posição ordenada — um `sorted([i0,i1])`
        # aqui quebra a correspondência entre m0/m1 e os vértices quando `i0` não é 0 ou
        # 1, produzindo um quad "em zigue-zague" — bug real, pego só depois de desenhar
        # a malha e notar lotes se cruzando).
        n = len(quad)  # sempre 4: a malha radial+anel só produz quads
        comprimentos = [math.dist(quad[i], quad[(i + 1) % n]) for i in range(n)]
        i0 = comprimentos.index(max(comprimentos))

        def meio(a, b):
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

        m0 = meio(quad[i0], quad[(i0 + 1) % n])
        m1 = meio(quad[(i0 + 2) % n], quad[(i0 + 3) % n])

        parte1 = [m0, quad[(i0 + 1) % n], quad[(i0 + 2) % n], m1]
        parte2 = [m1, quad[(i0 + 3) % n], quad[i0 % n], m0]

        return (self._subdividir_lote(parte1, profundidade + 1, max_profundidade) +
                self._subdividir_lote(parte2, profundidade + 1, max_profundidade))

    def _gerar_quarteiroes_e_lotes(self):
        """Bandas 1..num_aneis (banda 0 é a praça — Seção 4.2.8 adaptada: zoneamento por
        distância ao centro, comércio/artesanato perto, residencial pra fora)."""
        self._lotes = []  # lista de (quad, bairro, banda)
        for j in range(1, self.num_aneis + 1):
            raio_interno = self._vertices[j - 1]
            raio_externo = self._vertices[j]
            bairro = "Centro" if j == 1 else ("Bairro Médio" if j < self.num_aneis else "Bairro Externo")

            for i in range(self.num_setores):
                i2 = (i + 1) % self.num_setores
                quad = [raio_interno[i], raio_externo[i], raio_externo[i2], raio_interno[i2]]
                self._add_feature("Polygon", quad + [quad[0]], "quarteirao", {"bairro": bairro, "banda": j})

                lotes = self._subdividir_lote(quad)
                for lote in lotes:
                    self._add_feature("Polygon", lote + [lote[0]], "lote", {"bairro": bairro, "banda": j})
                    self._lotes.append((lote, bairro, j))

    # ------------------------------------------------------------------
    # 4.3 — Catálogo de edifícios (config-driven, subconjunto curado)
    # ------------------------------------------------------------------
    def _candidatos_catalogo(self):
        catalogo = cfg_get(self.cfg, "cidade_geo_catalogo_edificios")
        return [e for e in catalogo if not e.get("tamanhos") or self.tamanho in e["tamanhos"]]

    def _peso_efetivo(self, entrada):
        tipos_cidade = entrada.get("tipos_cidade") or []
        if self.tipo in tipos_cidade:
            return entrada["peso"] * 3.0
        if not tipos_cidade:
            return entrada["peso"]
        return entrada["peso"] * 0.25  # existe, mas é raro fora do tipo de cidade que pede

    def _escolher_edificio(self, candidatos_disponiveis):
        pesos = np.array([self._peso_efetivo(e) for e in candidatos_disponiveis], dtype=np.float64)
        if pesos.sum() <= 0:
            return None
        pesos = pesos / pesos.sum()
        idx = self.np_rng.choice(len(candidatos_disponiveis), p=pesos)
        return candidatos_disponiveis[idx]

    def _gerar_edificios(self):
        """Um edifício por lote — Point no centroide (o schema de `Local` só guarda
        `coordenadas` como ponto, então o footprint poligonal do lote já é a
        representação visual; o edifício em si não precisa de forma própria)."""
        candidatos = self._candidatos_catalogo()

        # Obrigatórios primeiro (min > 0), na ordem em que aparecem no catálogo.
        fila_tipos = []
        for e in candidatos:
            for _ in range(e.get("min", 0)):
                fila_tipos.append(e)

        n_lotes = len(self._lotes)
        n_residencial = int(round(n_lotes * self.fracao_residencial_base))

        contagem = {e["tipo_local"]: 0 for e in candidatos}
        idx_edificio = 0
        for pos, (lote, bairro, banda) in enumerate(self._lotes):
            cx = sum(p[0] for p in lote) / len(lote)
            cy = sum(p[1] for p in lote) / len(lote)

            # Fração residencial cresce com a banda (zoneamento: comércio perto do
            # centro, residencial nas bordas — Seção 4.2.8, versão simplificada).
            frac_residencial_banda = min(0.9, self.fracao_residencial_base + 0.12 * (banda - 1))
            eh_residencial = self.rng.random() < frac_residencial_banda

            if eh_residencial:
                nome_tipo, categoria, capacidade, salario = "Residência", "residencia", 5, 0
            else:
                entrada = None
                if fila_tipos:
                    entrada = fila_tipos.pop(0)
                else:
                    disponiveis = [e for e in candidatos if contagem[e["tipo_local"]] < e.get("max", 99)]
                    entrada = self._escolher_edificio(disponiveis) if disponiveis else None
                if entrada is None:
                    nome_tipo, categoria, capacidade, salario = "Residência", "residencia", 5, 0
                else:
                    nome_tipo = entrada["tipo_local"]
                    categoria = entrada["categoria"]
                    capacidade = entrada.get("capacidade", 5)
                    salario = entrada.get("salario_base", 80)
                    contagem[nome_tipo] = contagem.get(nome_tipo, 0) + 1

            idx_edificio += 1
            slug_id = f"{self.nome.lower().replace(' ', '_')}_{idx_edificio:03d}"
            nome_completo = f"{nome_tipo} de {self.nome}" if nome_tipo != "Residência" else f"Residência {idx_edificio:03d} — {bairro}"

            self._add_feature("Point", (cx, cy), "edificio", {
                "id": slug_id,
                "nome": nome_completo,
                "categoria": categoria,
                "tipo_local": nome_tipo,
                "capacidade": capacidade,
                "salario_base": salario,
                "bairro": bairro,
                "dono_npc_id": "",
            })

    # ------------------------------------------------------------------
    # 4.2.7 — Muralha (tamanho != pequeno ou tipo == fortaleza)
    # ------------------------------------------------------------------
    def _precisa_muralha(self):
        tamanhos_com_muralha = cfg_get(self.cfg, "cidade_geo_muralha_tamanhos")
        return self.tamanho in tamanhos_com_muralha or self.tipo == "fortaleza"

    def _gerar_muralha(self):
        if not self._precisa_muralha():
            return
        folga = cfg_get(self.cfg, "cidade_geo_muralha_folga_m")
        espacamento_torres = cfg_get(self.cfg, "cidade_geo_muralha_torres_espacamento_m")

        raio_muralha = self.raio_m + folga
        perturb = self.np_rng.uniform(-1.0, 1.0, size=self.num_setores)
        linha = [self._polar(raio_muralha * (1.0 + self.irreg * 0.3 * perturb[i]), self._angulos[i]) for i in range(self.num_setores)]
        self._add_feature("LineString", linha + [linha[0]], "muralha", {"nome": f"Muralha de {self.nome}"})

        perimetro = raio_muralha * 2 * math.pi
        num_torres = max(4, int(perimetro / max(1.0, espacamento_torres)))
        for k in range(num_torres):
            ang = 2 * math.pi * k / num_torres
            self._add_feature("Point", self._polar(raio_muralha, ang), "torre", {"nome": f"Torre {k + 1}"})

    # ------------------------------------------------------------------
    def gerar(self):
        self._construir_malha()
        self._gerar_quarteiroes_e_lotes()
        self._gerar_edificios()
        self._gerar_muralha()
        return {"type": "FeatureCollection", "features": self.features, "properties": {
            "cidade": self.nome, "continente": self.continente_nome, "tamanho": self.tamanho,
            "tipo": self.tipo, "seed": self.seed, "raio_m": self.raio_m,
            "x_global": self.cx_mundo, "y_global": self.cy_mundo,
        }}


def gerar_geometria_para_manifesto(nome_filtro=None):
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ Manifesto não encontrado em {MANIFEST_PATH}.")
        sys.exit(1)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = 0
    for cont in manifest.get("continentes", []):
        for cidade in cont.get("cidades", []):
            if nome_filtro and cidade["nome"].lower() != nome_filtro.lower():
                continue
            if "x_global" not in cidade or "y_global" not in cidade:
                continue
            gerador = GeradorCidade(cidade, cont["nome"], CARTOGRAPHER_CONFIG)
            geojson = gerador.gerar()
            slug = cidade["nome"].lower().replace(" ", "_")
            caminho = os.path.join(OUTPUT_DIR, f"{slug}.geojson")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False, indent=2)
            n_edificios = sum(1 for feat in geojson["features"] if feat["properties"].get("camada") == "edificio")
            print(f"  🏰 {cidade['nome']:<24} -> {caminho} ({n_edificios} edifícios)")
            total += 1

    print(f"✅ [GEOMETRIA-CIDADE] {total} cidade(s) geradas.")


if __name__ == "__main__":
    nome_filtro = sys.argv[1] if len(sys.argv) > 1 else None
    gerar_geometria_para_manifesto(nome_filtro)
