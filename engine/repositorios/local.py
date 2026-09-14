import json
from ..models import Local, CategoriaLocal, MetaChave


class RepositorioLocal:
    """SQL de locais e da tabela de mapeamento categoria->sistema (R-E01) — antes
    espalhado entre `DatabaseManager` e `engine/mechanics/market.py`/`mestre.py`."""

    def __init__(self, db):
        self.db = db

    def carregar_por_id(self) -> dict:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM locais')
            rows = cursor.fetchall()
            locais = {}
            for row in rows:
                locais[row['id']] = Local(
                    id=row['id'], nome=row['nome'], tipo=row['tipo'],
                    cidade_id=row['cidade_id'],
                    categoria=row['categoria'] or CategoriaLocal.GENERIC.value,
                    descricao=row['descricao'], coordenadas=json.loads(row['coordenadas']),
                    status=row['status'],
                    integridade=row['integridade'],
                    capacidade=row['capacidade'],
                    salario_base=row['salario_base'],
                    tipo_local=row['tipo_local'] or '',
                    bairro=row['bairro'] or '',
                    dono_npc_id=row['dono_npc_id'] or ''
                )
            return locais

    def salvar(self, local: Local):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO locais
                              (id, nome, tipo, cidade_id, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base, tipo_local, bairro, dono_npc_id)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                local.id, local.nome, local.tipo, local.cidade_id, local.categoria, local.descricao,
                json.dumps(local.coordenadas), local.status, local.integridade,
                local.capacidade, local.salario_base, local.tipo_local, local.bairro, local.dono_npc_id
            ))

    def salvar_em_lote(self, locais: list) -> None:
        """T02 (docs/PLANO_CIDADE_VIVA.md): importação inicial de uma cidade inteira —
        uma transação só, em vez de um commit por edifício (24.423 locais viravam
        24.423 commits num reset)."""
        if not locais:
            return
        with self.db.connection() as conn:
            conn.cursor().executemany(
                '''INSERT OR REPLACE INTO locais
                   (id, nome, tipo, cidade_id, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base, tipo_local, bairro, dono_npc_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [(l.id, l.nome, l.tipo, l.cidade_id, l.categoria, l.descricao,
                  json.dumps(l.coordenadas), l.status, l.integridade,
                  l.capacidade, l.salario_base, l.tipo_local, l.bairro, l.dono_npc_id)
                 for l in locais])

    def criar(self, id: str, nome: str, tipo: str, cidade_id, categoria: str, descricao: str,
              coordenadas: list, status: int = 1, integridade: int = 100, capacidade: int = 5,
              salario_base: int = 100):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO locais (id, nome, tipo, cidade_id, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (id, nome, tipo, cidade_id, categoria, descricao, json.dumps(coordenadas),
                 status, integridade, capacidade, salario_base)
            )
            self._incrementar_versao(cursor)

    def desativar(self, local_id: str):
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE locais SET status = 0, integridade = 0 WHERE id = ?", (local_id,))
            self._incrementar_versao(cursor)

    @staticmethod
    def _incrementar_versao(cursor) -> None:
        """M01 (docs/PLANO_POPULACAO_E_ESCALA.md): incrementa `MetaChave.LOCAIS_VERSAO`
        na MESMA transação (mesmo cursor/conexão) da escrita do local — é o que
        `run_simulation.py` usa pra saber, sem recarregar tudo, que precisa chamar
        `recarregar_locais()`."""
        cursor.execute(
            "INSERT INTO mundo_meta (chave, valor) VALUES (?, '1') "
            "ON CONFLICT(chave) DO UPDATE SET valor = CAST(valor AS INTEGER) + 1",
            (MetaChave.LOCAIS_VERSAO.value,))

    def coordenadas_ocupadas(self) -> set:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT coordenadas FROM locais")
            return {tuple(json.loads(r["coordenadas"])) for r in cursor.fetchall()}

    def listar_ativos_resumo(self, cidade_id) -> list:
        """Projeção enxuta (id, nome, tipo) de locais ativos DA CIDADE, usada pelo
        contexto do Modo Mestre — evita carregar e desserializar `coordenadas` de
        toda cidade (`carregar_por_id`) só para montar uma lista textual pro prompt
        da IA. M01 (docs/PLANO_MUNDO_CRIVEL.md, Bloco M): filtra por cidade e
        exclui residências — a contagem agregada (`contar_residencias_ativas`) é o
        que o contexto precisa, não 22.624 linhas de "Residência X"."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, tipo FROM locais WHERE status = 1 AND cidade_id = ? AND categoria != ?",
                (cidade_id, CategoriaLocal.RESIDENCIA.value))
            return cursor.fetchall()

    def contar_residencias_ativas(self, cidade_id) -> int:
        """M01: a contagem agregada que substitui a lista de residências no
        contexto do Mestre."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT COUNT(*) AS n FROM locais WHERE status = 1 AND cidade_id = ? AND categoria = ?",
                (cidade_id, CategoriaLocal.RESIDENCIA.value)).fetchone()
            return row["n"] if row else 0

    def buscar_por_cidade(self, cidade_id) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nome, tipo, categoria, coordenadas FROM locais WHERE cidade_id = ?', (cidade_id,))
            return cursor.fetchall()

    # ------------------------------------------------------------------
    # Bootstrap do Mercado de Trabalho (categorização de locais gerados pela IA)
    # ------------------------------------------------------------------

    def buscar_genericos(self) -> list:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, tipo FROM locais WHERE categoria = 'generic' OR categoria IS NULL")
            return cursor.fetchall()

    def atualizar_categoria(self, local_id: str, categoria: str, capacidade: int, salario_base: int):
        with self.db.connection() as conn:
            conn.cursor().execute(
                "UPDATE locais SET categoria = ?, capacidade = ?, salario_base = ? WHERE id = ?",
                (categoria, capacidade, salario_base, local_id)
            )

    def buscar_vagas_disponiveis(self, cidade_id, categorias_empregadoras: list) -> list:
        """V02 (docs/PLANO_MUNDO_CRIVEL.md, Bloco V): vaga é sempre da PRÓPRIA cidade
        (`cidade_id`) e de uma categoria EMPREGADORA (`urbanismo.
        categorias_empregadoras`) — nunca mais filtrado por `tipo != 'Casa'`, que
        deixava passar 'Residência' (tipo real é 'Casa' desde V01) e qualquer cidade:
        87,4% das vagas do mundo medido eram residências, e 665 de 705 contratados
        trabalhavam fora da própria cidade.

        X02: a ocupação era uma SUBCONSULTA CORRELACIONADA (uma varredura da tabela
        `npcs` inteira POR LINHA de `locais`) — 11,7 s medidos com 50 mil NPCs e
        ~1.200 locais/cidade. Virou um `LEFT JOIN` com um `GROUP BY` já filtrado pela
        mesma cidade — uma varredura de `npcs` por CHAMADA, não por linha de local."""
        placeholders = ",".join("?" for _ in categorias_empregadoras)
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT l.id, l.categoria, l.capacidade, COALESCE(o.ocupacao, 0) as ocupacao
                FROM locais l
                LEFT JOIN (
                    SELECT local_trabalho_id, COUNT(*) as ocupacao
                    FROM npcs
                    WHERE saude > 0 AND cidade_id = ?
                    GROUP BY local_trabalho_id
                ) o ON o.local_trabalho_id = l.id
                WHERE l.status = 1 AND l.cidade_id = ? AND l.categoria IN ({placeholders})
            """, (cidade_id, cidade_id, *categorias_empregadoras))
            return cursor.fetchall()

    def cidade_tem_local_social(self, cidade_id) -> bool:
        """M03 (docs/PLANO_MUNDO_CRIVEL.md, Bloco M): a cidade tem ao menos uma
        taverna/praça ativa — o invariante 5/9 de V05 (audit_mundo.py, fora do
        runtime), reimplementado aqui porque o Mestre roda no processo web."""
        with self.db.connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT 1 FROM locais WHERE cidade_id = ? AND status = 1 AND categoria IN (?, ?) LIMIT 1",
                (cidade_id, CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value)).fetchone()
            return row is not None

    def carregar_mapeamento_categorias_trabalho(self) -> dict:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT termo, categoria_sistema FROM mapeamento_categorias_trabalho')
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    def seed_mapeamento_categorias(self, pares: list):
        """`pares` é uma lista de `(termo, categoria_sistema)` — ver
        `engine/repositorios/seed.py::SemeadorDeDominio` (R-E04)."""
        with self.db.connection() as conn:
            conn.cursor().executemany(
                "INSERT OR IGNORE INTO mapeamento_categorias_trabalho VALUES (?, ?)", pares)
