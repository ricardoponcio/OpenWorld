"""
MODULE: afetar_npc.py
FUNÇÃO: Ação de mundo AFETAR_NPC do Modo Mestre.
"""
from typing import List

from ....models import ComandoMestre, ESCALA_MAXIMA, ESCALA_MINIMA, HumorNPC
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class AfetarNpc(AcaoDeMundo):
    comando = ComandoMestre.AFETAR_NPC

    def aplicar(self, mundo, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        npc = self.encontrar_npc(mundo, acao.alvo_id)
        if npc is None:
            return [f"⚠️ NPC {acao.alvo_id} não encontrado — nada mudou."]

        delta_saude = acao.dados.get("saude", 0)
        humor = self._humor_valido(acao.dados.get("humor"))
        npc.saude = max(ESCALA_MINIMA, min(ESCALA_MAXIMA, npc.saude + delta_saude))
        npc.humor = humor
        mundo.db.npcs.salvar(npc)
        # F03 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): mudou saúde/humor do NPC por um
        # motivo que não é o próprio metabolismo dele — reavalia agora, sem esperar o
        # instante que a agenda (A02) já tivesse calculado.
        mundo.acordar(npc)
        return [f"👤 {acao.alvo_id} afetado (saúde {delta_saude:+}, humor {humor})"]

    @staticmethod
    def _humor_valido(humor_proposto) -> str:
        """Humor vem da IA — entrada não confiável, valida contra o enum antes de
        persistir (R-C04 / ARQUITETURA.md Seção 9)."""
        try:
            return HumorNPC(humor_proposto).value
        except ValueError:
            return HumorNPC.NEUTRO.value
