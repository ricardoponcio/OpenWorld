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
        if locais and (npc.casa_id not in locais):
            casas_disponiveis = [l_id for l_id, l in locais.items() if l.tipo == 'Casa' or l.categoria == 'residencia']
            if casas_disponiveis:
                npc.casa_id = casas_disponiveis[0]

        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, config, locais, eventos_globais, indice)
        npc.acao_atual = max(utilidades, key=utilidades.get)

        # Validação de Segurança do Trabalho
        if npc.acao_atual == Acao.TRABALHAR:
            loc_trab = locais.get(npc.local_trabalho_id) if locais else None
            if not loc_trab or loc_trab.status != 1:
                npc.acao_atual = Acao.OCIOSO
