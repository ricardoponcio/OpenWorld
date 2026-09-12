"""
Testes de geometria de cidade — docs/ESPEC_DESENHO_CIDADE.md, Seção 9.2.

Cobre os invariantes que a arquitetura de modelo de cidade (F4) precisa proteger: a base
sozinha basta pra um modelo mínimo gerar uma cidade completa (T5), todo modelo registrado
responde à interface (T6), o contrato de quadrilátero (T2) e o teto de notáveis por
quarteirão (T3, regressão do bug 3.2) sobrevivem à refatoração.
"""
import sys
import os
import json
import random
import statistics

import pytest

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.generate_city_geometry import GeradorCidade
from cartographer.cities.geometria import quad
from cartographer.cities.geometria import lotes as lotes_mod
from cartographer.cities.modelos import SitioCidade, MODELOS
from cartographer.cities.modelos.base import ModeloCidade, Quadra, Malha
from config import cfg_get

_CIDADE_TESTE = {"nome": "Aurora Vales", "tamanho": "medio", "tipo": "residencial",
                  "x_global": 300, "y_global": 400}


class _ModeloMinimo(ModeloCidade):
    """Só implementa o gancho obrigatório (construir_malha) — T5/F4.7: se isso não gerar
    uma cidade completa, a base não está fazendo o trabalho compartilhado dela."""
    nome = "_teste_minimo"

    def construir_malha(self):
        quadras = []
        for banda in (1, 2):
            for setor in range(4):
                lado = 40.0
                cx, cy = setor * 60.0, banda * 60.0
                quad = [(cx - lado, cy - lado), (cx + lado, cy - lado),
                        (cx + lado, cy + lado), (cx - lado, cy + lado)]
                quadras.append(Quadra(vertices=quad, classes_aresta=["secundaria"] * 4,
                                       banda=banda, bairro=f"Bairro{banda}", id=(banda, setor)))
        return Malha(ruas=[], quadras=quadras, portoes=[], centro_praca=(0.0, 0.0),
                     raio_praca=10.0, raio_nucleo=0.0, num_bandas=3, contorno=[
                         (-40.0, -40.0), (280.0, -40.0), (280.0, 160.0), (-40.0, 160.0)])


def _gerar(nome_modelo_cls=None):
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    rng = random.Random(sitio.seed)
    cls = nome_modelo_cls or MODELOS["radial"]
    modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
    gerador = GeradorCidade(modelo)
    return gerador.gerar()


def test_base_sozinha_basta():
    """T5 — um modelo que só implementa construir_malha gera lotes, edifícios e índice."""
    geo = _gerar(_ModeloMinimo)
    camadas = {f["properties"]["camada"] for f in geo["features"]}
    assert "lote" in camadas
    assert "edificio" in camadas
    assert "quarteirao" in camadas


def test_todo_modelo_registrado_responde_a_interface():
    """T6 — cada classe em MODELOS gera uma cidade sem quebrar, com um sítio sintético."""
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        assert geo["features"], f"modelo {nome} não gerou feature nenhuma"


def test_contrato_de_quadrilatero():
    """T2 — toda Quadra de todo modelo registrado tem exatamente 4 vértices."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    for nome, cls in MODELOS.items():
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        malha = modelo.construir_malha()
        for quadra in malha.quadras:
            assert len(quadra.vertices) == 4, f"modelo {nome}: quadra com {len(quadra.vertices)} vértices"


def test_teto_de_notaveis_por_quarteirao():
    """T3 — regressão do bug 3.2 (Seção 3.2): marcos e comércio de bairro têm tetos
    INDEPENDENTES por quarteirão (F3.2 — "com o seu próprio teto, separado do dos
    marcos"), então o teto combinado é a soma dos dois. O bug 3.2 original estourava isso
    em ordens de grandeza (48 de 48 marcos num quarteirão só), não por uma unidade."""
    teto_marco = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_notaveis_max_por_quarteirao")
    teto_bairro = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_comercio_bairro_max_por_quarteirao")
    teto_combinado = teto_marco + teto_bairro
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        import collections
        por_quarteirao = collections.Counter(
            f["properties"]["quarteirao_id"] for f in geo["features"]
            if f["properties"]["camada"] == "edificio" and f["properties"]["categoria"] != "residencia")
        pior = max(por_quarteirao.values(), default=0)
        assert pior <= teto_combinado, (
            f"modelo {nome}: {pior} notáveis num único quarteirão (teto combinado {teto_combinado})")


def test_aneis_nao_cruzam():
    """G01 — docs/PLANO_CIDADE_VIVA.md Seção 1.1: em radial e organica, o raio de cada
    vértice tem que crescer estritamente por setor (nenhum anel cruza o vizinho), em
    200 seeds por combinação de modelo x tamanho. Antes de G01 a chance de cruzamento
    chegava a 82,5% (radial, 6 anéis) e 100% (organica)."""
    for nome_modelo in ("radial", "organica"):
        for tamanho in ("medio", "grande"):
            for seed_i in range(200):
                cidade = {"nome": f"TesteAneis{nome_modelo}{tamanho}{seed_i}",
                          "tamanho": tamanho, "tipo": "residencial",
                          "x_global": 100 + seed_i, "y_global": 100 + seed_i}
                sitio = SitioCidade.medir(cidade, "ContinenteTeste", CARTOGRAPHER_CONFIG)
                rng = random.Random(sitio.seed)
                modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng)
                malha = modelo.construir_malha()  # a própria asserção de G01 já falha aqui se cruzar
                assert malha.quadras


def test_nenhum_poligono_auto_intersectante():
    """G02 — Seção 1.1: o inset de quadra só rejeitava área quase zero e orientação
    invertida; um quad com vértice muito obtuso passava disso e virava gravata-borboleta
    depois do recuo. Toda feature Polygon emitida (quarteirão e lote) tem que ser simples."""
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        for f in geo["features"]:
            if f["geometry"]["type"] != "Polygon":
                continue
            anel = f["geometry"]["coordinates"][0][:-1]
            assert quad.e_quad_simples(anel) if len(anel) == 4 else True, (
                f"modelo {nome}: polígono {f['properties']['camada']} auto-intersectante")


def test_encolher_quad_rejeita_quad_concavo():
    """G02: `_encolher_quad` devolve None para um quad de entrada já auto-intersectante
    (bowtie), em vez de tentar encolher e emitir geometria inválida."""
    bowtie = [(0.0, 0.0), (40.0, 40.0), (40.0, 0.0), (0.0, 40.0)]
    assert quad.encolher_quad(bowtie, [3.0] * 4) is None


def _ponto_dentro_poligono(p, poligono):
    x, y = p
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1):
            dentro = not dentro
    return dentro


def test_quadra_dentro_da_muralha():
    """G03 — Seção 1.3: a muralha é derivada da borda real (envolver_poligono), então
    todo vértice de toda quadra tem que estar dentro do contorno, por construção — não
    por sorte. Só vale para modelo que precisa de muralha (`precisa_muralha()`)."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    for nome, cls in MODELOS.items():
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        if not modelo.precisa_muralha():
            continue
        malha = modelo.construir_malha()
        for quadra in malha.quadras:
            for vertice in quadra.vertices:
                assert _ponto_dentro_poligono(vertice, malha.contorno), (
                    f"modelo {nome}: vértice de quadra fora do contorno da muralha")


def _dist_ponto_segmento(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    comprimento2 = dx * dx + dy * dy
    if comprimento2 < 1e-12:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comprimento2))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5


def _dist_ponto_polilinha(p, pontos):
    return min(_dist_ponto_segmento(p, pontos[i], pontos[i + 1]) for i in range(len(pontos) - 1))


def test_rua_coincide_com_aresta_de_quadra():
    """G04 — Seção 1.2: rua e quadra são duas leituras da mesma grade; quem perturba a
    grade (organica) tem que perturbar as duas juntas. Para toda aresta de quadra que
    não seja 'servico' (viela de verdade, sem inset aqui) nem 'sem_via' (L02: não
    existe via nenhuma ali, por definição — não teria rua próxima mesmo), o PONTO
    MÉDIO da aresta tem que estar a menos de largura_da_classe/2 + 1.0 m (tolerância
    maior que a de produção — o objetivo aqui é provar a COERÊNCIA rua/quadra, não
    recalibrar recuo) de alguma rua.

    Só radial/organica: são os dois que compartilham a grade perturbada por G01/G04.
    `grade`/`linear` têm vocabulário próprio (ex.: linear reusa a classe 'anel' só como
    rótulo de largura pro recuo de fundo de quadra, sem rua física ali — não é o bug de
    Seção 1.2, que era especificamente radial/organica torcendo a rua sem torcer a
    quadra)."""
    larguras = cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_m_por_classe")
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    for nome in ("radial", "organica"):
        cls = MODELOS[nome]
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        malha = modelo.construir_malha()
        for quadra in malha.quadras:
            n = len(quadra.vertices)
            for k in range(n):
                classe = quadra.classes_aresta[k]
                if classe in ("servico", "sem_via"):
                    continue
                p0, p1 = quadra.vertices[k], quadra.vertices[(k + 1) % n]
                meio = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
                largura = larguras.get(classe, larguras.get("secundaria", 5.0))
                limite = largura / 2.0 + 1.0
                menor = min(
                    (_dist_ponto_polilinha(meio, rua.pontos) for rua in malha.ruas if len(rua.pontos) >= 2),
                    default=float("inf"),
                )
                assert menor <= limite, (
                    f"modelo {nome}: aresta '{classe}' da quadra {quadra.id} a {menor:.1f} m "
                    f"da rua mais próxima (limite {limite:.1f} m)")


def test_sitio_declividade_em_fora_da_janela():
    """G06 — armadilha 4: `declividade_em` devolve None pra um ponto fora da janela
    amostrada (antes: np.clip lia a célula da borda, silenciosamente), e um valor
    normal (não None) pra um ponto dentro dela — inclusive além do raio_m original,
    porque a janela agora tem margem (cidade_geo_janela_terreno_fator)."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    if sitio.terreno is None:
        return  # sem cartógrafo disponível neste ambiente — nada a checar
    fator_janela = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_janela_terreno_fator")
    raio_m = sitio.raio_janela_m / fator_janela
    assert sitio.declividade_em(raio_m * 4, 0.0) is None
    assert sitio.declividade_em(raio_m * 1.5, 0.0) is not None


def test_todo_lote_tem_frente():
    """Q01 — o invariante central do plano: para todo lote de toda quadra, a aresta de
    FRENTE (`_lotes_da_faixa` monta o polígono sempre como
    `[ext_t0, ext_t1, ins_t1, ins_t0]`, então é sempre a aresta 0-1) está CONTIDA, com
    tolerância de 0,1 m, numa aresta do quarteirão urbanizável OU numa viela aberta pra
    ele (Q01 Passo 2 — a quadra cortada não tem as duas metades como features de
    quarteirão separadas, só a viela marca o novo limite). Roda direto sobre
    `lotes.gerar_lotes_do_quarteirao`, sem depender de proximidade de rua renderizada —
    isso evita o falso-negativo de uma aresta 'servico' de G04 (anel com vão aberto, sem
    rua nenhuma por design) que uma checagem por distância-até-rua não distingue de uma
    viela de Q01 (que tem rua real)."""
    tolerancia = 0.1
    via_largura = cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_m_por_classe")
    recuo_rua = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_recuo_rua_m")

    for nome in ("radial", "organica"):
        cls = MODELOS[nome]
        sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        malha = modelo.construir_malha()

        for quadra in malha.quadras:
            distancias = [via_largura.get(c, via_largura.get("secundaria", 5.0)) / 2.0 + recuo_rua
                          for c in quadra.classes_aresta]
            quad_urbanizavel = quad.encolher_quad(quadra.vertices, distancias)
            if quad_urbanizavel is None:
                continue
            lotes_info, _, vielas, _ = lotes_mod.gerar_lotes_do_quarteirao(
                quad_urbanizavel, quadra.classes_aresta, quadra.banda, CARTOGRAPHER_CONFIG,
                modelo.lote_fator_cidade, rng)
            segmentos_validos = ([(quad_urbanizavel[k], quad_urbanizavel[(k + 1) % 4]) for k in range(4)]
                                 + list(vielas))
            for info in lotes_info:
                p0, p1 = info["poligono"][0], info["poligono"][1]
                tem_frente = any(
                    _dist_ponto_segmento(p0, a, b) < tolerancia and _dist_ponto_segmento(p1, a, b) < tolerancia
                    for a, b in segmentos_validos)
                assert tem_frente, (
                    f"modelo {nome}: lote sem frente (quadra {quadra.id}, aresta {info['aresta']}, "
                    f"indice_no_anel {info['indice_no_anel']})")


def test_ocupacao_inicial_nunca_ultrapassa_o_alvo():
    """T03/D2: edifícios/lotes nunca ULTRAPASSA a fração de ocupação inicial
    configurada — ultrapassar seria um bug real de orçamento (o orçamento é o teto).

    Não testa "dentro de 3pp" nos dois sentidos (o V01 original do plano): auditando as
    15 cidades reais, achamos que a fração de lotes com FOOTPRINT VIÁVEL (que sobra do
    recuo do edifício) varia bastante por cidade — em alguns casos bem abaixo do alvo
    configurado, por lotes geometricamente estreitos demais (pré-existente a T03, não
    causado por ele). T03 nunca inventa ocupação além do orçamento; ficar abaixo dele é
    esperado quando o terreno buildable não alcança, não uma regressão."""
    tolerancia_pp = 0.03
    for nome, cls in MODELOS.items():
        sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        gerador = GeradorCidade(modelo)
        geo = gerador.gerar()
        n_lotes = sum(1 for f in geo["features"] if f["properties"]["camada"] == "lote")
        n_edificios = sum(1 for f in geo["features"] if f["properties"]["camada"] == "edificio")
        alvo = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_ocupacao_inicial_por_tamanho")[_CIDADE_TESTE["tamanho"]]
        fracao_real = n_edificios / n_lotes if n_lotes else 0.0
        assert fracao_real <= alvo + tolerancia_pp, (
            f"modelo {nome}: ocupação {fracao_real:.2%} ultrapassa o alvo {alvo:.2%} "
            f"(+{tolerancia_pp:.0%} de tolerância)")


@pytest.mark.parametrize("nome_modelo", ["grade", "linear", "radial", "organica"])
def test_lotes_por_quadra_em_faixa(nome_modelo):
    """V01/Q01/Q03/S01 — mediana de lotes por quadra entre 4 e 30. Achado original
    (Registro de execução, Q01/Q03): `num_setores` era o mesmo em toda banda radial, e
    o arco da quadra crescia linearmente com o raio enquanto a profundidade (vão entre
    anéis) era constante — quadras de até 200-400 m de largura tangencial nas bandas
    externas. S01 (docs/PLANO_POPULACAO_E_ESCALA.md) resolveu dobrando o número de
    setores quando o arco ultrapassa a largura alvo; `radial`/`organica` deixaram de
    ser `xfail` porque passam de verdade agora."""
    geo = _gerar(MODELOS[nome_modelo])
    por_quarteirao = {}
    for f in geo["features"]:
        if f["properties"]["camada"] != "lote":
            continue
        qid = f["properties"]["quarteirao_id"]
        por_quarteirao[qid] = por_quarteirao.get(qid, 0) + 1
    assert por_quarteirao, f"modelo {nome_modelo} não gerou nenhum lote"
    mediana = statistics.median(por_quarteirao.values())
    assert 4 <= mediana <= 30, f"modelo {nome_modelo}: mediana de lotes/quadra = {mediana} (alvo 4-30)"


def test_lote_livre_nao_emite_edificio():
    """T03: lote sem atribuição (marco/comércio/residência sorteada) não vira feature
    'edificio' — fica com 'estado':'livre' na própria feature 'lote' (armadilha 2: o
    estado inicial é gravado na geometria, o banco é a verdade depois da importação)."""
    geo = _gerar()
    lotes_por_id = {f["properties"]["id"]: f for f in geo["features"] if f["properties"]["camada"] == "lote"}
    ids_edificio = {f["properties"]["id"] for f in geo["features"] if f["properties"]["camada"] == "edificio"}
    assert any(f["properties"]["estado"] == "livre" for f in lotes_por_id.values()), (
        "nenhum lote livre na cidade de teste — ajuste a fração de ocupação do teste?")
    for lote_id, feat in lotes_por_id.items():
        estado_esperado = "ocupado" if lote_id in ids_edificio else "livre"
        assert feat["properties"]["estado"] == estado_esperado


def test_determinismo():
    """T1 — gerar a mesma cidade duas vezes dá o mesmo GeoJSON, byte a byte."""
    a = _gerar()
    b = _gerar()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_praca_sem_lote_dentro():
    """T4 — nenhum centroide de lote cai dentro do polígono (aqui: círculo) da praça."""
    geo = _gerar()
    praca = next(f for f in geo["features"] if f["properties"]["camada"] == "praca")
    xs = [c[0] for c in praca["geometry"]["coordinates"][0]]
    ys = [c[1] for c in praca["geometry"]["coordinates"][0]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    raio = (max(xs) - min(xs)) / 2
    for f in geo["features"]:
        if f["properties"]["camada"] != "lote":
            continue
        coords = f["geometry"]["coordinates"][0][:-1]
        lx = sum(c[0] for c in coords) / len(coords)
        ly = sum(c[1] for c in coords) / len(coords)
        dist = ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5
        assert dist >= raio * 0.99, "lote com centroide dentro da praça"


def test_profundidade_de_lote_e_limitada_por_banda():
    """L01 (docs/PLANO_POPULACAO_E_ESCALA.md): sem pátio (quadra rasa/em cunha), o
    lote ia até o eixo médio da quadra — numa cunha isso produzia lotes de até 84 m de
    profundidade contra um alvo de ~22 m (fenelburgo_6_5_l53, 922 m²). Nenhum lote
    deve ter área muito acima da mediana da própria banda — usa `organica` (o modelo
    com as quadras mais tortas/em cunha) por banda."""
    geo = _gerar(MODELOS["organica"])
    areas_por_banda = {}
    for f in geo["features"]:
        if f["properties"]["camada"] != "lote":
            continue
        banda = f["properties"]["banda"]
        areas_por_banda.setdefault(banda, []).append(f["properties"]["area_m2"])

    for banda, areas in areas_por_banda.items():
        if len(areas) < 4:
            continue
        mediana = statistics.median(areas)
        maior = max(areas)
        assert maior <= mediana * 3.0, (
            f"organica banda {banda}: lote de {maior:.0f} m² contra mediana de {mediana:.0f} m² "
            f"(mais de 3x)")


def test_sem_lote_em_aresta_cega():
    """L02/W01 (docs/PLANO_POPULACAO_E_ESCALA.md): nenhum lote com
    `classe_frente == "sem_via"` — a aresta cega do anel aberto (`organica`) não pode
    dar frente a lote nenhum, por definição."""
    geo = _gerar(MODELOS["organica"])
    for f in geo["features"]:
        if f["properties"]["camada"] != "lote":
            continue
        assert f["properties"]["classe_frente"] != "sem_via", (
            f"lote {f['properties'].get('id')} com frente pra uma aresta sem via")


def test_id_de_lote_estavel_quando_uma_quadra_e_removida():
    """L03/V01 (docs/PLANO_POPULACAO_E_ESCALA.md): o pendente que V01 não conseguiu
    fechar — "monte uma malha, gere, remova uma quadra do meio, gere de novo, afirme
    que os ids dos lotes que sobraram não mudaram". Só é verdade agora que cada quadra
    sorteia com o próprio RNG (derivado do id do quarteirão): antes, um `self.rng`
    sequencial compartilhado fazia a contagem de lotes da quadra N depender de quantos
    sorteios as quadras 0..N-1 tinham consumido — remover uma quadra do meio deslocava
    a sequência de TODAS as quadras seguintes."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)

    def _lotes_por_quarteirao(malha_quadras):
        rng = random.Random(sitio.seed)
        modelo = MODELOS["radial"](sitio, CARTOGRAPHER_CONFIG, rng)
        gerador = GeradorCidade(modelo)
        modelo.malha = type(modelo.construir_malha())(
            ruas=[], quadras=malha_quadras, portoes=[], centro_praca=(0.0, 0.0),
            raio_praca=1.0, raio_nucleo=0.0, num_bandas=1, contorno=[])
        gerador._gerar_quarteiroes_e_lotes(modelo.malha)
        por_quarteirao = {}
        for lote in gerador._lotes:
            por_quarteirao.setdefault(gerador._quarteirao_id_str(lote.quadra.id), []).append(lote.id)
        return {qid: sorted(ids) for qid, ids in por_quarteirao.items()}

    rng_base = random.Random(sitio.seed)
    modelo_base = MODELOS["radial"](sitio, CARTOGRAPHER_CONFIG, rng_base)
    quadras_completas = modelo_base.construir_malha().quadras
    assert len(quadras_completas) >= 3, "cidade de teste pequena demais pra este teste"

    lotes_completo = _lotes_por_quarteirao(quadras_completas)

    meio = len(quadras_completas) // 2
    id_removido = quadras_completas[meio].id
    quadras_sem_meio = quadras_completas[:meio] + quadras_completas[meio + 1:]
    lotes_sem_meio = _lotes_por_quarteirao(quadras_sem_meio)

    id_removido_str = "_".join(str(p) for p in id_removido) if isinstance(id_removido, tuple) else str(id_removido)
    for quarteirao_id, ids_completo in lotes_completo.items():
        if quarteirao_id == id_removido_str:
            continue
        assert lotes_sem_meio.get(quarteirao_id) == ids_completo, (
            f"quarteirão {quarteirao_id}: ids de lote mudaram depois de remover outra "
            f"quadra ({id_removido_str}) da lista")
