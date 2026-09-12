import json
from ..models import Evento


class RepositorioEvento:
    """SQL de eventos individuais e eventos globais (R-E01) — antes espalhado entre
    `DatabaseManager`, `engine/mechanics/events.py` e `engine/mechanics/mestre.py`."""

    def __init__(self, db):
        self.db = db

    def salvar(self, evento: Evento):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO eventos VALUES (?, ?, ?, ?, ?, ?, ?)', (
                evento.id, evento.timestamp, evento.local_id, json.dumps(evento.envolvidos),
                evento.tipo_evento, evento.modificador_afinidade, evento.resumo_estruturado
            ))

    def salvar_muitos(self, eventos: list) -> None:
        """E01 (docs/PLANO_POPULACAO_E_ESCALA.md): uma transação pra TODOS os eventos
        do tick, não um commit por evento — mesmo padrão de `RepositorioNPC.
        salvar_muitos` (P05). `processar_interacao_social` chamava `salvar` um de
        cada vez: ~170 interações/tick com 25.000 NPCs, ~170 commits só nisto."""
        if not eventos:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                'INSERT OR REPLACE INTO eventos VALUES (?, ?, ?, ?, ?, ?, ?)',
                [(evento.id, evento.timestamp, evento.local_id, json.dumps(evento.envolvidos),
                  evento.tipo_evento, evento.modificador_afinidade, evento.resumo_estruturado)
                 for evento in eventos])

    def podar_por_idade(self, dia_de_corte: int) -> int:
        """E02 (docs/PLANO_POPULACAO_E_ESCALA.md): apaga da tabela `eventos` (NUNCA
        `eventos_globais` — outra tabela, outra semântica, o `GlobalEventManager`
        depende dela) tudo com "Dia N" anterior a `dia_de_corte`. `timestamp` é o
        texto RPG ("Dia 42, 14:30" — `RelogioMundo.timestamp_rpg`); extrai o número
        do dia via `SUBSTR`/`INSTR` em vez de trazer a tabela inteira pro Python só
        pra decidir o que apagar. Devolve quantas linhas foram apagadas."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM eventos WHERE "
                "CAST(SUBSTR(timestamp, 5, INSTR(timestamp, ',') - 5) AS INTEGER) < ?",
                (dia_de_corte,))
            return cursor.rowcount

    def atualizar_resumo(self, evento_id: str, resumo: str):
        with self.db.connection() as conn:
            conn.cursor().execute("UPDATE eventos SET resumo_estruturado = ? WHERE id = ?", (resumo, evento_id))

    def ultimo_rowid(self) -> int:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT MAX(rowid) AS m FROM eventos").fetchone()
            return row['m'] or 0

    def coletar_apos_rowid(self, rowid: int) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT timestamp, resumo_estruturado FROM eventos WHERE rowid > ? ORDER BY rowid ASC",
                (rowid,)
            ).fetchall()
            return [dict(r) for r in rows]

    def resumos_recentes(self, limite: int) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT resumo_estruturado FROM eventos ORDER BY rowid DESC LIMIT ?", (limite,))
            return cursor.fetchall()

    def listar_recentes(self, limite: int) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp, resumo_estruturado FROM eventos ORDER BY timestamp DESC LIMIT ?', (limite,))
            return cursor.fetchall()

    # ------------------------------------------------------------------
    # Eventos globais (a "vontade do mundo")
    # ------------------------------------------------------------------

    def salvar_global(self, ev_id, titulo, desc, tipo, loc_id, mods_json, duracao):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO eventos_globais
                              VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                           (ev_id, titulo, desc, tipo, loc_id, mods_json, duracao))

    def carregar_globais_ativos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM eventos_globais WHERE ticks_restantes > 0')
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def atualizar_ticks_restantes(self, eventos_ativos: list):
        """Decrementa cada evento em `eventos_ativos` (formato de `carregar_globais_ativos`)
        um tick; remove os que chegam a zero."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for ev in eventos_ativos:
                novos_ticks = ev['ticks_restantes'] - 1
                if novos_ticks <= 0:
                    cursor.execute("DELETE FROM eventos_globais WHERE id = ?", (ev['id'],))
                else:
                    cursor.execute("UPDATE eventos_globais SET ticks_restantes = ? WHERE id = ?", (novos_ticks, ev['id']))

    def titulos_globais_ativos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT titulo FROM eventos_globais WHERE ticks_restantes > 0")
            return cursor.fetchall()

    def buscar_global_ativo(self):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT titulo, descricao, tipo FROM eventos_globais WHERE ticks_restantes > 0 LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None

    def listar_globais_recentes(self, limite: int) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp_criacao, titulo FROM eventos_globais ORDER BY timestamp_criacao DESC LIMIT ?', (limite,))
            return cursor.fetchall()
