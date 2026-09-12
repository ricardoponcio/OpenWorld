"""
MODULE: events.py
FUNÇÃO: Gerenciamento de Eventos Globais.

DESCRIÇÃO:
    Gerencia os eventos temporários globais do reino, atualizando a duração
    de ticks ativos e limpando eventos expirados da base de dados.

    Recebe só o mundo (R-F01): não lê nenhum parâmetro de config, toda a regra de
    expiração mora no repositório de eventos.
"""
from ..mundo import EstadoDoMundo


class GlobalEventManager:
    def __init__(self, mundo: EstadoDoMundo):
        self._mundo = mundo

    def atualizar_eventos_globais(self):
        """
        Decrementa os ticks restantes de todos os eventos globais ativos.
        Deleta eventos expirados e atualiza a duração dos ativos no banco de dados.
        """
        eventos_globais = self._mundo.db.eventos.carregar_globais_ativos()
        if not eventos_globais:
            return

        self._mundo.db.eventos.atualizar_ticks_restantes(eventos_globais)
