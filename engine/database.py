import sqlite3
import json
import os
from .models import NPC, Local, Evento, Acao

class DatabaseManager:
    def __init__(self, db_path="database/openworld.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de NPCs (Ajustada para dinheiro_total_pc)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS npcs (
                id TEXT PRIMARY KEY,
                nome TEXT,
                profissao TEXT,
                casa_id TEXT,
                local_trabalho_id TEXT,
                localizacao_atual_id TEXT,
                acao_atual TEXT,
                energia REAL,
                dinheiro_total_pc INTEGER,
                social REAL,
                fome REAL,
                genealogia TEXT,
                relacionamentos TEXT
            )
        ''')
        
        # Tabela de Relacionamentos (SOCIAL)
        cursor.execute('''CREATE TABLE IF NOT EXISTS relacionamentos (
                            npc_a_id TEXT,
                            npc_b_id TEXT,
                            afinidade INTEGER DEFAULT 0,
                            vinculo TEXT DEFAULT 'Conhecido',
                            PRIMARY KEY (npc_a_id, npc_b_id))''')
        
        # Tabela de Locais
        cursor.execute('CREATE TABLE IF NOT EXISTS locais (id TEXT PRIMARY KEY, nome TEXT, tipo TEXT, descricao TEXT, coordenadas TEXT)')
        
        # Tabela de Eventos
        cursor.execute('CREATE TABLE IF NOT EXISTS eventos (id TEXT PRIMARY KEY, timestamp TEXT, local_id TEXT, envolvidos TEXT, tipo_evento TEXT, modificador_afinidade INTEGER, resumo_estruturado TEXT)')

        # Tabela de Meta
        cursor.execute('CREATE TABLE IF NOT EXISTS mundo_meta (chave TEXT PRIMARY KEY, valor TEXT)')
        
        conn.commit()
        conn.close()

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
        cursor.execute('INSERT OR REPLACE INTO locais VALUES (?, ?, ?, ?, ?)', (
            local.id, local.nome, local.tipo, local.descricao, json.dumps(local.coordenadas)
        ))
        conn.commit()
        conn.close()

    def carregar_locais(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM locais')
        rows = cursor.fetchall()
        locais = {}
        for row in rows:
            locais[row['id']] = Local(
                id=row['id'], nome=row['nome'], tipo=row['tipo'], 
                descricao=row['descricao'], coordenadas=json.loads(row['coordenadas'])
            )
        conn.close()
        return locais

    def salvar_npc(self, npc: NPC):

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO npcs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            npc.id, npc.nome, npc.profissao, npc.casa_id, npc.local_trabalho_id,
            npc.localizacao_atual_id, npc.acao_atual.value, npc.energia, npc.dinheiro_total_pc,
            npc.social, npc.fome, json.dumps(npc.genealogia), json.dumps(npc.relacionamentos)
        ))
        conn.commit()
        conn.close()

    def carregar_npcs(self) -> list:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM npcs')
            rows = cursor.fetchall()
            npcs = []
            for row in rows:
                npc = NPC(id=row[0], nome=row[1], profissao=row[2], casa_id=row[3], 
                          local_trabalho_id=row[4], localizacao_atual_id=row[5], 
                          acao_atual=Acao(row[6]), energia=row[7], dinheiro_total_pc=row[8], 
                          social=row[9], fome=row[10], genealogia=json.loads(row[11]), 
                          relacionamentos=json.loads(row[12]))
                npcs.append(npc)
            return npcs
        except sqlite3.OperationalError:
            return [] # Tabela não existe ou colunas erradas (precisa reset)
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

