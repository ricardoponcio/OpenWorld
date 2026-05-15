from flask import Flask, render_template, jsonify
import sqlite3
import os
import sys
import json

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

        # Mapeamento de Coordenadas
        locais_rows = safe_query(conn, 'SELECT id, coordenadas FROM locais')
        if not locais_rows: warnings.append("Tabela 'locais' ausente.")
        mapa_coords = {r['id']: json.loads(r['coordenadas']) if r['coordenadas'] else [0,0] for r in locais_rows}

        # NPCs
        npcs_rows = safe_query(conn, 'SELECT * FROM npcs')
        if not npcs_rows: warnings.append("Tabela 'npcs' ausente.")
        npcs = []
        for r in npcs_rows:
            npcs.append({
                "id": r['id'], "nome": r['nome'], "profissao": r['profissao'],
                "acao": r['acao_atual'], "coords": mapa_coords.get(r['localizacao_atual_id'], [0,0]),
                "status": {"e": r['energia'], "f": r['fome'], "s": r['social'], "d": formatar_moeda(r['dinheiro_total_pc'])}
            })

        # Relacionamentos
        rel_rows = safe_query(conn, 'SELECT * FROM relacionamentos WHERE afinidade != 0')
        rels = [{"a": r['npc_a_id'], "b": r['npc_b_id'], "af": r['afinidade'], "v": r['vinculo']} for r in rel_rows]

        # Meta
        meta_hora = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'hora_simulada'").fetchone()
        meta_pausa = conn.execute("SELECT valor FROM mundo_meta WHERE chave = 'simulacao_pausada'").fetchone()
        
        # Eventos
        ev_rows = safe_query(conn, 'SELECT * FROM eventos ORDER BY timestamp DESC LIMIT 15')
        eventos = [{"t": r['timestamp'], "r": r['resumo_estruturado']} for r in ev_rows]

        conn.close()
        return jsonify({
            "h": meta_hora['valor'] if meta_hora else "Sincronizando...",
            "p": meta_pausa['valor'] == "1" if meta_pausa else False,
            "npcs": npcs,
            "rels": rels,
            "evs": eventos,
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

if __name__ == '__main__':

    app.run(debug=True, host='0.0.0.0', port=5000)
