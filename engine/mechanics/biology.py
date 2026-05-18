from ..models import NPC
from .reproduction import NPCReproductionManager
from .lifecycle import NPCLifecycleManager

class NPCBiologyManager:
    @staticmethod
    def processar_concepcao(engine):
        """Redireciona para o gerenciador de reprodução."""
        NPCReproductionManager.processar_concepcao(engine)

    @staticmethod
    def processar_parto(engine, mae: NPC):
        """Redireciona para o gerenciador de reprodução."""
        NPCReproductionManager.processar_parto(engine, mae)

    @staticmethod
    def processar_crescimento(engine):
        """Redireciona para o gerenciador de ciclo de vida (aging)."""
        NPCLifecycleManager.processar_crescimento(engine)

    @staticmethod
    def processar_morte(engine, npc: NPC):
        """Redireciona para o gerenciador de ciclo de vida (aging)."""
        NPCLifecycleManager.processar_morte(engine, npc)
