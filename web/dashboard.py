from flask import Flask, render_template, jsonify
import sqlite3
import os
import sys
import json
from datetime import datetime

# Adicionar a raiz do projeto ao path para importar a engine/config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importações de módulos do projeto
from web.rotas import registrar_blueprints
from web.mestre_routes import mestre_bp
from config import get_config, cfg_get
from engine.models import MetaChave
from engine.tempo import RelogioMundo

# Config único do projeto (config.json, via config/) — não lê mais o arquivo por conta própria
config = get_config()

app = Flask(__name__, template_folder='templates')
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def formatar_moeda(total_pc):
    # Arredonda só na exibição — dinheiro é fracionário desde a Frente 4 (pago a cada tick de 1 min)
    total_pc = int(total_pc)
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

        meta_mapa = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.MAPA_TERRENO.value,)).fetchone()
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
        meta_hora = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.HORA_ISO.value,)).fetchone()
        data_simulada_iso = meta_hora['valor'] if meta_hora else RelogioMundo.HORA_INICIAL_PADRAO_ISO
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

        # Carregar limiar de morte da config (mesma chave/resolver que a engine usa —
        # antes este arquivo tinha seu próprio default (12), divergente do default
        # usado em builder/populate.py (120), ver docs/AUDITORIA_HARDCODE.md)
        limiar_morte = cfg_get(config, "biologia_e_sociedade", "crescimento_dias_idoso_para_morte")

        # NPCs
        npcs_rows = safe_query(conn, 'SELECT id, nome, profissao, acao_atual, localizacao_atual_id, energia, fome, social, dinheiro_total_pc, saude, humor, genero, estagio_vida, data_nascimento, pai_id, mae_id, estado_civil, conjuge_id, gravidez_ticks FROM npcs')
        if not npcs_rows: warnings.append("Tabela 'npcs' ausente.")
        npcs = []
        for r in npcs_rows:
            idade_anos = 0
            dn_raw = r['data_nascimento']
            if dn_raw:
                idade_anos = RelogioMundo.idade_em_anos(dn_raw, data_simulada, limiar_morte)

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
        meta_hora = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.HORA_FORMATADA.value,)).fetchone()
        meta_pausa = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.SIMULACAO_PAUSADA.value,)).fetchone()
        meta_vel = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.VELOCIDADE.value,)).fetchone()
        
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

@app.route('/api/toggle_pause', methods=['POST'])
def toggle_pause():
    try:
        conn = get_db_connection()
        # Buscar estado atual
        row = conn.execute("SELECT valor FROM mundo_meta WHERE chave = ?", (MetaChave.SIMULACAO_PAUSADA.value,)).fetchone()
        novo_estado = "1" if not row or row['valor'] == "0" else "0"
        
        conn.execute("INSERT OR REPLACE INTO mundo_meta (chave, valor) VALUES (?, ?)", (MetaChave.SIMULACAO_PAUSADA.value, novo_estado))
        conn.commit()
        conn.close()
        return jsonify({"pausado": novo_estado == "1"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/set_speed/<speed>')
def set_speed(speed):
    try:
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO mundo_meta (chave, valor) VALUES (?, ?)", (MetaChave.VELOCIDADE.value, speed))
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
registrar_blueprints(app)
app.register_blueprint(mestre_bp)

if __name__ == '__main__':


    app.run(debug=True, host='0.0.0.0', port=5000)
