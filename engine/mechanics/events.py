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
        # A03 (docs/13_PLANO_POPULACAO_E_ESCALA.md): ids de evento global já vistos, pra
        # detectar quando um É NOVO (não pra decidir se ele está ativo — isso continua
        # vindo do banco, todo tick). Escopo de instância, não é o tipo de estado que
        # fica velho: só serve pra saber "eu já acordei todo mundo por causa deste?".
        self._eventos_globais_conhecidos = set()

    def atualizar_eventos_globais(self):
        """
        Decrementa os ticks restantes de todos os eventos globais ativos.
        Deleta eventos expirados e atualiza a duração dos ativos no banco de dados.
        """
        eventos_globais = self._mundo.db.eventos.carregar_globais_ativos()
        if not eventos_globais:
            return

        # A03: um evento global novo (criado pelo Storyteller, fora do tick) muda o
        # que TODO NPC quer (clima, economia) — sem acordar todo mundo, quem estivesse
        # num salto grande da agenda (A02) só sentiria o evento na próxima reavaliação
        # natural, que pode ser horas depois.
        ids_atuais = {ev['id'] for ev in eventos_globais}
        if ids_atuais - self._eventos_globais_conhecidos:
            for npc in self._mundo.npcs:
                if npc.esta_vivo():
                    self._mundo.acordar(npc)
        self._eventos_globais_conhecidos = ids_atuais

        self._mundo.db.eventos.atualizar_ticks_restantes(eventos_globais)
