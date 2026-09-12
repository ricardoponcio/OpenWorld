"""
MODULE: banco.py
FUNÇÃO: Instância única de DatabaseManager para o processo do dashboard.

DESCRIÇÃO:
    DatabaseManager abre um pool de conexões e roda o schema no __init__ — criar um
    por requisição (comportamento anterior de mestre_routes._get_db) vazava 5
    conexões SQLite por chamada. O dashboard é um processo só, leitor da simulação;
    uma instância compartilhada basta, e o pool já é seguro entre threads.
"""
import os
from engine.database import DatabaseManager

CAMINHO_BANCO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))

_db = None


def obter_db() -> DatabaseManager:
    global _db
    if _db is None:
        _db = DatabaseManager(CAMINHO_BANCO)
    return _db
