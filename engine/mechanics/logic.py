"""
MODULE: logic.py
FUNÇÃO: Cérebro de decisão do NPC (Utility AI).

DESCRIÇÃO:
    `NPCBrain` não conhece a regra de nenhuma ação — ele só soma o que cada
    `AvaliadorDeUtilidade` (um por `Acao`, em `engine/mechanics/utilidade/`) devolve, e
    escolhe o máximo. Isso substitui o `calcular_utilidade` de 144 linhas que existia
    antes: 7 blocos de responsabilidades independentes misturados num corpo só (R-D01).

    `config` é o config.json completo (não só o bloco "ia_decisao") — os avaliadores de
    Comer e Construir também precisam de "acoes"/outros blocos.
"""
from typing import Dict, List, Optional
from ..models import Acao, NPC
from ..logger import WorldLogger
from .utilidade import (
    ContextoDecisao,
    AvaliadorComer, AvaliadorDormir, AvaliadorTrabalhar, AvaliadorSocializar,
    AvaliadorCuidarProle, AvaliadorConstruir, AvaliadorOcioso,
    aplicar_humor, aplicar_eventos_globais, aplicar_trava_dependente, aplicar_persistencia,
)


class NPCBrain:
    AVALIADORES = (AvaliadorComer(), AvaliadorDormir(), AvaliadorTrabalhar(),
                   AvaliadorSocializar(), AvaliadorCuidarProle(),
                   AvaliadorConstruir(), AvaliadorOcioso())
    MODIFICADORES = (aplicar_humor, aplicar_eventos_globais,
                      aplicar_trava_dependente, aplicar_persistencia)

    @staticmethod
    def calcular_utilidade(npc: NPC, hora_atual: int, config: Dict, locais: Dict = None,
                            eventos_globais: Optional[List] = None, indice=None) -> Dict[Acao, float]:
        ctx = ContextoDecisao(npc=npc, hora=hora_atual, config=config, locais=locais,
                               eventos_globais=eventos_globais or [], indice=indice)

        utilidades = {acao: 0.0 for acao in Acao}
        for avaliador in NPCBrain.AVALIADORES:
            utilidades[avaliador.acao] = avaliador.avaliar(ctx)
        for modificador in NPCBrain.MODIFICADORES:
            utilidades = modificador(utilidades, ctx)
        return utilidades

    @staticmethod
    def decidir_acao(npc: NPC, hora_atual: int, config: Dict, locais: Dict = None,
                      eventos_globais: Optional[List] = None, indice=None):
        """`config` é o config.json completo — ver `calcular_utilidade`."""
        # --- REDE DE SEGURANÇA: Habitação ---
        # X05 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 18): mesma correção que P04
        # (docs/12_PLANO_CIDADE_VIVA.md) já aplicou em `movement.py` — `locais.items()`
        # sem filtrar cidade podia mudar o NPC de cidade em silêncio (todo NPC sem
        # casa ia pra MESMA casa, a primeira do dicionário global). Mudar alguém de
        # cidade é decisão de migração, não fallback: sem casa na própria cidade,
        # `casa_id` fica como está, com um warning.
        if locais and (npc.casa_id not in locais):
            casas_disponiveis = indice.residencias_ativas(npc.cidade_id) if indice else []
            if casas_disponiveis:
                npc.casa_id = casas_disponiveis[0]
            else:
                WorldLogger.warning(
                    f"⚠️ [DECISÃO] {npc.nome} não tem casa válida na própria cidade "
                    f"(cidade_id={npc.cidade_id}) — casa_id inalterado.", npc=npc)

        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, config, locais, eventos_globais, indice)
        npc.acao_atual = max(utilidades, key=utilidades.get)

        # Validação de Segurança do Trabalho
        if npc.acao_atual == Acao.TRABALHAR:
            loc_trab = locais.get(npc.local_trabalho_id) if locais else None
            if not loc_trab or loc_trab.status != 1:
                npc.acao_atual = Acao.OCIOSO
