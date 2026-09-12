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
from web.banco import obter_db
from config import get_config, cfg_get
from engine.models import MetaChave
from engine.tempo import RelogioMundo

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

@app.route('/api/init')
def get_init():
    try:
        locais_por_id = _tabela_ou_vazio(lambda: db.locais.carregar_por_id(), default={})
        locais = [{"id": l.id, "nome": l.nome, "tipo": l.tipo, "coords": l.coordenadas} for l in locais_por_id.values()]

        meta_mapa = db.meta.carregar(MetaChave.MAPA_TERRENO)
        mapa_terreno = json.loads(meta_mapa) if meta_mapa else []

        return jsonify({"mapa": mapa_terreno, "locais": locais})
    except Exception as e:
        return jsonify({"error": f"Erro de Inicialização: {str(e)}"}), 500

@app.route('/api/update')
def get_update():
    try:
        warnings = []

        # Obter data simulada atual
        data_simulada_iso = db.meta.carregar(MetaChave.HORA_ISO) or RelogioMundo.HORA_INICIAL_PADRAO_ISO
        data_simulada = datetime.fromisoformat(data_simulada_iso)

        # Locais Dinâmicos
        locais_por_id = _tabela_ou_vazio(lambda: db.locais.carregar_por_id(), default={})
        mapa_coords = {}
        locs = {}
        for l in locais_por_id.values():
            mapa_coords[l.id] = l.coordenadas
            locs[l.id] = {
                "n": l.nome, "t": l.tipo, "c": l.coordenadas,
                "s": l.status, "i": l.integridade
            }

        # Carregar limiar de morte da config (mesma chave/resolver que a engine usa —
        # antes este arquivo tinha seu próprio default (12), divergente do default
        # usado em builder/populate.py (120), ver docs/AUDITORIA_HARDCODE.md)
        limiar_morte = cfg_get(config, "biologia_e_sociedade", "crescimento_dias_idoso_para_morte")

        # NPCs
        npcs_rows = _tabela_ou_vazio(lambda: db.npcs.listar_projecao_dashboard(), default=[])
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
        evg_dict = _tabela_ou_vazio(lambda: db.eventos.buscar_global_ativo(), default=None)
        evg = {"t": evg_dict['titulo'], "d": evg_dict['descricao'], "tp": evg_dict['tipo']} if evg_dict else None

        # Meta e Velocidade
        hora_formatada = db.meta.carregar(MetaChave.HORA_FORMATADA)
        pausado_raw = db.meta.carregar(MetaChave.SIMULACAO_PAUSADA)
        velocidade_raw = db.meta.carregar(MetaChave.VELOCIDADE)

        # Eventos Unificados
        ev_rows = _tabela_ou_vazio(lambda: db.eventos.listar_recentes(15), default=[])
        evg_rows = _tabela_ou_vazio(lambda: db.eventos.listar_globais_recentes(5), default=[])

        cronicas = [{"t": r['timestamp'], "r": r['resumo_estruturado'], "type": "npc"} for r in ev_rows]
        for eg in evg_rows:
            cronicas.append({"t": eg['timestamp_criacao'], "r": f"📢 EVENTO: {eg['titulo']}", "type": "global"})

        cronicas = sorted(cronicas, key=lambda x: x['t'], reverse=True)[:20]

        return jsonify({
            "h": hora_formatada if hora_formatada else "Sincronizando...",
            "p": pausado_raw == "1" if pausado_raw is not None else False,
            "v": float(velocidade_raw) if velocidade_raw else 1.0,
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
