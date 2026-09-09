import sqlite3
import json
import os
import queue
from contextlib import contextmanager
from .models import NPC, Local, Evento, Acao, EstadoCivil, CategoriaSistema
from .logger import WorldLogger

class DatabaseManager:
    def __init__(self, db_path="database/openworld.db", pool_size=5):
        self.db_path = db_path
        self._pool = queue.Queue(maxsize=pool_size)
        self._init_db()

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

            # Inserir Mapeamentos Padrão (IA -> Sistema Técnico)
            mapeamentos = [
                ('padaria', CategoriaSistema.COMERCIO.value), ('loja', CategoriaSistema.COMERCIO.value), ('mercado', CategoriaSistema.COMERCIO.value),
                ('taberna', CategoriaSistema.SOCIAL.value), ('taverna', CategoriaSistema.SOCIAL.value), ('estalagem', CategoriaSistema.SOCIAL.value), ('prédio social', CategoriaSistema.SOCIAL.value), ('publico', CategoriaSistema.SOCIAL.value),
                ('hospital', CategoriaSistema.SAUDE.value), ('clínica', CategoriaSistema.SAUDE.value),
                ('escola', CategoriaSistema.EDUCACAO.value), ('biblioteca', CategoriaSistema.EDUCACAO.value), ('universidade', CategoriaSistema.EDUCACAO.value),
                ('quartel', CategoriaSistema.MILITAR.value), ('guarda', CategoriaSistema.MILITAR.value), ('torre', CategoriaSistema.MILITAR.value),
                ('fazenda', CategoriaSistema.AGRICULTURA.value), ('campo', CategoriaSistema.AGRICULTURA.value), ('pomar', CategoriaSistema.AGRICULTURA.value),
                ('mina', CategoriaSistema.INDUSTRIA.value), ('forja', CategoriaSistema.INDUSTRIA.value), ('oficina', CategoriaSistema.INDUSTRIA.value), ('fabrica', CategoriaSistema.INDUSTRIA.value)
            ]
            cursor.executemany("INSERT OR IGNORE INTO mapeamento_categorias_trabalho VALUES (?, ?)", mapeamentos)

    def carregar_mapeamento_categorias_trabalho(self) -> dict:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT termo, categoria_sistema FROM mapeamento_categorias_trabalho')
            rows = cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    def salvar_evento_global(self, ev_id, titulo, desc, tipo, loc_id, mods_json, duracao):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO eventos_globais 
                              VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                           (ev_id, titulo, desc, tipo, loc_id, mods_json, duracao))

    def carregar_eventos_globais_ativos(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM eventos_globais WHERE ticks_restantes > 0')
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def salvar_meta(self, chave: str, valor: str):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO mundo_meta VALUES (?, ?)', (chave, valor))

    def carregar_meta(self, chave: str) -> str:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT valor FROM mundo_meta WHERE chave = ?', (chave,))
            row = cursor.fetchone()
            return row[0] if row else None

    def salvar_continente(self, uuid: str, nome: str, area_real_km2: float):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO continentes (uuid, nome, area_real_km2) VALUES (?, ?, ?)', 
                           (uuid, nome, area_real_km2))

    def salvar_cidade(self, continente_uuid: str, nome: str, tamanho: str, tipo: str, x_global: int, y_global: int) -> int:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO cidades (continente_uuid, nome, tamanho, tipo, x_global, y_global) VALUES (?, ?, ?, ?, ?, ?)', 
                           (continente_uuid, nome, tamanho, tipo, x_global, y_global))
            return cursor.lastrowid

    def carregar_cidades(self) -> list:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cidades')
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def salvar_local(self, local: Local):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO locais 
                              (id, nome, tipo, cidade_id, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                local.id, local.nome, local.tipo, local.cidade_id, local.categoria, local.descricao, 
                json.dumps(local.coordenadas), local.status, local.integridade,
                local.capacidade, local.salario_base
            ))

    def carregar_locais(self) -> dict:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM locais')
            rows = cursor.fetchall()
            locais = {}
            for row in rows:
                locais[row['id']] = Local(
                    id=row['id'], nome=row['nome'], tipo=row['tipo'], 
                    cidade_id=row['cidade_id'] if 'cidade_id' in row.keys() else None,
                    categoria=row['categoria'] if 'categoria' in row.keys() else 'generic',
                    descricao=row['descricao'], coordenadas=json.loads(row['coordenadas']),
                    status=row['status'] if 'status' in row.keys() else 1,
                    integridade=row['integridade'] if 'integridade' in row.keys() else 100,
                    capacidade=row['capacidade'] if 'capacidade' in row.keys() else 5,
                    salario_base=row['salario_base'] if 'salario_base' in row.keys() else 100
                )
            return locais

    def salvar_npc(self, npc: NPC):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO npcs                           (id, nome, profissao, profissao_id, cidade_id, casa_id, local_trabalho_id, localizacao_atual_id, 
                               acao_atual, energia, dinheiro_total_pc, social, fome, saude, humor, 
                               genero, estagio_vida, data_nascimento, estado_civil, conjuge_id, pai_id, mae_id, genealogia, relacionamentos, memoria_eventos, gravidez_ticks)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                npc.id, npc.nome, npc.profissao, npc.profissao_id, npc.cidade_id, npc.casa_id, npc.local_trabalho_id,
                npc.localizacao_atual_id, npc.acao_atual.value, npc.energia, npc.dinheiro_total_pc,
                npc.social, npc.fome, npc.saude, npc.humor, 
                npc.genero, npc.estagio_vida, npc.data_nascimento, npc.estado_civil, npc.conjuge_id, npc.pai_id, npc.mae_id,
                json.dumps(npc.genealogia), json.dumps(npc.relacionamentos), json.dumps(npc.memoria_eventos),
                npc.gravidez_ticks
            ))

    def _safe_json_load(self, data, default):
        try:
            return json.loads(data) if data else default
        except:
            return default

    def carregar_npcs(self) -> list:
        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT * FROM npcs')
                rows = cursor.fetchall()
                npcs = []
                for r in rows:
                    npc = NPC(
                        id=r['id'], nome=r['nome'], profissao=r['profissao'], 
                        profissao_id=r['profissao_id'] if 'profissao_id' in r.keys() else 'ocioso',
                        cidade_id=r['cidade_id'] if 'cidade_id' in r.keys() else None,
                        casa_id=r['casa_id'], 
                        local_trabalho_id=r['local_trabalho_id'], localizacao_atual_id=r['localizacao_atual_id'], 
                        acao_atual=Acao(r['acao_atual']) if 'acao_atual' in r.keys() else Acao.OCIOSO, 
                        energia=float(r['energia']) if r['energia'] is not None else 100.0,
                        dinheiro_total_pc=float(r['dinheiro_total_pc']) if r['dinheiro_total_pc'] is not None else 500.0,
                        social=float(r['social']) if r['social'] is not None else 100.0,
                        fome=float(r['fome']) if r['fome'] is not None else 0.0,
                        saude=int(r['saude']) if 'saude' in r.keys() and r['saude'] is not None else 100,
                        humor=r['humor'] if 'humor' in r.keys() else 'Neutro',
                        genero=r['genero'] if 'genero' in r.keys() else 'M',
                        estagio_vida=r['estagio_vida'] if 'estagio_vida' in r.keys() else 'adulto',
                        data_nascimento=r['data_nascimento'] if 'data_nascimento' in r.keys() else '',
                        estado_civil=r['estado_civil'] if 'estado_civil' in r.keys() else EstadoCivil.SOLTEIRO.value,
                        conjuge_id=r['conjuge_id'] if 'conjuge_id' in r.keys() else '',
                        pai_id=r['pai_id'] if 'pai_id' in r.keys() else '',
                        mae_id=r['mae_id'] if 'mae_id' in r.keys() else '',
                        genealogia=self._safe_json_load(r['genealogia'], []), 
                        relacionamentos=self._safe_json_load(r['relacionamentos'], {}),
                        memoria_eventos=self._safe_json_load(r['memoria_eventos'], []),
                        gravidez_ticks=r['gravidez_ticks'] if 'gravidez_ticks' in r.keys() and r['gravidez_ticks'] is not None else 0)

                    npcs.append(npc)
                return npcs
            except Exception as e:
                WorldLogger.error(f"Erro ao carregar NPCs: {e}")
                return []

    def salvar_evento(self, evento: Evento):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO eventos VALUES (?, ?, ?, ?, ?, ?, ?)', (
                evento.id, evento.timestamp, evento.local_id, json.dumps(evento.envolvidos), 
                evento.tipo_evento, evento.modificador_afinidade, evento.resumo_estruturado
            ))

    def salvar_relacionamento(self, a_id: str, b_id: str, afinidade: int, vinculo: str):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                           (a_id, b_id, afinidade, vinculo))
            cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                           (b_id, a_id, afinidade, vinculo))

    # ------------------------------------------------------------------
    # Modo Mestre de IA (Frente 5)
    # ------------------------------------------------------------------

    def salvar_mensagem_mestre(self, autor: str, mensagem: str, acoes_propostas: list = None) -> int:
        """Persiste um turno de conversa (jogador ou mestre) e retorna o id gerado."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO mestre_conversas (autor, mensagem, acoes_propostas, aplicada) VALUES (?, ?, ?, 0)',
                (autor, mensagem, json.dumps(acoes_propostas) if acoes_propostas else None)
            )
            return cursor.lastrowid

    def carregar_historico_mestre(self, limite: int = 50) -> list:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM mestre_conversas ORDER BY id DESC LIMIT ?', (limite,))
            rows = [dict(r) for r in cursor.fetchall()]
            return list(reversed(rows))

    def carregar_mensagem_mestre(self, conversa_id: int) -> dict:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM mestre_conversas WHERE id = ?', (conversa_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def marcar_mestre_aplicada(self, conversa_id: int):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE mestre_conversas SET aplicada = 1 WHERE id = ?', (conversa_id,))
