import json


class RepositorioMestre:
    """Conversas do Modo Mestre de IA (Frente 5) — tabela `mestre_conversas`."""

    def __init__(self, db):
        self.db = db

    def salvar_mensagem(self, autor: str, mensagem: str, acoes_propostas: list = None) -> int:
        """Persiste um turno de conversa (jogador ou mestre) e retorna o id gerado."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO mestre_conversas (autor, mensagem, acoes_propostas, aplicada) VALUES (?, ?, ?, 0)',
                (autor, mensagem, json.dumps(acoes_propostas) if acoes_propostas else None)
            )
            return cursor.lastrowid

    def carregar_historico(self, limite: int = 50) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM mestre_conversas ORDER BY id DESC LIMIT ?', (limite,))
            rows = [dict(r) for r in cursor.fetchall()]
            return list(reversed(rows))

    def carregar_mensagem(self, conversa_id: int) -> dict:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM mestre_conversas WHERE id = ?', (conversa_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def marcar_aplicada(self, conversa_id: int):
        with self.db.connection() as conn:
            conn.cursor().execute('UPDATE mestre_conversas SET aplicada = 1 WHERE id = ?', (conversa_id,))
