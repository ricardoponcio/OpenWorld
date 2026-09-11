"""
MODULE: mestre_routes.py
FUNÇÃO: Endpoints do Modo Mestre de IA (Frente 5).

DESCRIÇÃO:
    O dashboard Flask não é dono da SimulationEngine (ela roda no processo do
    run_simulation.py) — por isso "avançar o tempo" aqui não tica a engine
    diretamente, só sinaliza via mundo_meta (mesmo padrão já usado por pausa e
    velocidade) e espera o run_simulation.py consumir. Ver docs/ROADMAP.md, Frente 5.
"""
import os
import json
import time
from flask import Blueprint, request, jsonify

from engine.database import DatabaseManager
from engine.mechanics.mestre import MestreManager
from engine.ai import AIGameMasterClient
from engine.models import MetaChave

mestre_bp = Blueprint('mestre', __name__)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))
TEMA_PADRAO = "Fantasia Medieval"


def _get_db():
    return DatabaseManager(DB_PATH)


@mestre_bp.route('/api/mestre/historico')
def get_historico():
    try:
        db = _get_db()
        historico = db.carregar_historico_mestre(50)
        for h in historico:
            h['acoes_propostas'] = json.loads(h['acoes_propostas']) if h['acoes_propostas'] else []
        return jsonify({"historico": historico})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/estado')
def get_estado():
    try:
        db = _get_db()
        restante = int(db.carregar_meta(MetaChave.AVANCAR_MINUTOS) or 0)
        pausado = db.carregar_meta(MetaChave.SIMULACAO_PAUSADA) == "1"
        return jsonify({"pausado": pausado, "avancando": restante > 0, "minutos_restantes": restante})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/mensagem', methods=['POST'])
def post_mensagem():
    try:
        body = request.get_json(force=True) or {}
        mensagem = (body.get('mensagem') or '').strip()
        tema = body.get('tema') or TEMA_PADRAO
        if not mensagem:
            return jsonify({"error": "Mensagem vazia."}), 400

        db = _get_db()
        contexto = MestreManager.montar_contexto(db)
        historico = db.carregar_historico_mestre(20)

        db.salvar_mensagem_mestre('jogador', mensagem)
        resposta = AIGameMasterClient.gerar_resposta_mestre(tema, contexto, historico, mensagem)
        conversa_id = db.salvar_mensagem_mestre('mestre', resposta['narracao'], resposta.get('acoes_propostas') or [])

        return jsonify({
            "conversa_id": conversa_id,
            "narracao": resposta['narracao'],
            "acoes_propostas": resposta.get('acoes_propostas') or [],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/confirmar_acoes', methods=['POST'])
def post_confirmar_acoes():
    """Aplica as ações propostas de uma mensagem do Mestre — só chega aqui depois
    que o jogador confirmou explicitamente na interface. Nunca é chamado sozinho."""
    try:
        body = request.get_json(force=True) or {}
        conversa_id = body.get('conversa_id')
        if not conversa_id:
            return jsonify({"error": "conversa_id é obrigatório."}), 400

        db = _get_db()
        msg = db.carregar_mensagem_mestre(conversa_id)
        if not msg or msg['autor'] != 'mestre':
            return jsonify({"error": "Conversa não encontrada ou não é uma resposta do Mestre."}), 404
        if msg['aplicada']:
            return jsonify({"error": "Estas ações já foram aplicadas."}), 400

        acoes = json.loads(msg['acoes_propostas']) if msg['acoes_propostas'] else []
        resultados = MestreManager.aplicar_acoes(db, acoes)
        db.marcar_mestre_aplicada(conversa_id)

        return jsonify({"aplicado": True, "resultados": resultados})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/avancar_tempo', methods=['POST'])
def post_avancar_tempo():
    """Avança N minutos de jogo (a simulação precisa estar pausada — ver
    run_simulation.py) e devolve uma narração do que aconteceu no período."""
    try:
        body = request.get_json(force=True) or {}
        minutos = int(body.get('minutos', 0))
        tema = body.get('tema') or TEMA_PADRAO
        if minutos <= 0:
            return jsonify({"error": "minutos deve ser positivo."}), 400

        db = _get_db()
        ultimo_rowid = MestreManager.ultimo_rowid_eventos(db)

        # Garante que a simulação está pausada — sem isso, o run_simulation.py nunca
        # olha para mestre_avancar_minutos_restantes (esse contador só é consumido
        # dentro do ramo de pausa do loop).
        db.salvar_meta(MetaChave.SIMULACAO_PAUSADA, "1")
        db.salvar_meta(MetaChave.AVANCAR_MINUTOS, str(minutos))

        # Espera o run_simulation.py consumir o avanço (poll curto). Timeout generoso
        # o bastante mesmo para saltos grandes (medido ~1.2ms/tick na Frente 4).
        timeout = max(5.0, minutos * 0.02)
        inicio = time.time()
        while time.time() - inicio < timeout:
            restante = int(db.carregar_meta(MetaChave.AVANCAR_MINUTOS) or 0)
            if restante <= 0:
                break
            time.sleep(0.1)
        else:
            return jsonify({"error": "Tempo esgotado esperando o run_simulation.py avançar. Ele está rodando?"}), 504

        eventos = MestreManager.coletar_eventos_apos(db, ultimo_rowid)

        contexto = MestreManager.montar_contexto(db)
        contexto["eventos_do_periodo"] = [f"{e['timestamp']}: {e['resumo_estruturado']}" for e in eventos]

        historico = db.carregar_historico_mestre(20)
        mensagem_sintetica = f"(O tempo avançou {minutos} minutos de jogo.) Narre o que aconteceu nesse período."

        db.salvar_mensagem_mestre('jogador', mensagem_sintetica)
        resposta = AIGameMasterClient.gerar_resposta_mestre(tema, contexto, historico, mensagem_sintetica)
        conversa_id = db.salvar_mensagem_mestre('mestre', resposta['narracao'], resposta.get('acoes_propostas') or [])

        return jsonify({
            "conversa_id": conversa_id,
            "narracao": resposta['narracao'],
            "acoes_propostas": resposta.get('acoes_propostas') or [],
            "eventos_brutos": eventos,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
