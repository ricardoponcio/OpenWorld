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

    def _area_alvo_lote(self, banda):
        """E2 (Seção 5.2): alvo de área do lote cresce com a banda (centro denso, borda
        folgada) e leva o fator por cidade que o MODELO sorteou (`lote_fator_cidade`),
        pra duas cidades do mesmo tamanho não serem idênticas."""
        return self.lote_area_base * (self.lote_fator_por_banda ** (banda - 1)) * self.modelo.lote_fator_cidade

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
        return [(cx + (x - cx) * fator_linear, cy + (y - cy) * fator_linear) for x, y in recuado]

    def _distribuir_edificios(self, malha):
        """Distribuição dirigida (F2, Seção 5.2): decide primeiro QUANTOS de cada tipo a
        cidade tem e EM QUE QUADRA cada um vai (via `modelo.zona_de`/`encomendas`/
        `escolher_quadra` — não por ordem de lista, causa raiz do bug 3.2); depois roda o
        comércio de bairro (F3, densidade, teto próprio); só então preenche o resto com
        Residência. Um edifício por lote — Polygon (footprint dentro do lote).

        Quebrado em 4 fases (R-D05 do PLANO_REFATORACAO.md) — cada uma um método
        privado, com o estado compartilhado (`_AlocacaoDeLotes`) passado explicitamente,
        não uma closure fechando sobre uma variável definida mais abaixo no corpo."""
        alocacao = self._indexar_lotes()
        self._alocar_marcos(alocacao)
        self._alocar_comercio_de_bairro(alocacao)
        self._emitir_edificios(alocacao)

    def _indexar_lotes(self) -> _AlocacaoDeLotes:
        quarteiroes_por_zona = collections.defaultdict(list)
        lotes_por_quarteirao = collections.defaultdict(list)
        zona_ja_vista = {}
        for pos, (lote, quadra) in enumerate(self._lotes):
            if quadra.id not in zona_ja_vista:
                zona_ja_vista[quadra.id] = self.modelo.zona_de(quadra)
                quarteiroes_por_zona[zona_ja_vista[quadra.id]].append(quadra)
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
        uma quitanda. Nunca reduz a fração residencial abaixo do piso configurado."""
        candidatos_bairro = self.modelo.catalogo_comercio_bairro()
        teto_bairro = cfg_get(self.cfg, "cidade_geo_comercio_bairro_max_por_quarteirao")
        fracao_residencial_min = cfg_get(self.cfg, "cidade_geo_fracao_residencial_min")
        n_lotes = len(self._lotes)
        orcamento_bairro = max(0, int(n_lotes * (1.0 - fracao_residencial_min)) - len(alocacao.ocupados))
        if orcamento_bairro <= 0:
            return

        vistas = set()
        todos_quarteiroes = []
        for _, quadra in self._lotes:
            if quadra.id not in vistas:
                vistas.add(quadra.id)
                todos_quarteiroes.append(quadra)
        self.rng.shuffle(todos_quarteiroes)

        encomendas_bairro = []
        for entrada in candidatos_bairro:
            encomendas_bairro.extend([entrada] * (n_lotes // entrada["um_a_cada_n_lotes"]))
        self.rng.shuffle(encomendas_bairro)

        rodizio_bairro = collections.Counter()
        notaveis_em_bairro = collections.Counter()
        for entrada in encomendas_bairro[:orcamento_bairro]:
            quadra = self.modelo.escolher_quadra("_bairro", todos_quarteiroes, teto_bairro,
                                                  alocacao.tem_vaga, rodizio_bairro, notaveis_em_bairro)
            if quadra is None:
                continue
            livres = [p for p in alocacao.lotes_por_quarteirao[quadra.id] if p not in alocacao.ocupados]
            alocacao.ocupados[self.rng.choice(livres)] = entrada

    def _emitir_edificios(self, alocacao: _AlocacaoDeLotes) -> None:
        """Passada final: o resto. Lote com atribuição (marco ou comércio de bairro) usa
        a entrada atribuída; lote sem atribuição vira Residência."""
        residencia_padrao = cfg_get(self.cfg, "cidade_geo_residencia_padrao")
        entrada_padrao = cfg_get(self.cfg, "cidade_geo_catalogo_entrada_padrao")
        idx_edificio = 0

        for pos, (lote, quadra) in enumerate(self._lotes):
            cx = sum(p[0] for p in lote) / len(lote)
            cy = sum(p[1] for p in lote) / len(lote)

            if self.sitio.terreno is not None:
                # G06: None (ponto fora da janela de terreno amostrada) é tratado como
                # "não sei, rejeite o lote" — nunca como 0/plano. Não deveria acontecer
                # aqui (todo lote está dentro de raio_m, bem dentro da janela ampliada),
                # mas se acontecer é sinal de bug, não motivo pra construir às cegas.
                declividade = self.sitio.declividade_em(cx, cy)
                if declividade is None or declividade > self._declividade_max:
                    continue  # lote íngreme demais (ou fora da janela) — chão vazio

            footprint = self._footprint_edificio(lote)
            if footprint is None:
                continue  # lote estreito demais pro recuo — idem

            entrada = alocacao.ocupados.get(pos)
            if entrada is None:
                nome_tipo, categoria = "Residência", "residencia"
                capacidade, salario = residencia_padrao["capacidade"], residencia_padrao["salario_base"]
            else:
                nome_tipo = entrada["tipo_local"]
                categoria = entrada["categoria"]
                capacidade = entrada.get("capacidade", entrada_padrao["capacidade"])
                salario = entrada.get("salario_base", entrada_padrao["salario_base"])

            idx_edificio += 1
            slug_id = f"{self.nome.lower().replace(' ', '_')}_{idx_edificio:03d}"
            nome_completo = (f"{nome_tipo} de {self.nome}" if nome_tipo != "Residência"
                              else f"Residência {idx_edificio:03d} — {quadra.bairro}")

            altitude_local = self.sitio.altitude_em(cx, cy)
            self._add_feature("Polygon", footprint + [footprint[0]], "edificio", {
                "id": slug_id,
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
