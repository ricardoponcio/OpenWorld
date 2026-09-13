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

    # ------------------------------------------------------------------
    # F01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): fila de ações de mundo —
    # `enfileirar_acoes` é chamado do processo do Flask (nenhum EstadoDoMundo vivo
    # ali); `drenar_acoes_pendentes` é chamado só por run_simulation.py, que aplica
    # cada payload com o mundo vivo.
    # ------------------------------------------------------------------
    def enfileirar_acoes(self, payloads: list) -> None:
        if not payloads:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                'INSERT INTO mestre_acoes_pendentes (payload) VALUES (?)',
                [(json.dumps(p),) for p in payloads])

    def drenar_acoes_pendentes(self) -> list:
        """Lê TODAS as ações ainda não aplicadas e já marca `aplicada_em` na mesma
        chamada — devolve os payloads decodificados, na ordem em que chegaram.
        Idempotente por construção: uma ação já marcada nunca é devolvida de novo,
        mesmo que o processo da simulação seja reiniciado no meio do caminho."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, payload FROM mestre_acoes_pendentes WHERE aplicada_em IS NULL ORDER BY id')
            pendentes = cursor.fetchall()
            if not pendentes:
                return []
            cursor.executemany(
                "UPDATE mestre_acoes_pendentes SET aplicada_em = datetime('now', 'localtime') WHERE id = ?",
                [(row['id'],) for row in pendentes])
            return [json.loads(row['payload']) for row in pendentes]

    def ha_fila_nao_drenada(self, segundos: int) -> bool:
        """Existe ação pendente há mais de `segundos` sem ser aplicada — sinal de que
        `run_simulation.py` não está rodando (ou travou). Usado só pra avisar o
        jogador na interface em vez de deixar a ação sumir em silêncio (a mesma
        condição que `/api/mestre/avancar_tempo` já expõe hoje, por timeout)."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM mestre_acoes_pendentes "
                "WHERE aplicada_em IS NULL AND criada_em <= datetime('now', 'localtime', ?) LIMIT 1",
                (f'-{segundos} seconds',))
            return cursor.fetchone() is not None
