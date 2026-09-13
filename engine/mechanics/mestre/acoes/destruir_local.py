"""
MODULE: destruir_local.py
FUNÇÃO: Ação de mundo DESTRUIR_LOCAL do Modo Mestre.
"""
from typing import List

from ....models import ComandoMestre
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class DestruirLocal(AcaoDeMundo):
    comando = ComandoMestre.DESTRUIR_LOCAL

    def aplicar(self, mundo, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        local = mundo.locais.get(acao.alvo_id)
        if local is None:
            return [f"⚠️ Local {acao.alvo_id} não encontrado — nada mudou."]

        local.status = 0
        local.integridade = 0
        mundo.desativar_local(acao.alvo_id)

        # F03 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): quem morava, trabalhava ou estava
        # ali reavalia agora — o local que os ocupava não existe mais. Morada/
        # localização usam o índice mantido (A04, O(1)); trabalho não tem índice
        # próprio (é uma ação rara, disparada pelo jogador — O(NPCs) aqui é barato).
        # `NPC` não é hashável (dataclass com __eq__ padrão) — de-duplica por id.
        afetados = {n.id: n for n in mundo.npcs_por_casa.get(acao.alvo_id, ())}
        afetados.update((n.id, n) for n in mundo.npcs_por_localizacao.get(acao.alvo_id, ()))
        afetados.update((n.id, n) for n in mundo.npcs if n.local_trabalho_id == acao.alvo_id)
        for npc in afetados.values():
            mundo.acordar(npc)

        return [f"💥 {acao.alvo_id} foi destruído"]
