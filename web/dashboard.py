from flask import Flask, render_template, jsonify
import sqlite3
import os
import sys
import json

# Adicionar a raiz do projeto ao path para importar a engine/config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importações de módulos do projeto
from web.rotas import registrar_blueprints
from web.mestre_routes import mestre_bp
from web.banco import obter_db
from config import get_config
from engine.models import MetaChave

# Config único do projeto (config.json, via config/) — não lê mais o arquivo por conta própria
config = get_config()

app = Flask(__name__, template_folder='templates')

# Instância única de processo (R-E01/R-E02) — antes cada rota abria sua própria
# `sqlite3.connect(DB_PATH)` crua por requisição; agora todo SQL mora nos
# repositórios de `db` (`db.npcs`, `db.locais`, `db.meta`, `db.eventos`, ...), e a
# instância é compartilhada com `mestre_routes.py` via `web/banco.py`.
db = obter_db()


def _tabela_ou_vazio(fn, default):
    """Executa `fn()` e cai no `default` se a tabela consultada ainda não existir —
    mesma proteção que `safe_query` dava linha a linha, agora em torno de uma chamada
    de repositório (o SQL em si não vive mais aqui, ver R-E01)."""
    try:
        return fn()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print(f"⚠️ Aviso: tabela ausente: {e}")
            return default
        raise


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/init')
def get_init():
    try:
        # P01 (docs/16_PLANO_PAINEL_E_IA.md): `locais` (18 mil) saiu — staticData
        # nunca usava ("Old map generation removed", ver histórico do frontend);
        # ninguém mais lê `l.coords`/`l.tipo` daqui.
        meta_mapa = db.meta.carregar(MetaChave.MAPA_TERRENO)
        mapa_terreno = json.loads(meta_mapa) if meta_mapa else []

        return jsonify({"mapa": mapa_terreno})
    except Exception as e:
        return jsonify({"error": f"Erro de Inicialização: {str(e)}"}), 500

@app.route('/api/toggle_pause', methods=['POST'])
def toggle_pause():
    try:
        atual = db.meta.carregar(MetaChave.SIMULACAO_PAUSADA)
        novo_estado = "1" if not atual or atual == "0" else "0"
        db.meta.salvar(MetaChave.SIMULACAO_PAUSADA, novo_estado)
        return jsonify({"pausado": novo_estado == "1"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/set_speed/<speed>')
def set_speed(speed):
    try:
        db.meta.salvar(MetaChave.VELOCIDADE, speed)
        return jsonify({"velocidade": speed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/npc_logs/<npc_id>')
def get_npc_logs(npc_id):
    try:
        logs_rows = _tabela_ou_vazio(lambda: db.npcs.listar_logs(npc_id, 100), default=[])
        logs = [{"t": r['timestamp'], "l": r['level'], "m": r['message']} for r in logs_rows]
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/npc_rels/<npc_id>')
def get_npc_rels(npc_id):
    try:
        rel_rows = _tabela_ou_vazio(lambda: db.npcs.listar_relacionamentos(npc_id), default=[])
        rels = [{"b": r['npc_b_id'], "af": r['afinidade'], "v": r['vinculo']} for r in rel_rows]
        return jsonify({"rels": rels})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --- REGISTRO DO CARTÓGRAFO PRO (MÓDULO SEPARADO) ---
registrar_blueprints(app)
app.register_blueprint(mestre_bp)

if __name__ == '__main__':


    app.run(debug=True, host='0.0.0.0', port=5000)
