"""
F2/F3 — distribuição dirigida de marcos + comércio de bairro (Q02, docs/
PLANO_CIDADE_VIVA.md: pacote separado por assunto). `DistribuicaoMixin` é composto em
`GeradorCidade` (gerador.py) — os métodos aqui usam `self._lotes`, `self.rng`,
`self.modelo`, `self.cfg` etc., que a classe final fornece.
"""
import collections
import math
from dataclasses import dataclass, field

from config import cfg_get
from . import quad

# G02/Q01: abaixo disto, dois vértices do footprint viram o MESMO ponto depois do
# arredondamento de 6 casas decimais em px de mundo (1 px = 15,81 km — Seção 2.1), e o
# polígono emitido fica com vértice duplicado. 0.1 m dá margem confortável acima da
# granularidade real do arredondamento (~1,6 cm) sem rejeitar footprint nenhum de
# verdade (um prédio tem metros de aresta, não centímetros).
ARESTA_MINIMA_FOOTPRINT_M = 0.1


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


class DistribuicaoMixin:
    """F2 (marcos por zona + rodízio) e F3 (comércio de bairro por densidade), e o
    encolhimento de footprint do edifício dentro do lote."""

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
        recuado = quad.encolher_quad(lote, [self.edificacao_recuo] * 4)
        if recuado is None:
            return None
        jitter = self.rng.uniform(-self.edificacao_jitter, self.edificacao_jitter)
        taxa_efetiva = min(self.edificacao_taxa_ocupacao_max, max(self.edificacao_taxa_ocupacao_min, self.edificacao_taxa_ocupacao + jitter))
        fator_linear = math.sqrt(taxa_efetiva)
        cx = sum(p[0] for p in recuado) / len(recuado)
        cy = sum(p[1] for p in recuado) / len(recuado)
        footprint = [(cx + (x - cx) * fator_linear, cy + (y - cy) * fator_linear) for x, y in recuado]
        if quad.aresta_minima(footprint) < ARESTA_MINIMA_FOOTPRINT_M:
            return None  # lote em cunha (canto de faixa trapezoidal) — recuo colapsa a ponta
        return footprint

    def _ocupacao_inicial_fracao(self) -> float:
        """D2/T03: fração de lotes ocupados no nascimento da cidade (marcos + comércio
        de bairro + residências selecionadas) — o resto fica lote livre."""
        por_tamanho = cfg_get(self.cfg, "cidade_geo_ocupacao_inicial_por_tamanho")
        return por_tamanho.get(self.tamanho, next(iter(por_tamanho.values())))

    def _distribuir_edificios(self, malha):
        """Distribuição dirigida (F2, Seção 5.2): decide primeiro QUANTOS de cada tipo a
        cidade tem e EM QUE QUADRA cada um vai (via `modelo.zona_de`/`encomendas`/
        `escolher_quadra` — não por ordem de lista, causa raiz do bug 3.2); depois roda o
        comércio de bairro (F3, densidade, teto próprio); T03 seleciona quais lotes SEM
        atribuição ainda viram Residência até o orçamento de ocupação inicial (D2) — o
        resto fica lote livre. Um edifício por lote — Polygon (footprint dentro do lote).

        Quebrado em fases (R-D05 do PLANO_REFATORACAO.md) — cada uma um método
        privado, com o estado compartilhado (`_AlocacaoDeLotes`) passado explicitamente,
        não uma closure fechando sobre uma variável definida mais abaixo no corpo."""
        self._footprints = self._precomputar_footprints()
        alocacao = self._indexar_lotes()
        self._alocar_marcos(alocacao)
        self._alocar_comercio_de_bairro(alocacao)
        residencias = self._selecionar_residencias_iniciais(alocacao)
        self._emitir_edificios(alocacao, residencias)

    def _precomputar_footprints(self) -> dict:
        """T03: calcula o footprint de cada lote UMA vez (declividade + recuo),
        cacheado por posição — `_selecionar_residencias_iniciais` precisa saber ANTES
        de sortear quais lotes conseguem construir de verdade (terreno íngreme, ou
        lote estreito demais pro recuo), senão o orçamento de ocupação (D2) fica
        sistematicamente abaixo do configurado. A fração que falha o footprint varia
        MUITO por modelo — achado auditando: `grade`, com quadra mais rasa (Q03), só
        emplaca footprint em ~50% dos lotes, contra quase 100% do `radial`; sortear a
        fração alvo sem saber disso dava 31% de ocupação real numa cidade configurada
        pra 60%."""
        footprints = {}
        self._altitudes = {}
        for pos, item in enumerate(self._lotes):
            lote = item.poligono
            cx = sum(p[0] for p in lote) / len(lote)
            cy = sum(p[1] for p in lote) / len(lote)
            self._altitudes[pos] = self.sitio.altitude_em(cx, cy)
            if self.sitio.terreno is not None:
                declividade = self.sitio.declividade_em(cx, cy)
                if declividade is None or declividade > self._declividade_max:
                    footprints[pos] = None
                    continue
            footprints[pos] = self._footprint_edificio(lote)
        return footprints

    def _indexar_lotes(self) -> _AlocacaoDeLotes:
        """T03: só indexa lotes com footprint viável (`self._footprints`, calculado
        antes desta chamada) — sem isso, marco/comércio podiam ser atribuídos a um lote
        que falha o recuo depois, e a cidade saía sistematicamente abaixo da fração de
        ocupação configurada, sem ninguém perceber (a atribuição "vingava" no
        `_AlocacaoDeLotes`, só não virava feature de verdade)."""
        quarteiroes_por_zona = collections.defaultdict(list)
        lotes_por_quarteirao = collections.defaultdict(list)
        zona_ja_vista = {}
        for pos, item in enumerate(self._lotes):
            quadra = item.quadra
            if quadra.id not in zona_ja_vista:
                zona_ja_vista[quadra.id] = self.modelo.zona_de(quadra)
                quarteiroes_por_zona[zona_ja_vista[quadra.id]].append(quadra)
            if self._footprints.get(pos) is not None:
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
        uma quitanda. Nunca reduz a fração residencial abaixo do piso configurado.

        T03: uma cidade parcialmente ocupada pede menos comércio — a quantidade de
        hoje (densidade de lotes) escala pela MESMA fração de ocupação inicial, sem
        nunca passar do teto de não-residencial nem do orçamento restante."""
        candidatos_bairro = self.modelo.catalogo_comercio_bairro()
        teto_bairro = cfg_get(self.cfg, "cidade_geo_comercio_bairro_max_por_quarteirao")
        fracao_residencial_min = cfg_get(self.cfg, "cidade_geo_fracao_residencial_min")
        n_lotes = len(self._lotes)

        vistas = set()
        todos_quarteiroes = []
        for item in self._lotes:
            quadra = item.quadra
            if quadra.id not in vistas:
                vistas.add(quadra.id)
                todos_quarteiroes.append(quadra)
        self.rng.shuffle(todos_quarteiroes)

        encomendas_bairro = []
        for entrada in candidatos_bairro:
            encomendas_bairro.extend([entrada] * (n_lotes // entrada["um_a_cada_n_lotes"]))
        self.rng.shuffle(encomendas_bairro)

        orcamento_por_ocupacao = round(len(encomendas_bairro) * self._ocupacao_inicial_fracao())
        orcamento_por_teto_nao_residencial = max(
            0, int(n_lotes * (1.0 - fracao_residencial_min)) - len(alocacao.ocupados))
        orcamento_bairro = min(orcamento_por_ocupacao, orcamento_por_teto_nao_residencial)
        if orcamento_bairro <= 0:
            return

        rodizio_bairro = collections.Counter()
        notaveis_em_bairro = collections.Counter()
        for entrada in encomendas_bairro[:orcamento_bairro]:
            quadra = self.modelo.escolher_quadra("_bairro", todos_quarteiroes, teto_bairro,
                                                  alocacao.tem_vaga, rodizio_bairro, notaveis_em_bairro)
            if quadra is None:
                continue
            livres = [p for p in alocacao.lotes_por_quarteirao[quadra.id] if p not in alocacao.ocupados]
            alocacao.ocupados[self.rng.choice(livres)] = entrada

    def _selecionar_residencias_iniciais(self, alocacao: _AlocacaoDeLotes) -> set:
        """T03: decide quais lotes SEM atribuição (marco/comércio) nascem com uma
        Residência, até o orçamento TOTAL de ocupação inicial (D2) — o resto fica lote
        livre, pro Bloco T preencher com o tempo.

        ⚠️ Não sorteia lote a lote uniformemente (`rng.sample` sobre a lista global
        produz sal-e-pimenta: casa, vazio, casa, vazio). O peso é por ZONA (núcleo
        adensa primeiro) e o ruído é por QUADRA INTEIRA (mesma quadra, mesmo ruído) —
        é o que cria bolsão cheio e bolsão vazio, como cidade real cresce. Depois
        normaliza: soma os pesos, compara com o orçamento e escala tudo por um fator
        único, pra a contagem esperada bater com o alvo configurado."""
        n_lotes = len(self._lotes)
        orcamento_total = round(n_lotes * self._ocupacao_inicial_fracao())
        orcamento_residencial = max(0, orcamento_total - len(alocacao.ocupados))
        candidatos = [pos for pos in range(n_lotes)
                     if pos not in alocacao.ocupados and self._footprints.get(pos) is not None]
        if orcamento_residencial <= 0 or not candidatos:
            return set()

        peso_por_zona = cfg_get(self.cfg, "cidade_geo_ocupacao_peso_por_zona")
        faixa_ruido = cfg_get(self.cfg, "cidade_geo_ocupacao_ruido_quadra_faixa")
        ruido_por_quadra = {}
        pesos = {}
        for pos in candidatos:
            quadra = self._lotes[pos].quadra
            if quadra.id not in ruido_por_quadra:
                ruido_por_quadra[quadra.id] = self.rng.uniform(*faixa_ruido)
            zona = self.modelo.zona_de(quadra)
            peso_zona = peso_por_zona.get(zona, 1.0)
            pesos[pos] = peso_zona * (1.0 + ruido_por_quadra[quadra.id])

        soma = sum(pesos.values())
        if soma <= 0:
            return set()
        fator = orcamento_residencial / soma
        return {pos for pos, peso in pesos.items() if self.rng.random() < peso * fator}

    def _emitir_edificios(self, alocacao: _AlocacaoDeLotes, residencias: set) -> None:
        """Passada final. Lote com atribuição (marco ou comércio de bairro) usa a
        entrada atribuída; lote selecionado por `_selecionar_residencias_iniciais` vira
        Residência; qualquer outro fica SEM edifício — lote livre (T03/D2), pronto pra
        obra da simulação ocupar depois.

        Armadilha 3 (docs/PLANO_CIDADE_VIVA.md): o edifício usa o MESMO id do lote onde
        nasce — não um contador global de emissão, que desloca `NPC.casa_id`/
        `local_trabalho_id` de todo mundo sempre que uma quadra a mais é descartada."""
        residencia_padrao = cfg_get(self.cfg, "cidade_geo_residencia_padrao")
        entrada_padrao = cfg_get(self.cfg, "cidade_geo_catalogo_entrada_padrao")

        for pos, item in enumerate(self._lotes):
            entrada = alocacao.ocupados.get(pos)
            if entrada is None and pos not in residencias:
                continue  # T03: lote livre — nem marco, nem comércio, nem residência sorteada

            quadra, lote_id = item.quadra, item.id
            footprint = self._footprints.get(pos)
            if footprint is None:
                continue  # terreno íngreme, fora da janela, ou lote estreito demais pro
                          # recuo — chão vazio (checado uma vez em _precomputar_footprints)

            if entrada is None:
                nome_tipo, categoria = "Residência", "residencia"
                capacidade, salario = residencia_padrao["capacidade"], residencia_padrao["salario_base"]
            else:
                nome_tipo = entrada["tipo_local"]
                categoria = entrada["categoria"]
                capacidade = entrada.get("capacidade", entrada_padrao["capacidade"])
                salario = entrada.get("salario_base", entrada_padrao["salario_base"])

            sufixo_lote = lote_id.rsplit("_l", 1)[-1]
            nome_completo = (f"{nome_tipo} de {self.nome}" if nome_tipo != "Residência"
                              else f"Residência {quadra.bairro} {sufixo_lote}")

            altitude_local = self._altitudes.get(pos)
            item.props["estado"] = "ocupado"  # T03: reflete na feature "lote" já emitida
            self._add_feature("Polygon", footprint + [footprint[0]], "edificio", {
                "id": lote_id,
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
