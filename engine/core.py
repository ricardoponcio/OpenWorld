"""
MODULE: core.py
FUNÇÃO: Inicialização e Controle Central do Motor (SimulationEngine).

DESCRIÇÃO:
    Realiza o bootstrap do ecossistema do OpenWorld, carregando o banco de
    dados, estados e configurações, e delegando a execução do tick global
    ao módulo especializado GameLoop.

    É o ponto de entrada que constrói as dependências de infraestrutura do processo
    de simulação: o `DatabaseManager` nasce aqui e em nenhum gerenciador de mecânica
    (ARQUITETURA.md Seção 7, "Injeção de dependência").
"""
from .database import DatabaseManager
from .logger import WorldLogger
from .consultas_npc import NPCUtils
from .config_loader import carregar_config_global
from .mundo import EstadoDoMundo
from .loop import GameLoop


class SimulationEngine:
    def __init__(self, db_path="database/openworld.db"):
        db = DatabaseManager(db_path)
        # Carregar Configuração usando utilitário de config centralizado — fica fora de
        # `EstadoDoMundo` (R-F01): é estática, não faz parte do estado que muda a cada
        # tick, e os gerenciadores continuam recebendo-a à parte.
        self.config = carregar_config_global()

        self.mundo = EstadoDoMundo(
            npcs=db.npcs.carregar_todos(),
            locais=db.locais.carregar_por_id(),
            # Fase 2.1 (P0.3): expansão urbana (housing.py) precisa do pixel-âncora da
            # cidade do NPC pra sortear coordenada de mundo pra casa nova, não mais uma
            # grade local fake.
            cidades=db.mundo.carregar_cidades_por_id(),
            data_simulada=NPCUtils.obter_data_simulada_inicial(db),
            db=db,
        )

        # O laço é construído uma vez, não por tick: ele monta os gerenciadores de
        # mecânica e os reusa, cada um recebendo só o `EstadoDoMundo` e a config (R-F01).
        self._loop = GameLoop(self.mundo, self.config)

    def recarregar_habitantes(self):
        """Recarrega os NPCs do banco para sincronizar com mudanças externas (ex: JobMarket)."""
        novos_npcs = self.mundo.db.npcs.carregar_todos()
        if novos_npcs:
            self.mundo.npcs = novos_npcs
            WorldLogger.debug(f"🔄 Memória sincronizada com o banco de dados ({len(self.mundo.npcs)} NPCs).")

    def tick(self):
        """
        Delega a execução do tick global da simulação ao especialista GameLoop.
        """
        self._loop.executar_tick()
