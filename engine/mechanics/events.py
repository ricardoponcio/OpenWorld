"""
MODULE: events.py
FUNÇÃO: Gerenciamento de Eventos Globais.

DESCRIÇÃO:
    Gerencia os eventos temporários globais do reino, atualizando a duração
    de ticks ativos e limpando eventos expirados da base de dados.
"""
import sqlite3


class GlobalEventManager:
    @staticmethod
    def atualizar_eventos_globais(engine):
        """
        Decrementa os ticks restantes de todos os eventos globais ativos.
        Deleta eventos expirados e atualiza a duração dos ativos no banco de dados.
        """
        eventos_globais = engine.db.carregar_eventos_globais_ativos()
        for ev in eventos_globais:
            novos_ticks = ev['ticks_restantes'] - 1
            conn = sqlite3.connect(engine.db.db_path)
            if novos_ticks <= 0:
                conn.execute("DELETE FROM eventos_globais WHERE id = ?", (ev['id'],))
            else:
                conn.execute("UPDATE eventos_globais SET ticks_restantes = ? WHERE id = ?", (novos_ticks, ev['id']))
            conn.commit()
            conn.close()
