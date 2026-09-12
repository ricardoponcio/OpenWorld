"""
MODULE: destruir_local.py
FUNÇÃO: Ação de mundo DESTRUIR_LOCAL do Modo Mestre.
"""
from typing import List

from ....models import ComandoMestre
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class DestruirLocal(AcaoDeMundo):
    comando = ComandoMestre.DESTRUIR_LOCAL

    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        db.locais.desativar(acao.alvo_id)
        return [f"💥 {acao.alvo_id} foi destruído"]
