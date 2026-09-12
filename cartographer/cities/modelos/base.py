"""
A interface de modelo de cidade (ESPEC_DESENHO_CIDADE.md F4.3/F4.4). `Rua`/`Quadra`/`Malha`
são o que um modelo devolve; `ModeloCidade` são os sete ganchos que todo modelo responde —
a base resolve os seis genéricos de um jeito razoável, e cada modelo sobrescreve só os que
fazem sentido pra ele. `construir_malha` é o único obrigatório.

O que NÃO é gancho, e mora em `GeradorCidade` (generate_city_geometry.py), não aqui nem em
modelo nenhum: inset de quadra, subdivisão em lotes, footprint, emissão de feature, índice,
conversão de coordenada. Se um modelo precisar de qualquer um desses, é sinal de que ele
está reimplementando trabalho que já é compartilhado (Seção 5.5).
"""
import math
from dataclasses import dataclass, field

import numpy as np

from config import cfg_get


def pontos_ao_longo_do_poligono(poligono, espacamento):
    """Pontos igualmente espaçados ao longo do perímetro de um polígono fechado —
    utilitário de geometria pura, reusado por modelos que colocam torres numa muralha
    não-circular (F5+: `grade`/`bastida`). `poligono` não repete o primeiro ponto no fim."""
    n = len(poligono)
    perimetro = sum(math.dist(poligono[i], poligono[(i + 1) % n]) for i in range(n))
    if perimetro <= 0:
        return []
    num_pontos = max(4, int(perimetro / max(1.0, espacamento)))
    pontos = []
    for k in range(num_pontos):
        alvo = perimetro * k / num_pontos
        acumulado = 0.0
        for i in range(n):
            p0, p1 = poligono[i], poligono[(i + 1) % n]
            comprimento = math.dist(p0, p1)
            if acumulado + comprimento >= alvo:
                t = (alvo - acumulado) / comprimento if comprimento > 0 else 0.0
                pontos.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
                break
            acumulado += comprimento
        else:
            pontos.append(poligono[0])
    return pontos


def distancia_faixa_dominio(config, classe):
    """Meia-largura da via + recuo — a distância que `quad.encolher_quad` insere entre o
    quarteirão bruto e a faixa de domínio da rua. Era duplicado, idêntico, em
    `gerador.py` e em `linear.py`; extraído aqui pra `cartographer/cities/expansao.py`
    (X02, docs/PLANO_CIDADE_VIVA.md) ter a mesma conta sem copiar de novo."""
    largura_por_classe = cfg_get(config, "cidade_via_largura_m_por_classe")
    largura = largura_por_classe.get(classe, largura_por_classe.get("secundaria", 5.0))
    return largura / 2.0 + cfg_get(config, "cidade_geo_recuo_rua_m")


def gerar_fileiras_de_quadras(eixo_pontos, profundidade_m, comprimento_celula_m, classe_frente,
                               classe_fundo, classe_lateral, banda, bairro, id_prefix):
    """Dada uma polilinha de eixo (mão única, sem repetir o primeiro ponto no fim),
    produz UMA fileira de quadras retangulares de cada lado, cortada a cada
    ~`comprimento_celula_m` ao longo do eixo, e as ruas transversais nos cortes
    intermediários — a estrutura de `LinearModelo` (F6) com uma única fileira (`k=1`),
    extraída pra ser reusada por `cartographer/cities/expansao.py` (X02, docs/
    PLANO_CIDADE_VIVA.md): o arrabalde é exatamente "casas dos dois lados de uma rua",
    fora do muro.

    `id_prefix` é uma tupla; o id de cada quadra é `id_prefix + (segmento, corte, lado)`.
    Devolve `(quadras, ruas_transversais)` — nenhum dos dois é emitido feature aqui
    (quem emite é `GeradorCidade`/`expansao.py`, cada um com seu próprio slug/zoom)."""
    quadras = []
    ruas_transversais = []
    n_segmentos = len(eixo_pontos) - 1
    corte_global = 0
    for i in range(n_segmentos):
        p0, p1 = eixo_pontos[i], eixo_pontos[i + 1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        comprimento = math.hypot(dx, dy)
        if comprimento <= 0:
            continue
        nx, ny = -dy / comprimento, dx / comprimento
        n_celulas = max(1, round(comprimento / comprimento_celula_m))
        for c in range(n_celulas):
            t0, t1 = c / n_celulas, (c + 1) / n_celulas
            q0 = (p0[0] + dx * t0, p0[1] + dy * t0)
            q1 = (p0[0] + dx * t1, p0[1] + dy * t1)
            for lado in (1, -1):
                v2 = (q1[0] + lado * nx * profundidade_m, q1[1] + lado * ny * profundidade_m)
                v3 = (q0[0] + lado * nx * profundidade_m, q0[1] + lado * ny * profundidade_m)
                classes_aresta = [classe_frente, classe_lateral, classe_fundo, classe_lateral]
                quadras.append(Quadra(vertices=[q0, q1, v2, v3], classes_aresta=classes_aresta,
                                       banda=banda, bairro=bairro,
                                       id=id_prefix + (i, c, lado)))
            ultimo_corte_do_eixo = (i == n_segmentos - 1 and c == n_celulas - 1)
            if not ultimo_corte_do_eixo:
                transversal = [(q1[0] + lado_ * nx * profundidade_m, q1[1] + lado_ * ny * profundidade_m)
                               for lado_ in (1, -1)]
                ruas_transversais.append(Rua(pontos=transversal, classe_via=classe_lateral,
                                              tipo_via="transversal", indice=corte_global))
                corte_global += 1
    return quadras, ruas_transversais


def envolver_poligono(poligono, folga):
    """Infla um polígono radialmente em torno do próprio centroide, garantindo que todo
    vértice original fique DENTRO do resultado com ao menos `folga` de sobra. Usado pela
    muralha: ela tem que envolver a cidade por construção, não por sorte (Seção 1.3 do
    docs/PLANO_CIDADE_VIVA.md).

    `folga` aceita um único float (mesma folga em todo vértice) ou uma sequência do
    mesmo tamanho de `poligono` (folga por vértice — variação orgânica na muralha só
    pode SOMAR folga, nunca subtrair, senão ela deixa de envolver por construção)."""
    cx = sum(p[0] for p in poligono) / len(poligono)
    cy = sum(p[1] for p in poligono) / len(poligono)
    folgas = folga if hasattr(folga, "__len__") else [folga] * len(poligono)
    envolvido = []
    for (x, y), f in zip(poligono, folgas):
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy) or 1.0
        envolvido.append((cx + dx * (d + f) / d, cy + dy * (d + f) / d))
    return envolvido


@dataclass
class Rua:
    pontos: list          # [(x_m, y_m), ...] em metros locais
    classe_via: str        # "principal" | "anel" | "secundaria" — cidade_via_largura_m_por_classe
    tipo_via: str           # papel geométrico: "anel" | "radial" | "eixo" | "transversal" | "servico"
    indice: int


@dataclass
class Quadra:
    vertices: list          # EXATAMENTE 4 vértices
    classes_aresta: list     # 4 strings — a classe_via da rua sobre a aresta k
    banda: int               # 0 = núcleo ... num_bandas-1 = borda. Alimenta _area_alvo_lote
    bairro: str
    id: object               # identificador estável do quarteirão (hashable)
    extra: dict = field(default_factory=dict)  # espaço do modelo (ex.: {"fileira": 2})


@dataclass
class Malha:
    ruas: list
    quadras: list
    portoes: list
    centro_praca: tuple
    raio_praca: float
    raio_nucleo: float
    num_bandas: int
    contorno: list          # polígono do limite/muralha da cidade, em metros
    torres: list = field(default_factory=list)  # pontos (x_m, y_m) das torres, se houver muralha


class ModeloCidade:
    """Sete perguntas; a base responde todas de um jeito razoável (menos a 1, obrigatória),
    e cada modelo sobrescreve só as que fazem sentido pra ele (Seção 4.3/5.5)."""
    nome = "base"

    def __init__(self, sitio, config, rng):
        self.sitio = sitio
        self.cfg = config
        self.rng = rng
        self.np_rng = np.random.default_rng(sitio.seed)
        self.malha = None  # setado por GeradorCidade logo depois de construir_malha()
        # Defaults pra um modelo mínimo (só `construir_malha`) já dar uma cidade completa
        # (F4.7/9.2.5) — `radial.py` sobrescreve os dois com valores sorteados do próprio
        # rng, em ordem específica (ver o comentário de determinismo em radial.py).
        self.raio_m = 500.0
        self.lote_fator_cidade = 1.0
        # F5.2/Seção 10 item 10: ajustar_por_sitio roda ANTES de construir_malha, mas
        # DEPOIS de rng/np_rng existirem — e não pode consumir self.rng (desloca a
        # sequência inteira pra todas as cidades). Ele só lê o sítio e ajusta parâmetros.
        self.ajustar_por_sitio()

    # --- gancho 0 -----------------------------------------------------------------
    def ajustar_por_sitio(self):
        """Calibra parâmetros do modelo com clima/bioma do sítio. Base: no-op.
        ⚠️ Nunca consuma self.rng aqui (Seção 10 item 10)."""
        pass

    # --- gancho 1 (obrigatório) -----------------------------------------------------
    def construir_malha(self) -> Malha:
        raise NotImplementedError(f"{type(self).__name__} precisa implementar construir_malha()")

    # --- gancho 2 -------------------------------------------------------------------
    def zona_de(self, quadra: Quadra) -> str:
        """nucleo (banda 0) | centro (banda 1) | meio (bandas intermediárias) | borda
        (última banda). Cidade pequena com poucos anéis pode não ter banda "meio"
        nenhuma — normal, `GeradorCidade._zona_de_fallback` resolve isso."""
        num_bandas = self.malha.num_bandas if self.malha is not None else quadra.banda + 1
        if quadra.banda == 0:
            return "nucleo"
        if quadra.banda == 1:
            return "centro"
        if quadra.banda == num_bandas - 1:
            return "borda"
        return "meio"

    # --- gancho 3 -------------------------------------------------------------------
    def encomendas(self):
        """Quantidade de cada tipo do catálogo de MARCOS que esta cidade tem — min
        garantido, mais extras até o max com probabilidade proporcional ao peso efetivo
        (F2.3). Devolve [(entrada, zona), ...] já embaralhada."""
        candidatos = self._candidatos_catalogo()
        zona_por_categoria = cfg_get(self.cfg, "cidade_geo_zona_por_categoria")
        # Normaliza pelo peso BRUTO (sem o bônus/penalidade de tipos_cidade) — ver o log
        # de execução do F2 pra explicação de por que não é o peso EFETIVO.
        peso_max = max((e["peso"] for e in candidatos), default=1.0)
        encomendas = []
        for entrada in candidatos:
            n = entrada.get("min", 0)
            maximo = entrada.get("max", 99)
            while n < maximo and self.rng.random() < self._peso_efetivo(entrada) / peso_max:
                n += 1
            zona = entrada.get("zona") or zona_por_categoria.get(entrada["categoria"], "meio")
            for _ in range(n):
                encomendas.append((entrada, zona))
        self.rng.shuffle(encomendas)
        return encomendas

    def _candidatos_catalogo(self):
        catalogo = cfg_get(self.cfg, "cidade_geo_catalogo_edificios")
        return [e for e in catalogo if not e.get("tamanhos") or self.sitio.tamanho in e["tamanhos"]]

    def _peso_efetivo(self, entrada):
        tipos_cidade = entrada.get("tipos_cidade") or []
        if self.sitio.tipo in tipos_cidade:
            return entrada["peso"] * 3.0
        if not tipos_cidade:
            return entrada["peso"]
        return entrada["peso"] * 0.25

    # --- gancho 4 -------------------------------------------------------------------
    def catalogo_comercio_bairro(self):
        """Lista de densidade (F3.1) — sem min/max/tipos_cidade."""
        return cfg_get(self.cfg, "cidade_geo_catalogo_comercio_bairro")

    # --- gancho 5 -------------------------------------------------------------------
    def escolher_quadra(self, zona, candidatas, teto, tem_vaga, rodizio_idx, notaveis_em):
        """Rodízio sobre `candidatas` (já filtradas por zona), com teto de notáveis por
        quadra — a causa raiz do bug 3.2 (todos os notáveis caindo no mesmo quarteirão)
        era escolher por ordem de lista, não por rodízio. `tem_vaga(quadra)` diz se ainda
        há lote livre ali (GeradorCidade é quem sabe disso, não o modelo).

        `rodizio_idx`/`notaveis_em` (Counter) são passados pelo chamador — cada passada
        de distribuição (marcos, comércio de bairro) usa o seu próprio par, com teto
        independente (F3.2: "com o seu próprio teto, separado do dos marcos")."""
        if not candidatas:
            return None
        idx = rodizio_idx[zona]
        n = len(candidatas)
        for passo in range(n):
            quadra = candidatas[(idx + passo) % n]
            if notaveis_em[quadra.id] < teto and tem_vaga(quadra):
                rodizio_idx[zona] = idx + passo + 1
                notaveis_em[quadra.id] += 1
                return quadra
        rodizio_idx[zona] = idx + n
        return None

    # --- gancho 6 -------------------------------------------------------------------
    def precisa_muralha(self):
        tamanhos_com_muralha = cfg_get(self.cfg, "cidade_geo_muralha_tamanhos")
        return self.sitio.tamanho in tamanhos_com_muralha or self.sitio.tipo == "fortaleza"
