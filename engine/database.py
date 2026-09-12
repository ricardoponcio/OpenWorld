import sqlite3
import os
import queue
from contextlib import contextmanager
from .repositorios import (
    RepositorioNPC, RepositorioLocal, RepositorioEvento,
    RepositorioMeta, RepositorioMestre, RepositorioMundo,
)


class DatabaseManager:
    """Pool de conexões + ciclo de vida do schema (R-E01). Todo SQL de domínio mora nos
    repositórios (`self.npcs`, `self.locais`, `self.eventos`, `self.meta`, `self.mestre`,
    `self.mundo`) — este arquivo já foi um único lugar com ~20 métodos de SQL misturado
    (NPCs, locais, eventos, meta, mundo, mestre), o que o tornava o ponto de maior
    acoplamento do projeto."""

    # R-E03: colunas que `schema.sql` já declara hoje, mas que uma vez foram
    # adicionadas depois da criação original das tabelas — `CREATE TABLE IF NOT
    # EXISTS` não recria uma tabela já existente, então um banco criado antes dessas
    # colunas existirem no schema fica sem elas para sempre, a menos que alguém rode
    # o ALTER TABLE. Os carregadores (`RepositorioNPC`/`RepositorioLocal`) confiavam
    # cegamente que a coluna podia não estar lá (`if 'x' in row.keys()`) em vez de
    # corrigir o banco uma vez — eram 26 desses fallbacks.
    COLUNAS_ESPERADAS = {
        "npcs": [
            ("profissao_id", "TEXT"),
            ("cidade_id", "INTEGER"),
            ("saude", "INTEGER DEFAULT 100"),
            ("humor", "TEXT DEFAULT 'Neutro'"),
            ("genero", "TEXT DEFAULT 'M'"),
            ("estagio_vida", "TEXT DEFAULT 'adulto'"),
            ("raca", "TEXT DEFAULT ''"),
            ("personalidade", "TEXT DEFAULT ''"),
            ("background", "TEXT DEFAULT ''"),
            ("estado_civil", "TEXT DEFAULT 'solteiro'"),
            ("gravidez_ticks", "INTEGER DEFAULT 0"),
        ],
        "locais": [
            ("cidade_id", "INTEGER"),
            ("categoria", "TEXT"),
            ("status", "INTEGER DEFAULT 1"),
            ("integridade", "INTEGER DEFAULT 100"),
            ("capacidade", "INTEGER DEFAULT 5"),
            ("salario_base", "INTEGER DEFAULT 100"),
            ("tipo_local", "TEXT DEFAULT ''"),
            ("bairro", "TEXT DEFAULT ''"),
            ("dono_npc_id", "TEXT DEFAULT ''"),
        ],
    }

    def __init__(self, db_path="database/openworld.db", pool_size=5):
        self.db_path = db_path
        self._pool = queue.Queue(maxsize=pool_size)
        self._init_db()
        self.npcs = RepositorioNPC(self)
        self.locais = RepositorioLocal(self)
        self.eventos = RepositorioEvento(self)
        self.meta = RepositorioMeta(self)
        self.mestre = RepositorioMestre(self)
        self.mundo = RepositorioMundo(self)

    @contextmanager
    def connection(self):
        """Context Manager unificado para obter uma conexão segura do pool."""
        conn = self._pool.get(block=True)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._pool.put(conn)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Inicializa o Pool de conexões
        for _ in range(self._pool.maxsize):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Habilita o modo WAL para altíssima concorrência leitura/escrita
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._pool.put(conn)

        # Cria as tabelas se não existirem
        with self.connection() as conn:
            cursor = conn.cursor()
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            cursor.executescript(schema_sql)

            self._migrar_colunas_ausentes(conn)

    def _migrar_colunas_ausentes(self, conn) -> None:
        """Adiciona com ALTER TABLE as colunas que `COLUNAS_ESPERADAS` declara e a
        tabela não tem. Substitui os 26 fallbacks `if 'x' in row.keys()` espalhados
        pelos carregadores (R-E03): o banco passa a ficar correto uma vez, em vez de
        ser remendado a cada leitura."""
        cursor = conn.cursor()
        for tabela, colunas in self.COLUNAS_ESPERADAS.items():
            existentes = {row[1] for row in cursor.execute(f"PRAGMA table_info({tabela})").fetchall()}
            for nome, tipo_sql in colunas:
                if nome not in existentes:
                    cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo_sql}")
