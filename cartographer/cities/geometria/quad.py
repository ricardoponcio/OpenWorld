"""
Geometria PURA de quadrilátero — funções de módulo, não métodos de classe (Q02,
docs/PLANO_CIDADE_VIVA.md: são utilidades soltas, ARQUITETURA.md Seção 7). Usadas por
`gerador.py` (inset de quadra, footprint de edifício) e por `distribuicao.py` — nenhuma
delas conhece `GeradorCidade`, NPC ou banco.
"""
import math


def area_sinalizada(quad):
    """Shoelace COM sinal — positivo/negativo conforme a orientação (horário vs.
    anti-horário). `area_quad` é o valor absoluto disto; usada pra detectar quad
    invertido depois do inset (`encolher_quad`)."""
    area = 0.0
    n = len(quad)
    for i in range(n):
        x1, y1 = quad[i]
        x2, y2 = quad[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def area_quad(quad):
    """Fórmula do shoelace — área de um polígono simples (aqui sempre convexo o
    bastante pra não importar orientação)."""
    return abs(area_sinalizada(quad))


def segmentos_cruzam(a, b, c, d):
    """Interseção própria de dois segmentos, por teste de orientação. Colinearidade
    conta como não-cruzamento: o caso degenerado já é pego pelo piso de área."""
    def orientacao(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    o1, o2 = orientacao(a, b, c), orientacao(a, b, d)
    o3, o4 = orientacao(c, d, a), orientacao(c, d, b)
    return o1 != o2 and o3 != o4


def e_quad_simples(quad):
    """Um quadrilátero é simples se os dois pares de arestas OPOSTAS não se cruzam
    (0-2 e 1-3). Arestas adjacentes sempre se tocam no vértice — não são cruzamento."""
    return not (segmentos_cruzam(quad[0], quad[1], quad[2], quad[3])
                or segmentos_cruzam(quad[1], quad[2], quad[3], quad[0]))


def interseccao_retas(p1, d1, p2, d2):
    """Interseção de duas retas em forma ponto + t*direção (sistema 2x2). `None` se as
    retas forem paralelas (determinante ~0) — cabe ao chamador decidir o fallback."""
    x1, y1 = p1
    dx1, dy1 = d1
    x2, y2 = p2
    dx2, dy2 = d2
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-9:
        return None
    t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom
    return (x1 + dx1 * t, y1 + dy1 * t)


def encolher_quad(quad, distancias):
    """Desloca cada aresta do quad para DENTRO por distancias[k] e reintercepta. `quad`
    tem 4 vértices em sentido consistente; `distancias[k]` é o recuo da aresta k (de
    quad[k] para quad[k+1]), em metros. Retorna o quad encolhido, ou None se ele
    degenerar (quadra estreita demais pra caber a rua, ou polígono invertido)."""
    if len(quad) != 4 or not e_quad_simples(quad):
        return None  # G02: quad de entrada já inválido (bug de modelo) morre aqui
    n = len(quad)
    cx = sum(p[0] for p in quad) / n
    cy = sum(p[1] for p in quad) / n
    orientacao_original = area_sinalizada(quad)

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
        pt = interseccao_retas(p_prev, d_prev, p_cur, d_cur)
        if pt is None:
            pt = ((p_prev[0] + p_cur[0]) / 2.0, (p_prev[1] + p_cur[1]) / 2.0)
        novo.append(pt)

    # Degeneração geométrica: um inset que "virou do avesso" (recuo maior que o quad
    # aguenta) produz um quad com orientação oposta à original, ou área ~0 — descarta em
    # vez de emitir polígono invertido. `encolher_quad` é geometria pura: o piso de área
    # específico de cada uso fica por conta do chamador.
    if area_quad(novo) < 1e-6:
        return None
    if area_sinalizada(novo) * orientacao_original <= 0:
        return None
    if not e_quad_simples(novo):
        return None  # G02: vértice muito obtuso pode manter a área/orientação e ainda
        # assim virar gravata-borboleta depois do recuo (Seção 1.1/G02).
    return novo


def subdividir_lote_recursivo(quad, area_alvo, profundidade_max, profundidade=0):
    """Corta o quadrilátero ao meio pelo lado mais longo, recursivamente, até a área
    ficar perto do alvo (a malha só produz quads, nunca formas mais complexas).

    ⚠️ Q01 (docs/PLANO_CIDADE_VIVA.md) substitui esta função pelo anel perimetral +
    pátio — ela produz até 64% dos lotes sem frente pra rua porque não sabe onde estão
    as ruas. Mantida até lá."""
    area = area_quad(quad)
    if area <= area_alvo * 1.6 or profundidade >= profundidade_max:
        return [quad]

    # Acha o lado mais longo e corta pelo meio dele e do seu oposto. Fórmula em índice
    # modular relativo a `i0` (não por posição ordenada — um `sorted([i0,i1])` aqui
    # quebra a correspondência entre m0/m1 e os vértices quando `i0` não é 0 ou 1,
    # produzindo um quad "em zigue-zague").
    n = len(quad)  # sempre 4
    comprimentos = [math.dist(quad[i], quad[(i + 1) % n]) for i in range(n)]
    i0 = comprimentos.index(max(comprimentos))

    def meio(a, b):
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

    m0 = meio(quad[i0], quad[(i0 + 1) % n])
    m1 = meio(quad[(i0 + 2) % n], quad[(i0 + 3) % n])

    parte1 = [m0, quad[(i0 + 1) % n], quad[(i0 + 2) % n], m1]
    parte2 = [m1, quad[(i0 + 3) % n], quad[i0 % n], m0]

    return (subdividir_lote_recursivo(parte1, area_alvo, profundidade_max, profundidade + 1) +
            subdividir_lote_recursivo(parte2, area_alvo, profundidade_max, profundidade + 1))
