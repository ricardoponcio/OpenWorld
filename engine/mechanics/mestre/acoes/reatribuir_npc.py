"""
MODULE: reatribuir_npc.py
FUNÇÃO: Ação de mundo REATRIBUIR_NPC do Modo Mestre.
"""
from typing import List, Optional

from ....models import ComandoMestre
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre

# Marcador que a IA usa para dizer "o local que você acabou de criar nesta mesma
# resposta" — o prompt do Mestre documenta esse contrato.
MARCADOR_NOVO_LOCAL = "NOVO_LOCAL"


class ReatribuirNpc(AcaoDeMundo):
    comando = ComandoMestre.REATRIBUIR_NPC

    def aplicar(self, mundo, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        npc = self.encontrar_npc(mundo, acao.alvo_id)
        if npc is None:
            return [f"⚠️ NPC {acao.alvo_id} não encontrado — nada mudou."]

        trabalho_id = self._resolver(acao.dados.get("local_trabalho_id"), contexto)
        casa_id = self._resolver(acao.dados.get("casa_id"), contexto)

        resultados = []
        if trabalho_id and trabalho_id in mundo.locais:
            npc.local_trabalho_id = trabalho_id
            resultados.append(f"💼 {acao.alvo_id} agora trabalha em {trabalho_id}")
        if casa_id and casa_id in mundo.locais:
            # F01: a porta de A04 — reindexa `npcs_por_casa`, não só o campo. Sem
            # isto o NPC continuaria aparecendo (ou faltando) na casa errada em
            # qualquer consulta que use o índice mantido (armadilha 12).
            mundo.mudar_casa(npc, casa_id)
            resultados.append(f"🏠 {acao.alvo_id} mudou-se para {casa_id}")
        if resultados:
            mundo.db.npcs.salvar(npc)
            # F03: reatribuir trabalho/casa muda o que o NPC quer — reavalia agora.
            mundo.acordar(npc)
        return resultados

    @staticmethod
    def _resolver(local_id: Optional[str], contexto: ContextoMestre) -> Optional[str]:
        """Troca o marcador `NOVO_LOCAL` pelo id criado por CRIAR_LOCAL nesta mesma
        lista de ações. Sem um CRIAR_LOCAL antes, o marcador resolve para None e a
        reatribuição é simplesmente ignorada."""
        if local_id == MARCADOR_NOVO_LOCAL:
            return contexto.novo_local_id
        return local_id
