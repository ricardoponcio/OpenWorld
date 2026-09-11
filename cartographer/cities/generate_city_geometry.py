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
from datetime import datetime

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

import numpy as np
from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.tiles.render import obter_cartografo
from cartographer.cities.escala import metros_por_pixel_mundo, zoom_min_por_camada
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

        # E6 (Seção 5.6): raio e nº de anéis deixam de ser um valor fixo por tamanho —
        # sorteados dentro de uma faixa com `self.rng` (determinístico por nome), é isso
        # que faz duas cidades "media" saírem diferentes. `cidade_geo_raio_m_por_tamanho`
        # sobrevive só como raio NOMINAL (usado por escala.py:tabela_zoom_min pro popup).
        faixa_raio = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(
            self.tamanho, [500.0, 500.0])
        self.raio_m = self.rng.uniform(*faixa_raio)
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(self.tamanho, 2)
        faixa_aneis = cfg_get(config, "cidade_geo_num_aneis_faixa_por_tamanho").get(
            self.tamanho, [2, 2])
        self.num_aneis = self.rng.randint(int(faixa_aneis[0]), int(faixa_aneis[1]))
        self.irreg = cfg_get(config, "cidade_geo_irregularidade_via")
        # E2 (Seção 5.2): alvo de área do lote passa a depender da banda (centro denso,
        # borda folgada) e de um fator sorteado por cidade — ver `_area_alvo_lote`.
        self.lote_area_base = cfg_get(config, "cidade_geo_lote_area_base_m2")
        self.lote_fator_por_banda = cfg_get(config, "cidade_geo_lote_fator_por_banda")
        self.lote_profundidade_max = cfg_get(config, "cidade_geo_lote_profundidade_max")
        faixa_fator_cidade = cfg_get(config, "cidade_geo_lote_fator_cidade_faixa")
        self.lote_fator_cidade = self.rng.uniform(*faixa_fator_cidade)
        self.quadra_area_minima = cfg_get(config, "cidade_geo_quadra_area_minima_m2")
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")
        self.via_largura_por_classe = cfg_get(config, "cidade_via_largura_m_por_classe")
        # E3 (Seção 5.3): footprint da edificação — recuo da divisa do lote e taxa de
        # ocupação (com jitter por construção, pra quadra não virar tabuleiro perfeito).
        self.edificacao_recuo = cfg_get(config, "cidade_geo_edificacao_recuo_m")
        self.edificacao_taxa_ocupacao = cfg_get(config, "cidade_geo_edificacao_taxa_ocupacao")
        self.edificacao_jitter = cfg_get(config, "cidade_geo_edificacao_jitter")
        self.praca_raio = cfg_get(config, "cidade_geo_praca_raio_m")
        self.fracao_residencial_base = cfg_get(config, "cidade_geo_fracao_residencial")
        # Toda conversão metro <-> px de mundo passa por aqui (cartographer/cities/escala.py).
        self.metros_por_px = metros_por_pixel_mundo(config)
        # E6: recebe o RAIO REAL sorteado acima, não o rótulo de tamanho — senão toda
        # cidade "media" acenderia rua/edifício no mesmo zoom, apagando a variedade.
        self.zoom_min_camada = zoom_min_por_camada(config, self.raio_m)

        # E6: `max(6, num_portoes*2)` amarrava o número de setores ao de portões e forçava
        # o espaçamento dos portões a ser sempre perfeito. Agora é sorteado dentro de
        # `cidade_geo_setores_por_portao_faixa`, com piso em `num_portoes*2` (abaixo disso
        # não sobra setor pra alternar portão/não-portão).
        faixa_setores_por_portao = cfg_get(config, "cidade_geo_setores_por_portao_faixa")
        sorteio_setores = self.rng.uniform(*faixa_setores_por_portao)
        self.num_setores = max(self.num_portoes * 2, round(self.num_portoes * sorteio_setores))
        self.features = []
        self._contagem_catalogo = {}  # tipo_local -> quantos já colocados

        # D2/Caminho B (DIAGNOSTICO_V3 Seção 13.5 Passo 5): o terreno na escala da cidade
        # passou a existir. Amostrar aqui é o que liga a geometria urbana ao relevo do
        # mundo — antes isto era ruído inventado localmente, sem relação com o continente.
        # `obter_cartografo()` é o TileCartographer de processo único montado a partir do
        # manifesto — não instanciar um novo aqui, um layout diferente geraria terreno
        # diferente do que o mapa mostra.
        cartografo = obter_cartografo()
        self.terreno = None
        self._grad_y = None
        self._grad_x = None
        self._declividade_max = cfg_get(config, "cidade_geo_declividade_max")
        if cartografo is not None:
            lado_px = 2.0 * self.raio_m / self.metros_por_px
            janela = cartografo.gerar_janela(
                self.cx_mundo - lado_px / 2, self.cy_mundo - lado_px / 2,
                self.cx_mundo + lado_px / 2, self.cy_mundo + lado_px / 2,
                64, 64,
                oitavas_extra=cfg_get(config, "tile_oitavas_max") - cfg_get(config, "ruido_macro_oitavas"),
            )
            self.terreno = janela[:, :, 0]
            self._grad_y, self._grad_x = np.gradient(self.terreno)

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
    # a grade 64x64 amostrada em __init__. Coordenadas de entrada são metros locais
    # (mesma origem no centro da cidade usada pelo resto da geometria).
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
        — usado pra rejeitar lote íngreme demais (edifício) e preferir setor mais plano
        (praça, portão)."""
        if self.terreno is None:
            return 0.0
        iy, ix = self._indice_terreno(x_m, y_m)
        m_por_celula = (2.0 * self.raio_m) / self.terreno.shape[0]
        return float(math.hypot(self._grad_x[iy, ix], self._grad_y[iy, ix]) / m_por_celula)

    # `zoom_min` é calculado em cartographer/cities/escala.py a partir do raio real da
    # cidade e dos alvos em px de tela do config.json — nunca uma tabela escrita à mão, que
    # é como a anterior acabou calibrada CONTRA o bug de escala do D1 (4 níveis altos demais).

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

    def _melhor_centro_praca(self, raio_banda0):
        """D2/Caminho B (Seção 13.5 Passo 5): procura, entre alguns candidatos dentro do
        anel central, o de menor declividade — sem ultrapassar o raio da banda 0 (onde
        nenhum lote é gerado), pra nunca invadir o quarteirão vizinho."""
        if self.terreno is None:
            return (0.0, 0.0)
        raio_disponivel = max(0.0, raio_banda0 - self.praca_raio) * 0.6
        if raio_disponivel <= 0.0:
            return (0.0, 0.0)
        melhor = (0.0, 0.0)
        melhor_declive = self._declividade_local(0.0, 0.0)
        n_candidatos = 12
        for k in range(n_candidatos):
            ang = 2 * math.pi * k / n_candidatos
            x, y = raio_disponivel * math.cos(ang), raio_disponivel * math.sin(ang)
            declive = self._declividade_local(x, y)
            if declive < melhor_declive:
                melhor_declive, melhor = declive, (x, y)
        return melhor

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

        # Portões: subconjunto dos setores, na borda externa. D2/Caminho B (Seção 13.5
        # Passo 5): quando há terreno, prefere os setores de menor declividade — é por
        # onde uma estrada real sairia. Mantém espaçamento mínimo entre portões pra não
        # agrupar todos no mesmo lado plano; sem terreno, cai no espaçamento uniforme
        # original.
        #
        # Calculado ANTES de emitir as ruas porque é ele que define quais radiais são
        # via principal (a que liga o portão ao centro). Nenhum sorteio acontece aqui, só
        # ordenação por declividade, então adiantar este bloco não mexe na sequência do
        # RNG nem, portanto, na geometria gerada.
        passo = max(1, self.num_setores // self.num_portoes)

        def _rotacao_uniforme(deslocamento):
            """Os portões igualmente espaçados, girados de `deslocamento` setores."""
            return [(deslocamento + k * passo) % self.num_setores for k in range(self.num_portoes)]

        if self.terreno is not None:
            declividades = [self._declividade_local(*borda[i]) for i in range(self.num_setores)]
            ordem = sorted(range(self.num_setores), key=lambda i: declividades[i])
            # O espaçamento mínimo é o próprio espaçamento ideal. Era
            # `num_setores // (num_portoes * 2)`, que como num_setores nunca passa de
            # `num_portoes * 2` dava sempre 1 — ou seja, "não pode ser o vizinho imediato"
            # virava "pode qualquer coisa", e a guarda não guardava nada: 12 das 14 cidades
            # saíam com portões colados (Aurora Vales tinha os três nos setores 3, 4 e 5,
            # com um vão de 4 setores do outro lado). Passava despercebido enquanto a rua
            # era um fio; com a via principal a 11 m isso vira três avenidas grudadas.
            espacamento_min = passo
            indices_portao = []
            for i in ordem:
                if all(min((i - j) % self.num_setores, (j - i) % self.num_setores) >= espacamento_min
                       for j in indices_portao):
                    indices_portao.append(i)
                if len(indices_portao) == self.num_portoes:
                    break
            if len(indices_portao) < self.num_portoes:
                # O guloso pode se encurralar (escolher um setor que inviabiliza o resto).
                # Cai na rotação uniforme mais plana: espaçamento perfeito garantido, e o
                # terreno ainda decide qual das `passo` rotações. A versão anterior
                # completava com setores fixos sem checar distância, o que reintroduzia
                # exatamente os portões colados que o bloco acima tenta evitar.
                indices_portao = min(
                    (_rotacao_uniforme(d) for d in range(passo)),
                    key=lambda ids: sum(declividades[i] for i in ids),
                )
        else:
            indices_portao = _rotacao_uniforme(0)

        # Ruas: cada anel (loop fechado) + cada radial (centro -> borda). `classe_via` é a
        # hierarquia viária (larguras em cidade_via_largura_m_por_classe), `tipo_via`
        # continua descrevendo o papel geométrico na malha — perguntas diferentes.
        # A radial que termina num portão é a via principal: numa cidade real é o caminho
        # que a estrada de fora vira ao entrar, e por isso a rua mais larga.
        setores_portao = set(indices_portao)
        self._setores_portao = setores_portao  # reusado pela E1 (_gerar_quarteiroes_e_lotes)
        for j, linha in enumerate(vertices):
            self._add_feature("LineString", linha + [linha[0]], "rua",
                              {"tipo_via": "anel", "classe_via": "anel", "indice": j})
        for i in range(self.num_setores):
            pontos = [(0.0, 0.0)] + [vertices[j][i] for j in range(self.num_aneis + 1)]
            classe = "principal" if i in setores_portao else "secundaria"
            self._add_feature("LineString", pontos, "rua",
                              {"tipo_via": "radial", "classe_via": classe, "indice": i})

        for i in indices_portao:
            self._add_feature("Point", borda[i], "portao", {"nome": f"Portão de {self.nome} #{i}"})

        # Praça central — círculo decorativo; NENHUM lote/edifício entra na banda 0
        # (reservada pra praça), então não há checagem de sobreposição a fazer. D2/Caminho
        # B (Seção 13.5 Passo 5): em vez do centro geométrico fixo, procura o ponto mais
        # plano dentro do próprio anel central — sem mover a malha viária, que continua
        # ancorada em (0,0) (Seção 13.5: "não troque as duas coisas ao mesmo tempo").
        centro_praca = self._melhor_centro_praca(raios_base[0])
        circulo = []
        for k in range(16):
            dx, dy = self._polar(self.praca_raio, 2 * math.pi * k / 16)
            circulo.append((centro_praca[0] + dx, centro_praca[1] + dy))
        self._add_feature("Polygon", circulo + [circulo[0]], "praca", {"nome": f"Praça Central de {self.nome}"})

        self._vertices = vertices
        self._angulos = angulos

    # ------------------------------------------------------------------
    # 4.2.4/4.2.5 — Quarteirões e lotes (subdivisão recursiva pelo lado maior)
    # ------------------------------------------------------------------
    @staticmethod
    def _area_sinalizada(quad):
        """Shoelace COM sinal — positivo/negativo conforme a orientação (horário vs.
        anti-horário). `_area_quad` é o valor absoluto disto; a E1 usa o sinal pra
        detectar quad invertido depois do inset (`_encolher_quad`)."""
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
    def _interseccao_retas(p1, d1, p2, d2):
        """Interseção de duas retas em forma ponto + t*direção (sistema 2x2). `None` se
        as retas forem paralelas (determinante ~0) — cabe ao chamador decidir o fallback
        (Seção 6/E1: "use o ponto deslocado direto")."""
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
        degenerar (quadra estreita demais pra caber a rua, ou polígono invertido) — Seção
        6/E1 do ESPEC_TECIDO_URBANO.md."""
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
            # Normal a 90° da aresta — testada contra o centroide, nunca presumida
            # (o mesmo bug de orientação já pago em `_subdividir_lote`, ver comentário lá).
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
                # Arestas paralelas: usa o ponto deslocado direto (média dos dois pontos
                # de referência), como orienta a Seção 6/E1.
                pt = ((p_prev[0] + p_cur[0]) / 2.0, (p_prev[1] + p_cur[1]) / 2.0)
            novo.append(pt)

        # Degeneração geométrica: um inset que "virou do avesso" (recuo maior que o quad
        # aguenta) produz um quad com orientação oposta à original, ou área ~0 — descarta
        # em vez de emitir polígono invertido. O piso de área ESPECÍFICO de cada uso
        # (quadra mínima urbanizável na E1, nenhum na E3) fica por conta do chamador —
        # `_encolher_quad` é geometria pura, não sabe se está encolhendo quarteirão ou
        # footprint de edifício.
        if self._area_quad(novo) < 1e-6:
            return None
        if self._area_sinalizada(novo) * orientacao_original <= 0:
            return None
        return novo

    def _classe_via_radial(self, indice_setor):
        return "principal" if indice_setor in self._setores_portao else "secundaria"

    def _distancia_faixa_dominio(self, classe):
        largura = self.via_largura_por_classe.get(classe, self.via_largura_por_classe.get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    def _area_alvo_lote(self, banda):
        """E2 (Seção 5.2): alvo de área do lote cresce com a banda (centro denso, borda
        folgada) e leva um fator por cidade sorteado da seed do nome, pra duas cidades do
        mesmo tamanho não serem idênticas."""
        return self.lote_area_base * (self.lote_fator_por_banda ** (banda - 1)) * self.lote_fator_cidade

    def _subdividir_lote(self, quad, area_alvo, profundidade=0):
        """Corta o quadrilátero ao meio pelo lado mais longo, recursivamente, até a área
        ficar perto do alvo — é a "subdivisão recursiva pelo lado maior" da Seção 4.2.5,
        aplicada a um quad em vez de um polígono arbitrário (a malha radial+anel só
        produz quads, nunca formas mais complexas)."""
        area = self._area_quad(quad)
        if area <= area_alvo * 1.6 or profundidade >= self.lote_profundidade_max:
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

        return (self._subdividir_lote(parte1, area_alvo, profundidade + 1) +
                self._subdividir_lote(parte2, area_alvo, profundidade + 1))

    def _gerar_quarteiroes_e_lotes(self):
        """Bandas 1..num_aneis (banda 0 é a praça — Seção 4.2.8 adaptada: zoneamento por
        distância ao centro, comércio/artesanato perto, residencial pra fora).

        E1 (Seção 5.1): cada quad encolhe pra dentro pela faixa de domínio da rua que o
        limita ANTES de virar quarteirão/lote — a rua passa a existir como vazio entre
        construções, não como traço por cima do chão. Quadra que degenera (estreita demais
        depois do recuo) é descartada, não vira polígono invertido."""
        self._lotes = []  # lista de (quad, bairro, banda)
        for j in range(1, self.num_aneis + 1):
            raio_interno = self._vertices[j - 1]
            raio_externo = self._vertices[j]
            bairro = "Centro" if j == 1 else ("Bairro Médio" if j < self.num_aneis else "Bairro Externo")

            for i in range(self.num_setores):
                i2 = (i + 1) % self.num_setores
                quad = [raio_interno[i], raio_externo[i], raio_externo[i2], raio_interno[i2]]

                # As 4 arestas do quad caem, cada uma, sobre a linha de centro de uma rua
                # (Seção 6/E1, tabela de correspondência aresta -> rua).
                distancias = [
                    self._distancia_faixa_dominio(self._classe_via_radial(i)),   # interno[i] -> externo[i]
                    self._distancia_faixa_dominio("anel"),                       # externo[i] -> externo[i2]
                    self._distancia_faixa_dominio(self._classe_via_radial(i2)),  # externo[i2] -> interno[i2]
                    self._distancia_faixa_dominio("anel"),                       # interno[i2] -> interno[i]
                ]
                quad_urbanizavel = self._encolher_quad(quad, distancias)
                if quad_urbanizavel is None or self._area_quad(quad_urbanizavel) < self.quadra_area_minima:
                    continue  # quadra degenerada, ou pequena demais pra urbanizar (E1)

                self._add_feature("Polygon", quad_urbanizavel + [quad_urbanizavel[0]], "quarteirao",
                                  {"bairro": bairro, "banda": j})

                area_alvo = self._area_alvo_lote(j)
                lotes = self._subdividir_lote(quad_urbanizavel, area_alvo)
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

    def _footprint_edificio(self, lote):
        """E3 (Seção 5.3): footprint poligonal dentro do lote — recuo da divisa (mesmo
        inset da E1, `_encolher_quad`, com distância igual nos 4 lados) e depois um
        segundo encolhimento em torno do centroide pela RAIZ da taxa de ocupação (a área
        escala com o quadrado do fator linear). `jitter` varia a taxa por construção pra
        a quadra não virar um tabuleiro perfeito. Retorna `None` se o lote for estreito
        demais pro recuo (mesmo caso de degeneração da E1)."""
        recuado = self._encolher_quad(lote, [self.edificacao_recuo] * 4)
        if recuado is None:
            return None
        jitter = self.rng.uniform(-self.edificacao_jitter, self.edificacao_jitter)
        taxa_efetiva = min(0.95, max(0.15, self.edificacao_taxa_ocupacao + jitter))
        fator_linear = math.sqrt(taxa_efetiva)
        cx = sum(p[0] for p in recuado) / len(recuado)
        cy = sum(p[1] for p in recuado) / len(recuado)
        return [(cx + (x - cx) * fator_linear, cy + (y - cy) * fator_linear) for x, y in recuado]

    def _gerar_edificios(self):
        """Um edifício por lote — Polygon (footprint dentro do lote, Seção 5.3), não mais
        um Point no centroide. `builder/populate.py` importa isso como `Local` calculando
        o centroide do anel externo (E4)."""
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

            # D2/Caminho B (Seção 13.5 Passo 5): rejeita lote íngreme demais — vira
            # espaço vazio (sem feature "edificio"), não um edifício empurrado pro lugar
            # errado. O polígono do lote em si já foi adicionado em
            # `_gerar_quarteiroes_e_lotes` e continua de pé.
            if self.terreno is not None and self._declividade_local(cx, cy) > self._declividade_max:
                continue

            # E3: footprint poligonal dentro do lote. Lote estreito demais pro recuo
            # (mesma degeneração da E1) também vira espaço vazio, não um prédio espremido.
            footprint = self._footprint_edificio(lote)
            if footprint is None:
                continue

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

            altitude_local = self._altitude_local(cx, cy)
            self._add_feature("Polygon", footprint + [footprint[0]], "edificio", {
                "id": slug_id,
                "nome": nome_completo,
                "categoria": categoria,
                "tipo_local": nome_tipo,
                "capacidade": capacidade,
                "salario_base": salario,
                "bairro": bairro,
                "dono_npc_id": "",
                # D2/Caminho B (Seção 13.5 Passo 5): abre a porta pra Fase 5 gerar
                # narrativa coerente ("a forja fica na parte alta da cidade").
                "altitude": round(altitude_local, 6) if altitude_local is not None else None,
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

    def indice(self, slug):
        """E5 (Seção 5.5/6): bbox da cidade em px de MUNDO + contagem/zoom_min por camada,
        pro `web/composed_routes.py` descartar a cidade inteira sem abrir o arquivo quando
        ela não intersecta o bbox pedido, ou quando nenhuma camada visível já acendeu
        naquele zoom. Reaproveita a mesma conversão [lng,lat]=[x_mundo,-y_mundo] (Seção
        2.3) usada nas features — desfaz aqui pra voltar a px de mundo."""
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
            "slug": slug, "nome": self.nome, "tamanho": self.tamanho,
            "raio_m": self.raio_m, "bbox": bbox, "camadas": camadas,
        }

    @staticmethod
    def _achatar_coords(coords):
        """Percorre coordinates de qualquer geometry (Point/LineString/Polygon) até o par
        [lng,lat] mais interno — mesma lógica de `achatar` em web/composed_routes.py."""
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
            indice_por_slug[slug] = gerador.indice(slug)
            n_edificios = sum(1 for feat in geojson["features"] if feat["properties"].get("camada") == "edificio")
            print(f"  🏰 {cidade['nome']:<24} -> {caminho} ({n_edificios} edifícios)")
            total += 1

    with open(indice_path, "w", encoding="utf-8") as f:
        json.dump({
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "cidades": list(indice_por_slug.values()),
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ [GEOMETRIA-CIDADE] {total} cidade(s) geradas. Índice: {indice_path}")


if __name__ == "__main__":
    nome_filtro = sys.argv[1] if len(sys.argv) > 1 else None
    gerar_geometria_para_manifesto(nome_filtro)
