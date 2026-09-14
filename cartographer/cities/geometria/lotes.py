"""
Q01 (docs/12_PLANO_CIDADE_VIVA.md) — anel perimetral + pátio: substitui a subdivisão
recursiva (cortava a quadra ao meio sem saber onde estavam as ruas — até 64% dos lotes
sem frente, mediana de 94 lotes por quadra numa quadra só).

`gerar_lotes_do_quarteirao` é uma função PURA (sem `self`, sem banco, sem GeoJSON): pega
o quad urbanizável (já com o inset da faixa de domínio aplicado por `gerador.py`) e
devolve os lotes do anel perimetral, o(s) pátio(s) e as vielas de serviço quando a
quadra é funda demais. Quem emite feature é `gerador.py`.
"""
import math

from config import cfg_get

from . import quad

# Limite de recursão pra quadra funda demais virar duas (Q01, Passo 2): sem teto, uma
# quadra patologicamente comprida cortaria pra sempre.
PROFUNDIDADE_CORTE_MAXIMA = 2

# Abaixo disto não é um lote pequeno, é ruído numérico: um corte de canto onde a aresta
# interna (pátio) é bem mais curta que a externa produz, no último passo de `t`, um
# quadrilátero quase-degenerado (dois vértices a menos de 1 mm um do outro depois do
# arredondamento pra GeoJSON) — não um terreno real. Achado auditando: um lote assim
# fazia `_footprint_edificio` (escala uniforme, que não pode introduzir auto-interseção
# sozinha) emitir um Polygon inválido, porque o LOTE de entrada já era degenerado.
AREA_MINIMA_LOTE_M2 = 4.0


def _profundidade_lote(config, banda, lote_fator_cidade):
    por_banda = cfg_get(config, "cidade_geo_lote_profundidade_m_por_banda")
    base = por_banda.get(str(banda), por_banda["_default"])
    return base * lote_fator_cidade


def _faixa_frente(config, banda):
    por_banda = cfg_get(config, "cidade_geo_lote_frente_m_faixa_por_banda")
    return por_banda.get(str(banda), por_banda["_default"])


def _lotes_da_faixa(quad_ext, k, ins, classe_frente, faixa_frente_m, rng, indice_inicial):
    """Corta a faixa trapezoidal entre a aresta `k` de `quad_ext` e `ins` em lotes,
    dividindo a aresta externa E a interna pelo MESMO parâmetro `t` (Passo 5) — é o que
    garante que os lotes tilam a faixa sem vão e sem sobreposição (interpolar por
    distância absoluta não tila, porque as duas arestas têm comprimentos diferentes)."""
    ext0, ext1 = quad_ext[k], quad_ext[(k + 1) % 4]
    ins1, ins0 = ins[(k + 1) % 4], ins[k]
    comprimento = math.dist(ext0, ext1)
    frente_alvo = rng.uniform(*faixa_frente_m)
    n_lotes = max(1, round(comprimento / frente_alvo))

    lotes = []
    idx = indice_inicial
    for m in range(n_lotes):
        t0, t1 = m / n_lotes, (m + 1) / n_lotes
        poligono = [quad.lerp(ext0, ext1, t0), quad.lerp(ext0, ext1, t1),
                    quad.lerp(ins1, ins0, 1 - t1), quad.lerp(ins1, ins0, 1 - t0)]
        area = quad.area_quad(poligono)
        if area < AREA_MINIMA_LOTE_M2:
            continue  # ruído numérico de canto, não um lote — não consome índice
        lotes.append({
            "poligono": poligono, "classe_frente": classe_frente, "aresta": k,
            "indice_no_anel": idx, "area_m2": round(area, 1),
        })
        idx += 1
    return lotes, idx


def _eixo_medio_sem_patio(quad_ext, pair, config, banda, lote_fator_cidade):
    """Sem pátio (quadra rasa demais), a 'faixa' vai até o EIXO MÉDIO da quadra em vez
    do pátio. O eixo médio liga os pontos médios das duas arestas PERPENDICULARES ao
    par escolhido — devolve um array de 4 pontos com a mesma forma de `quad_interno`,
    pra `_lotes_da_faixa` não precisar saber a diferença.

    L01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): pra uma quadra em CUNHA (fina numa ponta,
    grossa na outra), o eixo médio bruto pode ficar muito mais longe da aresta do que
    a profundidade de lote configurada — puxa cada ponto de volta em direção à aresta
    quando isso acontece. Continua PURA (sem `self`): recebe `config`/`banda`/
    `lote_fator_cidade` só pra calcular o teto, nada de estado."""
    perp = [e for e in range(4) if e not in pair]
    meios = {e: quad.lerp(quad_ext[e], quad_ext[(e + 1) % 4], 0.5) for e in perp}
    eixo = []
    for k in range(4):
        e_anterior = (k - 1) % 4
        eixo.append(meios[e_anterior] if e_anterior in meios else meios[k])

    profundidade_alvo = _profundidade_lote(config, banda, lote_fator_cidade)
    for k in range(4):
        canto = quad_ext[k]
        d = math.dist(canto, eixo[k])
        if d > profundidade_alvo:
            eixo[k] = quad.lerp(canto, eixo[k], profundidade_alvo / d)
    return eixo


def _cortar_quadra_funda(quad_ext, classes_aresta, banda, config, lote_fator_cidade, rng,
                          profundidade_corte, indice_inicial):
    """Passo 2, caso 'pátio grande demais': corta a quadra em duas pelo eixo mais longo,
    abre uma viela no corte, e recomeça o Passo 1 pra cada metade."""
    parte1, parte2, corte, i0 = quad.bisseccao_quad(quad_ext)
    # A aresta i0 (a mais longa) e sua oposta ficam cortadas ao meio; o corte novo entra
    # como a quarta aresta, classe "servico" (viela, não rua de verdade pra frente).
    classes1 = [classes_aresta[i0], classes_aresta[(i0 + 1) % 4], classes_aresta[(i0 + 2) % 4], "servico"]
    classes2 = [classes_aresta[(i0 + 2) % 4], classes_aresta[(i0 + 3) % 4], classes_aresta[i0], "servico"]

    lotes1, patios1, vielas1, prox_indice = gerar_lotes_do_quarteirao(
        parte1, classes1, banda, config, lote_fator_cidade, rng, profundidade_corte + 1, indice_inicial)
    lotes2, patios2, vielas2, indice_final = gerar_lotes_do_quarteirao(
        parte2, classes2, banda, config, lote_fator_cidade, rng, profundidade_corte + 1, prox_indice)

    return lotes1 + lotes2, patios1 + patios2, [corte] + vielas1 + vielas2, indice_final


def gerar_lotes_do_quarteirao(quad_ext, classes_aresta, banda, config, lote_fator_cidade, rng,
                               profundidade_corte=0, indice_inicial=0):
    """Devolve `(lotes, patios, vielas, indice_final)`:
    - `lotes`: lista de dicts {poligono, classe_frente, aresta, indice_no_anel, area_m2}
    - `patios`: lista de polígonos (0, 1 ou 2 — 2 só quando a quadra foi cortada)
    - `vielas`: lista de segmentos `(p0, p1)` — viram Rua tipo_via='servico' em
      gerador.py, emitidas DEPOIS de `_emitir_ruas` (a viela só existe depois da
      subdivisão de lote, mas `gerar()` não pode ser reordenado)
    - `indice_final`: próximo `indice_no_anel` livre — o índice é por QUARTEIRÃO
      (armadilha 3), não por metade, então uma quadra cortada em duas continua com uma
      sequência única de ids de lote."""
    profundidade = _profundidade_lote(config, banda, lote_fator_cidade)
    quad_interno = quad.encolher_quad(quad_ext, [profundidade] * 4)
    area_max = cfg_get(config, "cidade_geo_patio_area_maxima_m2")

    if (quad_interno is not None and quad.area_quad(quad_interno) > area_max
            and profundidade_corte < PROFUNDIDADE_CORTE_MAXIMA):
        return _cortar_quadra_funda(quad_ext, classes_aresta, banda, config, lote_fator_cidade,
                                     rng, profundidade_corte, indice_inicial)

    area_min = cfg_get(config, "cidade_geo_patio_area_minima_m2")
    if quad_interno is not None and quad.area_quad(quad_interno) < area_min:
        quad_interno = None  # quadra rasa: sem pátio, lote atravessa de lado a lado

    faixa_frente = _faixa_frente(config, banda)
    lotes = []
    idx = indice_inicial

    if quad_interno is None:
        k_longo = max(range(4), key=lambda i: math.dist(quad_ext[i], quad_ext[(i + 1) % 4]))
        pair = (k_longo, (k_longo + 2) % 4)
        eixo_medio = _eixo_medio_sem_patio(quad_ext, pair, config, banda, lote_fator_cidade)
        for k in pair:
            # L02: nenhuma faixa de lotes na aresta "sem_via" — não existe rua ali,
            # nenhum lote pode ter frente.
            if classes_aresta[k] == "sem_via":
                continue
            lotes_k, idx = _lotes_da_faixa(quad_ext, k, eixo_medio, classes_aresta[k], faixa_frente, rng, idx)
            lotes.extend(lotes_k)
        # L01: o teto de profundidade de _eixo_medio_sem_patio pode deixar um miolo
        # de verdade entre as duas faixas opostas — devolve como pátio legítimo (só
        # se a área bater o mínimo E o quadrilátero for simples; cada canto é puxado
        # de forma independente, então em quadra bem torta o miolo pode sair
        # bowtie — nesse caso é mais seguro tratar como "sem pátio" do que emitir um
        # polígono inválido, G02).
        patios = []
        if quad.e_quad_simples(eixo_medio) and quad.area_quad(eixo_medio) > area_min:
            patios = [eixo_medio]
    else:
        for k in range(4):
            # L02: nenhuma faixa de lotes na aresta "sem_via".
            if classes_aresta[k] == "sem_via":
                continue
            lotes_k, idx = _lotes_da_faixa(quad_ext, k, quad_interno, classes_aresta[k], faixa_frente, rng, idx)
            lotes.extend(lotes_k)
        patios = [quad_interno]

    return lotes, patios, [], idx


def preparar_quadra(quad_bruto, classes_aresta, banda, config, lote_fator_cidade, rng,
                     quadra_area_minima, distancia_faixa_dominio_fn, indice_inicial=0):
    """Inset pela faixa de domínio + subdivisão em lotes — o mesmo par de passos que
    `GeradorCidade._gerar_quarteiroes_e_lotes` aplica a toda quadra de uma cidade nova.
    Extraído (X02, docs/12_PLANO_CIDADE_VIVA.md) pra `cartographer/cities/expansao.py`
    reusar sem ter uma segunda implementação de subdivisão de quadra — o arrabalde não
    pode divergir da cidade original.

    Devolve `None` se a quadra encolhida for degenerada ou pequena demais (mesmo
    critério de `gerador.py`), senão `(quad_urbanizavel, lotes_info, patios, vielas,
    indice_final)`.

    L02 (docs/13_PLANO_POPULACAO_E_ESCALA.md): uma quadra com as 4 arestas "sem_via" não
    tem frente nenhuma pra lote nenhum — descartada aqui, mesmo critério de "degenerada"."""
    if all(c == "sem_via" for c in classes_aresta):
        return None
    distancias = [distancia_faixa_dominio_fn(c) for c in classes_aresta]
    quad_urbanizavel = quad.encolher_quad(quad_bruto, distancias)
    if quad_urbanizavel is None or quad.area_quad(quad_urbanizavel) < quadra_area_minima:
        return None
    lotes_info, patios, vielas, indice_final = gerar_lotes_do_quarteirao(
        quad_urbanizavel, classes_aresta, banda, config, lote_fator_cidade, rng,
        indice_inicial=indice_inicial)
    return quad_urbanizavel, lotes_info, patios, vielas, indice_final
