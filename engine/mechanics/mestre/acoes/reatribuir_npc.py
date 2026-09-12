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

    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        trabalho_id = self._resolver(acao.dados.get("local_trabalho_id"), contexto)
        casa_id = self._resolver(acao.dados.get("casa_id"), contexto)

        resultados = []
        if trabalho_id and db.locais.existe(trabalho_id):
            db.npcs.atualizar_local_trabalho(acao.alvo_id, trabalho_id)
            resultados.append(f"💼 {acao.alvo_id} agora trabalha em {trabalho_id}")
        if casa_id and db.locais.existe(casa_id):
            db.npcs.atualizar_casa(acao.alvo_id, casa_id)
            resultados.append(f"🏠 {acao.alvo_id} mudou-se para {casa_id}")
        return resultados

    @staticmethod
    def _resolver(local_id: Optional[str], contexto: ContextoMestre) -> Optional[str]:
        """Troca o marcador `NOVO_LOCAL` pelo id criado por CRIAR_LOCAL nesta mesma
        lista de ações. Sem um CRIAR_LOCAL antes, o marcador resolve para None e a
        reatribuição é simplesmente ignorada."""
        if local_id == MARCADOR_NOVO_LOCAL:
            return contexto.novo_local_id
        return local_id
