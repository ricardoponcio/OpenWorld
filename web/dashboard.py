from flask import Flask, render_template, jsonify
import sqlite3
import os
import sys
import json
from datetime import datetime

# Importações de módulos do projeto
from web.composed_routes import composed_bp


# Carregar config.json globalmente
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.json'))
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Adicionar a raiz do projeto ao path para importar a engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__, template_folder='templates')
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def formatar_moeda(total_pc):
    po = total_pc // 1000
    resto_pp = total_pc % 1000
    pp = resto_pp // 100
    pc = resto_pp % 100
    parts = []
    if po > 0: parts.append(f"{po}po")
    if pp > 0: parts.append(f"{pp}pp")
    if pc > 0 or not parts: parts.append(f"{pc}pc")
    return ", ".join(parts)

@app.route('/')
def index():
    return render_template('index.html')

def safe_query(conn, query, params=(), default=[]):
    """Executa uma query e retorna o padrão se a tabela não existir."""
    try:
        return conn.execute(query, params).fetchall()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print(f"⚠️ Aviso: Tabela não encontrada na query: {query}")
            return default
        raise e

@app.route('/api/init')
def get_init():
    try:
        conn = get_db_connection()
        locais_rows = safe_query(conn, 'SELECT id, nome, tipo, coordenadas FROM locais')
        locais = []
        for r in locais_rows:
            locais.append({
                "id": r['id'], "nome": r['nome'], "tipo": r['tipo'],
                "coords": json.loads(r['coordenadas']) if r['coordenadas'] else [0,0]
            })

        meta_mapa = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'mapa_terreno'").fetchone()
        mapa_terreno = json.loads(meta_mapa['valor']) if meta_mapa else []
        
        conn.close()
        return jsonify({"mapa": mapa_terreno, "locais": locais})
    except Exception as e:
        return jsonify({"error": f"Erro de Inicialização: {str(e)}"}), 500

@app.route('/api/update')
def get_update():
    try:
        conn = get_db_connection()
        warnings = []

        # Obter data simulada atual
        meta_hora = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'hora_simulada_iso'").fetchone()
        data_simulada_iso = meta_hora['valor'] if meta_hora else '1200-01-01T06:00:00'
        data_simulada = datetime.fromisoformat(data_simulada_iso)

        # Locais Dinâmicos
        loc_rows = safe_query(conn, 'SELECT id, nome, tipo, status, integridade, coordenadas FROM locais')
        mapa_coords = {}
        locs = {}
        for r in loc_rows:
            coords = json.loads(r['coordenadas']) if r['coordenadas'] else [0,0]
            mapa_coords[r['id']] = coords
            locs[r['id']] = {
                "n": r['nome'], "t": r['tipo'], "c": coords,
                "s": r['status'], "i": r['integridade']
            }

        # Carregar limiar de morte da config
        cfg_bio = config.get("biologia_e_sociedade", {})
        limiar_morte = cfg_bio.get("crescimento_dias_idoso_para_morte", 12)

        # NPCs
        npcs_rows = safe_query(conn, 'SELECT id, nome, profissao, acao_atual, localizacao_atual_id, energia, fome, social, dinheiro_total_pc, saude, humor, genero, estagio_vida, data_nascimento, pai_id, mae_id, estado_civil, conjuge_id, gravidez_ticks FROM npcs')
        if not npcs_rows: warnings.append("Tabela 'npcs' ausente.")
        npcs = []
        for r in npcs_rows:
            idade_anos = 0
            dn_raw = r['data_nascimento']
            if dn_raw:
                try:
                    dt_str = dn_raw.replace(' ', 'T')
                    birth = datetime.fromisoformat(dt_str)
                    idade_dias = (data_simulada - birth).days
                    idade_anos = int((idade_dias / limiar_morte) * 80.0)
                except Exception:
                    pass

            npcs.append({
                "id": r['id'], "nome": r['nome'], "profissao": r['profissao'],
                "acao": r['acao_atual'], "coords": mapa_coords.get(r['localizacao_atual_id'], [0,0]),
                "loc_id": r['localizacao_atual_id'],
                "status": {
                    "e": r['energia'], "f": r['fome'], "s": r['social'], 
                    "d": formatar_moeda(r['dinheiro_total_pc']),
                    "h": r['saude'], "m": r['humor']
                },
                "bio": {
                    "g": r['genero'], "ev": r['estagio_vida'],
                    "dn": r['data_nascimento'], "pai": r['pai_id'],
                    "mae": r['mae_id'], "ec": r['estado_civil'],
                    "cj": r['conjuge_id'], "gr": r['gravidez_ticks'],
                    "idade": idade_anos
                }
            })

        # Evento Global Ativo
        evg_row = safe_query(conn, 'SELECT titulo, descricao, tipo FROM eventos_globais WHERE ticks_restantes > 0 LIMIT 1')
        evg = {"t": evg_row[0]['titulo'], "d": evg_row[0]['descricao'], "tp": evg_row[0]['tipo']} if evg_row else None

        # Meta e Velocidade
        meta_hora = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'hora_simulada'").fetchone()
        meta_pausa = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'simulacao_pausada'").fetchone()
        meta_vel = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'velocidade_simulacao'").fetchone()
        
        # Eventos Unificados
        ev_rows = safe_query(conn, 'SELECT timestamp, resumo_estruturado FROM eventos ORDER BY timestamp DESC LIMIT 15')
        evg_rows = safe_query(conn, 'SELECT timestamp_criacao, titulo FROM eventos_globais ORDER BY timestamp_criacao DESC LIMIT 5')
        
        cronicas = [{"t": r['timestamp'], "r": r['resumo_estruturado'], "type": "npc"} for r in ev_rows]
        for eg in evg_rows:
            cronicas.append({"t": eg['timestamp_criacao'], "r": f"📢 EVENTO: {eg['titulo']}", "type": "global"})
        
        cronicas = sorted(cronicas, key=lambda x: x['t'], reverse=True)[:20]

        conn.close()
        return jsonify({
            "h": meta_hora['valor'] if meta_hora else "Sincronizando...",
            "p": meta_pausa['valor'] == "1" if meta_pausa else False,
            "v": float(meta_vel['valor']) if meta_vel else 1.0,
            "npcs": npcs,
            "evs": cronicas,
            "locs": locs,
            "evg": evg,
            "warnings": warnings
        })



    except Exception as e:
        return jsonify({"error": f"Erro de Sincronização: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/toggle_pause', methods=['POST'])
def toggle_pause():
    try:
        conn = get_db_connection()
        # Buscar estado atual
        row = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'simulacao_pausada'").fetchone()
        novo_estado = "1" if not row or row['valor'] == "0" else "0"
        
        conn.execute("INSERT OR REPLACE INTO mundo_meta (chave, valor) VALUES ('simulacao_pausada', ?)", (novo_estado,))
        conn.commit()
        conn.close()
        return jsonify({"pausado": novo_estado == "1"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/set_speed/<speed>')
def set_speed(speed):
    try:
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO mundo_meta (chave, valor) VALUES ('velocidade_simulacao', ?)", (speed,))
        conn.commit()
        conn.close()
        return jsonify({"velocidade": speed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/npc_logs/<npc_id>')
def get_npc_logs(npc_id):
    try:
        conn = get_db_connection()
        logs_rows = safe_query(conn, 'SELECT timestamp, level, message FROM npc_logs WHERE npc_id = ? ORDER BY id DESC LIMIT 100', (npc_id,))
        logs = [{"t": r['timestamp'], "l": r['level'], "m": r['message']} for r in logs_rows]
        conn.close()
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/npc_rels/<npc_id>')
def get_npc_rels(npc_id):
    try:
        conn = get_db_connection()
        rel_rows = safe_query(conn, 'SELECT npc_b_id, afinidade, vinculo FROM relacionamentos WHERE npc_a_id = ? AND afinidade != 0', (npc_id,))
        rels = [{"b": r['npc_b_id'], "af": r['afinidade'], "v": r['vinculo']} for r in rel_rows]
        conn.close()
        return jsonify({"rels": rels})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --- REGISTRO DO CARTÓGRAFO PRO (MÓDULO SEPARADO) ---
app.register_blueprint(composed_bp)

if __name__ == '__main__':


    app.run(debug=True, host='0.0.0.0', port=5000)
