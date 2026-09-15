"""
MODULE: sobreposicao.py
FUNÇÃO: Área de interseção entre polígonos convexos — a métrica que falta pro
    invariante "quadras/lotes/edifícios não se sobrepõem" (G01, docs/
    16_PLANO_PAINEL_E_IA.md).

DESCRIÇÃO:
    `builder/fix/audit_cidades.py` não media sobreposição nenhuma; a primeira
    tentativa óbvia (cruzamento de arestas) conta borda encostando como
    sobreposição (Armadilha 21) — dois quadrados vizinhos, lado a lado sem
    nenhuma área em comum, têm arestas coincidentes, e um teste de cruzamento
    "pega" isso como falso positivo. Área de interseção é a métrica certa: zero
    quando só encostam, positiva só quando as áreas realmente se sobrepõem.

    ⚠️ Sutherland–Hodgman é EXATO quando o polígono de RECORTE é convexo.
    Quadras, lotes e edifícios deste projeto são quadriláteros (contrato de
    `Quadra.vertices`: exatamente 4) e o gerador já rejeita quad côncavo
    (`test_encolher_quad_rejeita_quad_concavo`, `cartographer/cities/geometria/
    quad.py`), então vale. Se um dia houver polígono côncavo aqui, esta função
    SUBESTIMA a área (corta como se a "reentrância" não existisse).

    As coordenadas de entrada devem já estar na unidade em que a área importa
    (metros) — o chamador converte de pixel de mundo ANTES de chamar
    (`cartographer.cities.escala.metros_por_pixel_mundo`); nada aqui sabe o que
    é pixel de mundo.
"""


def area_poligono(pontos) -> float:
    """Fórmula do laço (shoelace), valor absoluto — funciona em qualquer
    orientação (horário ou anti-horário)."""
    n = len(pontos)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _area_assinada(pontos) -> float:
    n = len(pontos)
    total = 0.0
    for i in range(n):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total


def _garantir_anti_horario(pontos: list) -> list:
    """Sutherland–Hodgman precisa saber de que lado de cada aresta do recorte
    fica "dentro" — normaliza pra anti-horário (área assinada positiva) em vez
    de assumir que quem chamou já orientou certo."""
    return pontos if _area_assinada(pontos) > 0 else list(reversed(pontos))


def _lado(a, b, p) -> float:
    """> 0 se `p` está à esquerda do segmento a->b (== "dentro", já que o
    recorte foi normalizado pra anti-horário)."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _intersecao(p1, p2, a, b):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = a
    x4, y4 = b
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return p2  # segmentos quase paralelos — não deveria acontecer no uso normal
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def recortar_convexo(sujeito: list, recorte: list) -> list:
    """Sutherland–Hodgman: recorta `sujeito` (qualquer polígono simples) pelo
    polígono CONVEXO `recorte`. Devolve os vértices do polígono resultante —
    pode vir vazio (sem interseção) ou com menos de 3 pontos (interseção
    degenerada, área zero)."""
    saida = list(sujeito)
    recorte = _garantir_anti_horario(list(recorte))
    n = len(recorte)
    for i in range(n):
        if not saida:
            break
        a, b = recorte[i], recorte[(i + 1) % n]
        entrada, saida = saida, []
        for j in range(len(entrada)):
            atual = entrada[j]
            anterior = entrada[j - 1]
            lado_atual = _lado(a, b, atual)
            lado_anterior = _lado(a, b, anterior)
            if lado_atual >= 0:
                if lado_anterior < 0:
                    saida.append(_intersecao(anterior, atual, a, b))
                saida.append(atual)
            elif lado_anterior >= 0:
                saida.append(_intersecao(anterior, atual, a, b))
    return saida


def area_de_intersecao(a: list, b: list) -> float:
    """`area_poligono(recortar_convexo(a, b))` — 0.0 se o recorte tiver menos
    de 3 pontos (sem área, ou só um ponto/segmento de contato)."""
    resultado = recortar_convexo(a, b)
    if len(resultado) < 3:
        return 0.0
    return area_poligono(resultado)


def _bbox(pontos):
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    return (min(xs), min(ys), max(xs), max(ys))


def _bboxes_se_tocam(b1, b2) -> bool:
    return not (b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1])


def pares_sobrepostos(poligonos: list, area_minima_m2: float) -> list:
    """Todos os pares `(i, j, area)` de `poligonos` cuja interseção tem área
    `>= area_minima_m2` — pré-filtra por bbox (descarta pares cujas caixas nem
    se tocam) antes de pagar o custo do recorte."""
    bboxes = [_bbox(p) for p in poligonos]
    resultado = []
    n = len(poligonos)
    for i in range(n):
        for j in range(i + 1, n):
            if not _bboxes_se_tocam(bboxes[i], bboxes[j]):
                continue
            area = area_de_intersecao(poligonos[i], poligonos[j])
            if area >= area_minima_m2:
                resultado.append((i, j, area))
    return resultado
