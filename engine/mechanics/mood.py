"""
MODULE: mood.py
FUNÇÃO: Gerenciamento do Humor Emergente dos NPCs.

DESCRIÇÃO:
    Antes da Frente 3, o humor era uma flag setada ad-hoc só ao socializar
    (20% de chance de virar Alegre, 10% de virar Triste) e nunca decaía de
    volta — por isso toda a população convergia para "Alegre" com o tempo.

    Este módulo substitui isso por um retrato contínuo do bem-estar do NPC,
    recalculado a cada tick a partir de energia/fome/social (as mesmas
    necessidades que a engine já rastreia), com uma transição gradual (não
    instantânea) em direção ao humor-alvo. Pânico/Medo ficam fora deste
    cálculo — continuam reservados para serem forçados externamente (ex.:
    futuro Modo Mestre de IA), e a transição gradual naturalmente traz o NPC
    de volta ao humor calculado assim que ele deixa de estar em Pânico/Medo.
"""
import random
from ..models import NPC, HumorNPC
from ..config_loader import cfg_get


class NPCMoodManager:
    @staticmethod
    def _calcular_humor_alvo(npc: NPC, cfg_bio: dict) -> str:
        peso_energia = cfg_get(cfg_bio, "humor_peso_energia")
        peso_fome = cfg_get(cfg_bio, "humor_peso_fome")
        peso_social = cfg_get(cfg_bio, "humor_peso_social")

        bem_estar = (
            peso_energia * npc.energia
            + peso_fome * (100 - npc.fome)
            + peso_social * npc.social
        )

        if bem_estar >= cfg_get(cfg_bio, "humor_limiar_alegre"):
            return HumorNPC.ALEGRE.value
        if bem_estar >= cfg_get(cfg_bio, "humor_limiar_contente"):
            return HumorNPC.CONTENTE.value
        if bem_estar <= cfg_get(cfg_bio, "humor_limiar_angustiado"):
            return HumorNPC.ANGUSTIADO.value
        if bem_estar <= cfg_get(cfg_bio, "humor_limiar_triste"):
            return HumorNPC.TRISTE.value
        return HumorNPC.NEUTRO.value

    @staticmethod
    def processar_humor(engine, npc: NPC):
        """Aproxima gradualmente o humor do NPC do humor-alvo calculado a partir
        do seu bem-estar atual. Chamado uma vez por NPC vivo a cada tick."""
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        alvo = NPCMoodManager._calcular_humor_alvo(npc, cfg_bio)

        if npc.humor == alvo:
            return

        chance_transicao = cfg_get(cfg_bio, "humor_chance_transicao")
        if random.random() >= chance_transicao:
            return

        # NPC em Pânico/Medo (forçado externamente) não tem posição na escala
        # normal — qualquer transição o move direto para o alvo calculado,
        # trazendo-o de volta ao normal assim que a condição é reavaliada.
        escala = [h.value for h in HumorNPC.escala_normal()]
        if npc.humor not in escala:
            npc.humor = alvo
            return

        indice_atual = escala.index(npc.humor)
        indice_alvo = escala.index(alvo)

        if indice_alvo > indice_atual:
            npc.humor = escala[indice_atual + 1]
        else:
            npc.humor = escala[indice_atual - 1]
