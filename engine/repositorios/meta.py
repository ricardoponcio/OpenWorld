from ..models import MetaChave


class RepositorioMeta:
    """Chave/valor de estado do mundo (`mundo_meta` — relógio, pausa, velocidade...)."""

    def __init__(self, db):
        self.db = db

    def salvar(self, chave, valor: str):
        """`chave` aceita `MetaChave` ou `str` — `str` continua funcionando pra não
        quebrar `builder/fix/` e SQL ad-hoc de diagnóstico (R-B05)."""
        chave_str = chave.value if isinstance(chave, MetaChave) else chave
        with self.db.connection() as conn:
            conn.cursor().execute('INSERT OR REPLACE INTO mundo_meta VALUES (?, ?)', (chave_str, valor))

    def carregar(self, chave) -> str:
        chave_str = chave.value if isinstance(chave, MetaChave) else chave
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT valor FROM mundo_meta WHERE chave = ?', (chave_str,))
            row = cursor.fetchone()
            return row[0] if row else None
