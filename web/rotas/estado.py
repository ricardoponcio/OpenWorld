"""
MODULE: estado.py
FUNÇÃO: Estado leve do relógio/simulação para o polling de 1s do painel.

DESCRIÇÃO:
    P01 (docs/16_PLANO_PAINEL_E_IA.md): substitui `/api/update` (23 MB/s, Seção
    2.1) — devolve só relógio, pausa, velocidade, evento global e crônicas. NUNCA
    a lista de NPCs/locais (Armadilha 24: "tudo, e o front filtra" é o problema,
    não a solução).
"""
from flask import Blueprint, jsonify

from web.banco import obter_db
from web.rotas._erros import registrar_erro_handler
from web.serializadores import serializar_estado, serializar_estatisticas

estado_bp = Blueprint('estado', __name__)
registrar_erro_handler(estado_bp)


@estado_bp.route('/api/estado')
def api_estado():
    return jsonify(serializar_estado(obter_db()))


@estado_bp.route('/api/estatisticas')
def api_estatisticas():
    return jsonify(serializar_estatisticas(obter_db()))
