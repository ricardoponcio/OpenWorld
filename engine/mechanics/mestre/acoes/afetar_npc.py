"""
MODULE: afetar_npc.py
FUNÇÃO: Ação de mundo AFETAR_NPC do Modo Mestre.
"""
from typing import List

from ....models import ComandoMestre, HumorNPC
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class AfetarNpc(AcaoDeMundo):
    comando = ComandoMestre.AFETAR_NPC

    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        delta_saude = acao.dados.get("saude", 0)
        humor = self._humor_valido(acao.dados.get("humor"))
        db.npcs.ajustar_saude_e_humor(acao.alvo_id, delta_saude, humor)
        return [f"👤 {acao.alvo_id} afetado (saúde {delta_saude:+}, humor {humor})"]

    @staticmethod
    def _humor_valido(humor_proposto) -> str:
        """Humor vem da IA — entrada não confiável, valida contra o enum antes de
        persistir (R-C04 / ARQUITETURA.md Seção 9)."""
        try:
            return HumorNPC(humor_proposto).value
        except ValueError:
            return HumorNPC.NEUTRO.value
