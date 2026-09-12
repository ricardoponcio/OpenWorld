"""
SCRIPT: audit_cidades.py
OBJETIVO: Auditar as cidades já geradas em `database/cidades/*.geojson` contra os
          invariantes geométricos do docs/PLANO_CIDADE_VIVA.md (V02) — uma linha por
          cidade, com os números medidos que a Seção 1 do plano usa para diagnosticar
          "cidade contorcida", "rua e quadra se sobrepondo", "casa no meio da quadra" etc.
MOMENTO DE USO: depois de cada tarefa do Bloco G ou Q (README do plano, regra de
                execução #4), e antes de qualquer commit que toque geometria de cidade —
                sai com código 1 se algum invariante estiver violado, servindo de porta.

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine, lê só arquivo GeoJSON. Não
importe este módulo de dentro de engine/, web/ ou cartographer/ — não faz parte do
runtime (ARQUITETURA.md, "é diagnóstico manual, fora do runtime").

⚠️ NUNCA leia a saída deste script com `| tail` nem `| head` — o pipe engole o código
de saída (`$?`), e já enganou uma sessão inteira (docs/PLANO_POPULACAO_E_ESCALA.md,
regra de execução #4). A saída cabe numa tela sem paginar; rode direto e confira
`echo $?` depois, se precisar do código.
"""
import os
import sys
import json
import glob
import math
import statistics
import collections

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.escala import metros_por_pixel_mundo

CIDADES_DIR = "database/cidades"

# Tolerâncias dos invariantes — violação de qualquer uma faz o script sair com código 1.
TOLERANCIA_FORA_MURO_M = 0.5
TOLERANCIA_SEM_FRENTE_PCT = 0.0


def _achatar_anel(coords):
    """Um Polygon do GeoJSON é [[ [lng,lat], ... ]] — devolve só o anel externo, sem o
    ponto de fechamento duplicado."""
    anel = coords[0]
    if anel and anel[0] == anel[-1]:
        anel = anel[:-1]
    return [tuple(p) for p in anel]


def _orientacao(p, q, r):
    v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)


def _segmentos_cruzam(a, b, c, d):
    o1, o2 = _orientacao(a, b, c), _orientacao(a, b, d)
    o3, o4 = _orientacao(c, d, a), _orientacao(c, d, b)
    return o1 != o2 and o3 != o4


def _poligono_e_simples(pontos):
    """Teste genérico (qualquer N ≥ 4): nenhum par de arestas NÃO-ADJACENTES se cruza.
    Diagnóstico independente da otimização de quadrilátero que G02 usa em produção —
    de propósito, para o auditor não herdar um bug do código que ele audita."""
    n = len(pontos)
    if n < 4:
        return True
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # arestas adjacentes sempre se tocam no vértice compartilhado
            a, b = pontos[i], pontos[(i + 1) % n]
            c, d = pontos[j], pontos[(j + 1) % n]
            if _segmentos_cruzam(a, b, c, d):
                return False
    return True


def _area_shoelace(pontos):
    n = len(pontos)
    area = 0.0
    for i in range(n):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _dist_ponto_segmento(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    comprimento2 = dx * dx + dy * dy
    if comprimento2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comprimento2))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _dist_ponto_polilinha(p, polilinha):
    return min(_dist_ponto_segmento(p, polilinha[i], polilinha[i + 1])
               for i in range(len(polilinha) - 1))


def _ponto_dentro_poligono(p, poligono):
    """Ray casting padrão — usado para checar quarteirão dentro da muralha."""
    x, y = p
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1):
            dentro = not dentro
    return dentro


def _cruzamentos_de_anel(features, centro):
    """G01: para cada setor, o raio (distância ao centro) tem que crescer estritamente
    à medida que o índice do anel cresce. Reconstrói os anéis a partir das ruas
    tipo_via="anel", na mesma ordem angular em que o modelo as emitiu."""
    aneis = {}
    for f in features:
        props = f["properties"]
        if props.get("camada") != "rua" or props.get("tipo_via") != "anel":
            continue
        aneis[props["indice"]] = _achatar_anel([f["geometry"]["coordinates"]])
    if len(aneis) < 2:
        return 0, 0
    indices_ordenados = sorted(aneis.keys())
    num_aneis = max(i for i in indices_ordenados if i >= 0)
    n_setores = len(aneis[indices_ordenados[0]])
    setores_com_cruzamento = 0
    for k in range(n_setores):
        raios = []
        for idx in indices_ordenados:
            anel = aneis[idx]
            if k >= len(anel):
                raios = None
                break
            raios.append(math.hypot(anel[k][0] - centro[0], anel[k][1] - centro[1]))
        if raios is None:
            continue
        if any(b <= a for a, b in zip(raios, raios[1:])):
            setores_com_cruzamento += 1
    return setores_com_cruzamento, num_aneis


def _pior_invasao_muralha(features):
    muralha_feats = [f for f in features if f["properties"].get("camada") == "muralha"]
    if not muralha_feats:
        return None  # cidade sem muralha — coluna não se aplica
    contorno = _achatar_anel([muralha_feats[0]["geometry"]["coordinates"]])
    pior = 0.0
    for f in features:
        if f["properties"].get("camada") != "quarteirao":
            continue
        for vertice in _achatar_anel(f["geometry"]["coordinates"]):
            if not _ponto_dentro_poligono(vertice, contorno):
                dist = _dist_ponto_polilinha(vertice, contorno + [contorno[0]])
                pior = max(pior, dist)
    return pior


def _razao_largura_profundidade(quarteiroes, metros_por_px):
    """L04 (docs/PLANO_POPULACAO_E_ESCALA.md): mediana da razão largura/profundidade
    das quadras de uma cidade — o número que denuncia a regressão de S01 (quadra
    larga demais, profundidade constante). Um quarteirão sempre tem 4 arestas na
    ordem [radial, anel, radial, anel] (gerador.py); pareia arestas OPOSTAS (0-2,
    1-3) e trata o par mais curto como profundidade — verdadeiro pros modelos radial/
    organica (o alvo de S01), e uma aproximação razoável pra grade/linear."""
    razoes = []
    for f in quarteiroes:
        pontos = _achatar_anel(f["geometry"]["coordinates"])
        if len(pontos) != 4:
            continue
        arestas = [math.dist(pontos[k], pontos[(k + 1) % 4]) * metros_por_px for k in range(4)]
        par_a = (arestas[0] + arestas[2]) / 2.0
        par_b = (arestas[1] + arestas[3]) / 2.0
        profundidade, largura = min(par_a, par_b), max(par_a, par_b)
        if profundidade > 1e-6:
            razoes.append(largura / profundidade)
    return statistics.median(razoes) if razoes else None


def _densidade_lotes_por_raio2(num_lotes, raio_m):
    if not raio_m:
        return None
    return num_lotes / (raio_m ** 2)


def _percentual_sem_frente(features, metros_por_px, limite_m=25.0):
    ruas = [_achatar_anel([f["geometry"]["coordinates"]]) + [_achatar_anel([f["geometry"]["coordinates"]])[0]]
            for f in features if f["properties"].get("camada") == "rua"]
    lotes = [f for f in features if f["properties"].get("camada") == "lote"]
    if not lotes or not ruas:
        return 0.0
    limite_px = limite_m / metros_por_px
    sem_frente = 0
    for lote in lotes:
        pontos = _achatar_anel(lote["geometry"]["coordinates"])
        cx = sum(p[0] for p in pontos) / len(pontos)
        cy = sum(p[1] for p in pontos) / len(pontos)
        menor = min(_dist_ponto_polilinha((cx, cy), rua) for rua in ruas)
        if menor > limite_px:
            sem_frente += 1
    return 100.0 * sem_frente / len(lotes)


def auditar_cidade(caminho, metros_por_px):
    with open(caminho, "r", encoding="utf-8") as f:
        geo = json.load(f)
    features = geo["features"]
    props_topo = geo.get("properties", {})
    centro = (props_topo.get("x_global", 0.0), -props_topo.get("y_global", 0.0))

    quarteiroes = [f for f in features if f["properties"].get("camada") == "quarteirao"]
    lotes = [f for f in features if f["properties"].get("camada") == "lote"]
    edificios = [f for f in features if f["properties"].get("camada") == "edificio"]

    bowtie_quarteirao = sum(1 for f in quarteiroes if not _poligono_e_simples(_achatar_anel(f["geometry"]["coordinates"])))
    bowtie_lote = sum(1 for f in lotes if not _poligono_e_simples(_achatar_anel(f["geometry"]["coordinates"])))
    setores_cruzados, num_aneis = _cruzamentos_de_anel(features, centro)

    lotes_por_quadra = collections.Counter(f["properties"].get("quarteirao_id") for f in lotes)
    contagens = list(lotes_por_quadra.values()) or [0]

    areas_lote_m2 = [_area_shoelace(_achatar_anel(f["geometry"]["coordinates"])) * metros_por_px ** 2
                     for f in lotes]

    pior_invasao = _pior_invasao_muralha(features)
    sem_frente_pct = _percentual_sem_frente(features, metros_por_px)

    raio_m = props_topo.get("raio_m", 0.0)
    vao_m = raio_m / (num_aneis + 1) if num_aneis > 0 else None

    return {
        "cidade": props_topo.get("cidade", os.path.basename(caminho)),
        "modelo": props_topo.get("modelo", "?"),
        "aneis": num_aneis,
        "vao_m": vao_m,
        "quadras": len(lotes_por_quadra),
        "lotes": len(lotes),
        "ocupacao_pct": 100.0 * len(edificios) / len(lotes) if lotes else 0.0,
        "bowtie_quarteirao": bowtie_quarteirao,
        "bowtie_lote": bowtie_lote,
        "cruzamentos_anel": setores_cruzados,
        "l_quadra_mediana": statistics.median(contagens),
        "l_quadra_max": max(contagens),
        "sem_frente_pct": sem_frente_pct,
        "fora_muro_m": pior_invasao,
        "area_lote_mediana_m2": statistics.median(areas_lote_m2) if areas_lote_m2 else 0.0,
        # L04: largura/profundidade denuncia a regressão de S01; lotes/raio² é a
        # constante de densidade que R02 vai calibrar por modelo.
        "largura_profundidade": _razao_largura_profundidade(quarteiroes, metros_por_px),
        "lotes_por_raio2": _densidade_lotes_por_raio2(len(lotes), raio_m),
    }


# L04: mediana de lotes por quadra fora de [4, 30] é violação dura, mesmo critério que
# bowtie/anel/muro/frente — S01 (docs/PLANO_POPULACAO_E_ESCALA.md) existe pra manter a
# quadra "quase quadrada" dentro dessa faixa.
LOTES_POR_QUADRA_MEDIANA_MIN = 4
LOTES_POR_QUADRA_MEDIANA_MAX = 30


def _viola_invariantes(linha):
    if linha["bowtie_quarteirao"] > 0 or linha["bowtie_lote"] > 0:
        return True
    if linha["cruzamentos_anel"] > 0:
        return True
    if linha["fora_muro_m"] is not None and linha["fora_muro_m"] > TOLERANCIA_FORA_MURO_M:
        return True
    if linha["sem_frente_pct"] > TOLERANCIA_SEM_FRENTE_PCT:
        return True
    mediana = linha["l_quadra_mediana"]
    if not (LOTES_POR_QUADRA_MEDIANA_MIN <= mediana <= LOTES_POR_QUADRA_MEDIANA_MAX):
        return True
    return False


def _fmt(valor, casas=0):
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:.{casas}f}"
    return str(valor)


def main():
    metros_por_px = metros_por_pixel_mundo(CARTOGRAPHER_CONFIG)
    caminhos = sorted(glob.glob(os.path.join(CIDADES_DIR, "*.geojson")))
    if not caminhos:
        print(f"❌ Nenhuma cidade encontrada em {CIDADES_DIR}. Rode generate_city_geometry.py antes.")
        sys.exit(1)

    cabecalho = (f"{'cidade':<22} {'modelo':<10} {'aneis':>5} {'vao_m':>6} {'quadras':>7} "
                 f"{'lotes':>6} {'ocup%':>6} {'bowtie_q':>8} {'bowtie_l':>8} {'anel_x':>6} "
                 f"{'l/quadra':>9} {'max/qd':>7} {'sem_front%':>10} {'fora_muro':>9} "
                 f"{'area_med_m2':>11} {'larg/prof':>9} {'lotes/raio2':>11}")
    print(cabecalho)
    print("-" * len(cabecalho))

    algum_violado = False
    for caminho in caminhos:
        linha = auditar_cidade(caminho, metros_por_px)
        if _viola_invariantes(linha):
            algum_violado = True
        print(f"{linha['cidade']:<22} {linha['modelo']:<10} {_fmt(linha['aneis']):>5} "
              f"{_fmt(linha['vao_m']):>6} {_fmt(linha['quadras']):>7} {_fmt(linha['lotes']):>6} "
              f"{_fmt(linha['ocupacao_pct'], 0):>6} {_fmt(linha['bowtie_quarteirao']):>8} "
              f"{_fmt(linha['bowtie_lote']):>8} {_fmt(linha['cruzamentos_anel']):>6} "
              f"{_fmt(linha['l_quadra_mediana'], 1):>9} {_fmt(linha['l_quadra_max']):>7} "
              f"{_fmt(linha['sem_frente_pct'], 1):>10} "
              f"{_fmt(linha['fora_muro_m'], 1) if linha['fora_muro_m'] is not None else '-':>9} "
              f"{_fmt(linha['area_lote_mediana_m2'], 1):>11} "
              f"{_fmt(linha['largura_profundidade'], 2):>9} "
              f"{_fmt(linha['lotes_por_raio2'], 4):>11}")

    if algum_violado:
        print("\n❌ Um ou mais invariantes violados (bowtie, anéis cruzados, muro, lote sem "
              f"frente, ou mediana de lotes/quadra fora de [{LOTES_POR_QUADRA_MEDIANA_MIN}, "
              f"{LOTES_POR_QUADRA_MEDIANA_MAX}]).")
        sys.exit(1)
    print("\n✅ Nenhum invariante violado nas cidades auditadas.")


if __name__ == "__main__":
    main()
