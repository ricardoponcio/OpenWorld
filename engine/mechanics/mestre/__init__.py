"""
MODULE: mestre/__init__.py
FUNÇÃO: Fachada do pacote do Modo Mestre — mantém `from engine.mechanics.mestre import
MestreManager` funcionando para web/ e builder/ depois da quebra em pacote (R-F03).
"""
from .gerenciador import MestreManager
from .acoes import AcaoDeMundo, AcaoProposta, ContextoMestre, ACOES, POR_COMANDO

__all__ = [
    "MestreManager",
    "AcaoDeMundo", "AcaoProposta", "ContextoMestre",
    "ACOES", "POR_COMANDO",
]
