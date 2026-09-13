"""
MODULE: mestre_routes.py
FUNÇÃO: Endpoints do Modo Mestre de IA (Frente 5).

DESCRIÇÃO:
    O dashboard Flask não é dono da SimulationEngine (ela roda no processo do
    run_simulation.py) — por isso "avançar o tempo" aqui não tica a engine
    diretamente, só sinaliza via mundo_meta (mesmo padrão já usado por pausa e
    velocidade) e espera o run_simulation.py consumir. Ver docs/ROADMAP.md, Frente 5.
"""
import json
import time
from flask import Blueprint, request, jsonify

from web.banco import obter_db
from engine.mechanics.mestre import MestreManager
from engine.config_loader import carregar_config_global
from engine.ai import AIGameMasterClient
from engine.models import MetaChave

mestre_bp = Blueprint('mestre', __name__)


def obter_mestre() -> MestreManager:
    """MestreManager recebe banco e config (R-F03). O banco é a instância única do
    processo (web/banco.py) e a config já vem do cache do resolvedor — nenhum dos dois
    é construído de novo por requisição."""
    return MestreManager(obter_db(), carregar_config_global())

TEMA_PADRAO = "Fantasia Medieval"
# F01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): se uma ação enfileirada há mais tempo do
# que isto ainda não foi aplicada, run_simulation.py provavelmente não está rodando
# (ou travou) — mesma condição que /api/mestre/avancar_tempo já expõe por timeout,
# só que agora sem bloquear a requisição esperando.
AVISO_FILA_PARADA_SEGUNDOS = 10


@mestre_bp.route('/api/mestre/historico')
def get_historico():
    try:
        db = obter_db()
        historico = db.mestre.carregar_historico(50)
        for h in historico:
            h['acoes_propostas'] = json.loads(h['acoes_propostas']) if h['acoes_propostas'] else []
        return jsonify({"historico": historico})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/estado')
def get_estado():
    try:
        db = obter_db()
        restante = int(db.meta.carregar(MetaChave.AVANCAR_MINUTOS) or 0)
        pausado = db.meta.carregar(MetaChave.SIMULACAO_PAUSADA) == "1"
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

        db = obter_db()
        contexto = obter_mestre().montar_contexto()
        historico = db.mestre.carregar_historico(20)

        db.mestre.salvar_mensagem('jogador', mensagem)
        resposta = AIGameMasterClient.gerar_resposta_mestre(tema, contexto, historico, mensagem)
        conversa_id = db.mestre.salvar_mensagem('mestre', resposta['narracao'], resposta.get('acoes_propostas') or [])

        return jsonify({
            "conversa_id": conversa_id,
            "narracao": resposta['narracao'],
            "acoes_propostas": resposta.get('acoes_propostas') or [],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mestre_bp.route('/api/mestre/confirmar_acoes', methods=['POST'])
def post_confirmar_acoes():
    """F01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): ENFILEIRA as ações propostas de uma
    mensagem do Mestre — só chega aqui depois que o jogador confirmou explicitamente
    na interface. Nunca é chamado sozinho.

    A resposta é assíncrona: `enfileirado: True`, não `aplicado: True` — a ação só
    é de fato aplicada quando `run_simulation.py` drenar a fila, no próximo tick
    (ou na próxima volta do laço, se a simulação estiver pausada). Se a fila já
    tiver algo pendente há tempo demais, `aviso` sinaliza que a simulação pode não
    estar rodando — sem bloquear esta requisição esperando (ao contrário de
    `/avancar_tempo`, que já espera por natureza)."""
    try:
        body = request.get_json(force=True) or {}
        conversa_id = body.get('conversa_id')
        if not conversa_id:
            return jsonify({"error": "conversa_id é obrigatório."}), 400

        db = obter_db()
        msg = db.mestre.carregar_mensagem(conversa_id)
        if not msg or msg['autor'] != 'mestre':
            return jsonify({"error": "Conversa não encontrada ou não é uma resposta do Mestre."}), 404
        if msg['aplicada']:
            return jsonify({"error": "Estas ações já foram aplicadas."}), 400

        acoes = json.loads(msg['acoes_propostas']) if msg['acoes_propostas'] else []
        resultados = obter_mestre().aplicar_acoes(acoes)
        db.mestre.marcar_aplicada(conversa_id)

        aviso = None
        if db.mestre.ha_fila_nao_drenada(AVISO_FILA_PARADA_SEGUNDOS):
            aviso = "A simulação não parece estar processando a fila — run_simulation.py está rodando?"

        return jsonify({"enfileirado": True, "resultados": resultados, "aviso": aviso})
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

        db = obter_db()
        ultimo_rowid = obter_mestre().ultimo_rowid_eventos()

        # Garante que a simulação está pausada — sem isso, o run_simulation.py nunca
        # olha para mestre_avancar_minutos_restantes (esse contador só é consumido
        # dentro do ramo de pausa do loop).
        db.meta.salvar(MetaChave.SIMULACAO_PAUSADA, "1")
        db.meta.salvar(MetaChave.AVANCAR_MINUTOS, str(minutos))

        # Espera o run_simulation.py consumir o avanço (poll curto). Timeout generoso
        # o bastante mesmo para saltos grandes (medido ~1.2ms/tick na Frente 4).
        timeout = max(5.0, minutos * 0.02)
        inicio = time.time()
        while time.time() - inicio < timeout:
            restante = int(db.meta.carregar(MetaChave.AVANCAR_MINUTOS) or 0)
            if restante <= 0:
                break
            time.sleep(0.1)
        else:
            return jsonify({"error": "Tempo esgotado esperando o run_simulation.py avançar. Ele está rodando?"}), 504

        eventos = obter_mestre().coletar_eventos_apos(ultimo_rowid)

        contexto = obter_mestre().montar_contexto()
        contexto["eventos_do_periodo"] = [f"{e['timestamp']}: {e['resumo_estruturado']}" for e in eventos]

        historico = db.mestre.carregar_historico(20)
        mensagem_sintetica = f"(O tempo avançou {minutos} minutos de jogo.) Narre o que aconteceu nesse período."

        db.mestre.salvar_mensagem('jogador', mensagem_sintetica)
        resposta = AIGameMasterClient.gerar_resposta_mestre(tema, contexto, historico, mensagem_sintetica)
        conversa_id = db.mestre.salvar_mensagem('mestre', resposta['narracao'], resposta.get('acoes_propostas') or [])

        return jsonify({
            "conversa_id": conversa_id,
            "narracao": resposta['narracao'],
            "acoes_propostas": resposta.get('acoes_propostas') or [],
            "eventos_brutos": eventos,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
