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
