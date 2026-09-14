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
    """Recalcula o humor a cada tick. Recebe só a config (R-F01): o cálculo é função
    das necessidades do próprio NPC, então este é o único gerenciador que não precisa
    do estado do mundo."""

    def __init__(self, config: dict):
        self._config = config

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

    def processar_humor(self, npc: NPC, minutos: int = 1):
        """Aproxima gradualmente o humor do NPC do humor-alvo calculado a partir do
        seu bem-estar atual. Chamado uma vez por NPC vivo processado (A02, docs/
        13_PLANO_POPULACAO_E_ESCALA.md: `minutos` é quantos minutos se passaram desde a
        última avaliação).

        X01 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 17): a agenda faz o NPC ser
        avaliado ~20-30 vezes por dia em vez de 1.440 — `minutos` pode ser 1 ou 240.
        A versão antiga fazia `min(minutos, distancia)` TENTATIVAS de transição, o
        que capava o número de tentativas ao número de PASSOS possíveis: com
        `distancia<=4` (a escala tem 5 humores), nunca mais de 4 tentativas por
        chamada, não importa se passaram 240 minutos — o humor ficou ~3x mais lento
        que antes da agenda (P(transição no dia) caiu de 1,000 pra 0,352 medido).

        `p_transicao` é a probabilidade de AO MENOS UMA transição ter acontecido no
        intervalo inteiro de `minutos` (1.440 tentativas de 1 minuto viram uma só
        fórmula, sem laço) — é o que faz o resultado ser o MESMO nos dois regimes
        (1 chamada de 240 minutos ≈ 240 chamadas de 1 minuto)."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        alvo = NPCMoodManager._calcular_humor_alvo(npc, cfg_bio)

        if npc.humor == alvo:
            return

        chance_transicao = cfg_get(cfg_bio, "humor_chance_transicao")
        p_transicao = 1.0 - (1.0 - chance_transicao) ** minutos

        # NPC em Pânico/Medo (forçado externamente) não tem posição na escala
        # normal — qualquer transição o move direto para o alvo calculado,
        # trazendo-o de volta ao normal assim que a condição é reavaliada.
        escala = [h.value for h in HumorNPC.escala_normal()]
        if npc.humor not in escala:
            if random.random() < p_transicao:
                npc.humor = alvo
            return

        indice_atual = escala.index(npc.humor)
        indice_alvo = escala.index(alvo)
        distancia = abs(indice_alvo - indice_atual)
        direcao = 1 if indice_alvo > indice_atual else -1

        if random.random() < p_transicao:
            # Nunca mais tentativas extras do que MINUTOS realmente dá direito —
            # com `minutos=1` (o caso comum, tick a tick) isto é 0, e o humor
            # sempre anda 1 passo por vez, nunca pula direto pro alvo (é a garantia
            # que a "gradação" do humor promete, independente de quão grande
            # `distancia` seja).
            tentativas_extra = min(minutos, distancia) - 1
            passos = 1 + sum(1 for _ in range(tentativas_extra) if random.random() < p_transicao)
            npc.humor = escala[indice_atual + direcao * min(passos, distancia)]
