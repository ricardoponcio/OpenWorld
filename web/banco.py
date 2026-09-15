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


def configurar_db(db: DatabaseManager) -> None:
    """P01 (docs/16_PLANO_PAINEL_E_IA.md): mesmo padrão de
    `config.resolver.configurar_fonte` — troca a instância usada pelo processo
    inteiro. Único jeito de testar uma rota Flask com `app.test_client()` sem
    tocar `database/openworld.db`: chame isto ANTES de importar `web.dashboard`
    pela primeira vez (o módulo faz `db = obter_db()` na importação)."""
    global _db
    _db = db


def obter_db() -> DatabaseManager:
    global _db
    if _db is None:
        _db = DatabaseManager(CAMINHO_BANCO)
    return _db
