import sqlite3
import json
import os
from .models import NPC, Local, Evento, Acao, EstadoCivil
from .logger import WorldLogger

class DatabaseManager:
    def __init__(self, db_path="database/openworld.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Carregar esquema SQL externo
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
            
        cursor.executescript(schema_sql)

        # Inserir Mapeamentos Padrão (IA -> Sistema Técnico)
        mapeamentos = [
            ('padaria', 'comercio'), ('loja', 'comercio'), ('mercado', 'comercio'),
            ('taberna', 'social'), ('estalagem', 'social'), ('prédio social', 'social'),
            ('hospital', 'saude'), ('clínica', 'saude'),
            ('escola', 'educacao'), ('biblioteca', 'educacao'), ('universidade', 'educacao'),
            ('quartel', 'militar'), ('guarda', 'militar'), ('torre', 'militar'),
            ('fazenda', 'agricultura'), ('campo', 'agricultura'), ('pomar', 'agricultura'),
            ('mina', 'industria'), ('forja', 'industria'), ('oficina', 'industria'), ('fabrica', 'industria')
        ]
        cursor.executemany("INSERT OR IGNORE INTO mapeamento_categorias_trabalho VALUES (?, ?)", mapeamentos)

        conn.commit()
        conn.close()

    def carregar_mapeamento_categorias_trabalho(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT termo, categoria_sistema FROM mapeamento_categorias_trabalho')
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}



    def salvar_evento_global(self, ev_id, titulo, desc, tipo, loc_id, mods_json, duracao):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO eventos_globais 
                          VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                       (ev_id, titulo, desc, tipo, loc_id, mods_json, duracao))
        conn.commit()
        conn.close()

    def carregar_eventos_globais_ativos(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM eventos_globais WHERE ticks_restantes > 0')
        rows = cursor.fetchall()
        conn.close()
        return rows

    def salvar_meta(self, chave: str, valor: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO mundo_meta VALUES (?, ?)', (chave, valor))
        conn.commit()
        conn.close()

    def carregar_meta(self, chave: str) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT valor FROM mundo_meta WHERE chave = ?', (chave,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def salvar_local(self, local: Local):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO locais 
                          (id, nome, tipo, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            local.id, local.nome, local.tipo, local.categoria, local.descricao, 
            json.dumps(local.coordenadas), local.status, local.integridade,
            local.capacidade, local.salario_base
        ))
        conn.commit()
        conn.close()

    def carregar_locais(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM locais')
        rows = cursor.fetchall()
        locais = {}
        for row in rows:
            locais[row['id']] = Local(
                id=row['id'], nome=row['nome'], tipo=row['tipo'], 
                categoria=row['categoria'] if 'categoria' in row.keys() else 'generic',
                descricao=row['descricao'], coordenadas=json.loads(row['coordenadas']),
                status=row['status'] if 'status' in row.keys() else 1,
                integridade=row['integridade'] if 'integridade' in row.keys() else 100,
                capacidade=row['capacidade'] if 'capacidade' in row.keys() else 5,
                salario_base=row['salario_base'] if 'salario_base' in row.keys() else 100
            )
        conn.close()
        return locais

    def salvar_npc(self, npc: NPC):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO npcs                           (id, nome, profissao, profissao_id, casa_id, local_trabalho_id, localizacao_atual_id, 
                           acao_atual, energia, dinheiro_total_pc, social, fome, saude, humor, 
                           genero, estagio_vida, data_nascimento, estado_civil, conjuge_id, pai_id, mae_id, genealogia, relacionamentos, memoria_eventos, gravidez_ticks)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            npc.id, npc.nome, npc.profissao, npc.profissao_id, npc.casa_id, npc.local_trabalho_id,
            npc.localizacao_atual_id, npc.acao_atual.value, npc.energia, npc.dinheiro_total_pc,
            npc.social, npc.fome, npc.saude, npc.humor, 
            npc.genero, npc.estagio_vida, npc.data_nascimento, npc.estado_civil, npc.conjuge_id, npc.pai_id, npc.mae_id,
            json.dumps(npc.genealogia), json.dumps(npc.relacionamentos), json.dumps(npc.memoria_eventos),
            npc.gravidez_ticks
        ))
        conn.commit()
        conn.close()


    def _safe_json_load(self, data, default):
        try:
            return json.loads(data) if data else default
        except:
            return default

    def carregar_npcs(self) -> list:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM npcs')
            rows = cursor.fetchall()
            npcs = []
            for r in rows:
                npc = NPC(
                    id=r['id'], nome=r['nome'], profissao=r['profissao'], 
                    profissao_id=r['profissao_id'] if 'profissao_id' in r.keys() else 'ocioso',
                    casa_id=r['casa_id'], 
                    local_trabalho_id=r['local_trabalho_id'], localizacao_atual_id=r['localizacao_atual_id'], 
                    acao_atual=Acao(r['acao_atual']) if 'acao_atual' in r.keys() else Acao.OCIOSO, 
                    energia=float(r['energia']) if r['energia'] is not None else 100.0,
                    dinheiro_total_pc=int(r['dinheiro_total_pc']) if r['dinheiro_total_pc'] is not None else 500,
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
        finally:
            conn.close()

    def salvar_evento(self, evento: Evento):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO eventos VALUES (?, ?, ?, ?, ?, ?, ?)', (
            evento.id, evento.timestamp, evento.local_id, json.dumps(evento.envolvidos), 
            evento.tipo_evento, evento.modificador_afinidade, evento.resumo_estruturado
        ))
        conn.commit()
        conn.close()

    def salvar_relacionamento(self, a_id: str, b_id: str, afinidade: int, vinculo: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Salva o par A->B e B->A para facilitar consultas
        cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                       (a_id, b_id, afinidade, vinculo))
        cursor.execute('INSERT OR REPLACE INTO relacionamentos (npc_a_id, npc_b_id, afinidade, vinculo) VALUES (?, ?, ?, ?)',
                       (b_id, a_id, afinidade, vinculo))
        conn.commit()
        conn.close()

