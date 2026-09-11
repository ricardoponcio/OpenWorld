"""
MODULE: core.py
FUNÇÃO: Inicialização e Controle Central do Motor (SimulationEngine).

DESCRIÇÃO:
    Realiza o bootstrap do ecossistema do OpenWorld, carregando o banco de
    dados, estados e configurações, e delegando a execução do tick global
    ao módulo especializado GameLoop.
"""
from .database import DatabaseManager
from .logger import WorldLogger
from .consultas_npc import NPCUtils
from .config_loader import carregar_config_global
from .loop import GameLoop


class SimulationEngine:
    def __init__(self, db_path="database/openworld.db"):
        self.db = DatabaseManager(db_path)
        self.npcs = self.db.carregar_npcs()
        self.locais = self.db.carregar_locais_por_id()
        # Fase 2.1 (P0.3): expansão urbana (housing.py) precisa do pixel-âncora da
        # cidade do NPC pra sortear coordenada de mundo pra casa nova, não mais uma
        # grade local fake.
        self.cidades = self.db.carregar_cidades_por_id()
        self.tick_count = 0
        
        # Carregar Configuração usando utilitário de config centralizado
        self.config = carregar_config_global()
        
        # Inicializar data simulada recuperando do banco usando utilitário centralizado
        self.data_simulada = NPCUtils.obter_data_simulada_inicial(self.db)

    def recarregar_habitantes(self):
        """Recarrega os NPCs do banco para sincronizar com mudanças externas (ex: JobMarket)."""
        novos_npcs = self.db.carregar_npcs()
        if novos_npcs:
            self.npcs = novos_npcs
            WorldLogger.debug(f"🔄 Memória sincronizada com o banco de dados ({len(self.npcs)} NPCs).")

    def tick(self):
        """
        Delega a execução do tick global da simulação ao especialista GameLoop.
        """
        GameLoop.executar_tick(self)
