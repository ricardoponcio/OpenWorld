"""
MODULE: cidade.py
FUNÇÃO: Estado de simulação por cidade que a geometria estática (GeoJSON) não carrega.

DESCRIÇÃO:
    T05 (docs/PLANO_CIDADE_VIVA.md): o GeoJSON de uma cidade guarda o estado INICIAL de
    cada lote (a foto do momento em que foi gerado); a partir da importação, o banco é
    a verdade (armadilha 2 — cartographer/ nunca escreve estado de simulação). Uma casa
    construída durante o jogo nunca apareceria no mapa se o frontend só lesse o arquivo
    — esta rota devolve o DELTA (lotes cujo estado mudou desde a importação), pro
    frontend reaplicar estilo em cima das features já carregadas, sem regenerar nada.
"""
from flask import Blueprint, jsonify
from web.banco import obter_db
from web.rotas._erros import registrar_erro_handler

cidade_bp = Blueprint('cidade', __name__)
registrar_erro_handler(cidade_bp)


@cidade_bp.route('/api/cidade/<int:cidade_id>/lotes_alterados')
def api_cidade_lotes_alterados(cidade_id):
    """`GET /api/cidade/<cidade_id>/lotes_alterados` -> `[{"id", "estado", "local_id"}]`
    — só os lotes cujo `estado` já não é mais o que o GeoJSON gravou na importação. O
    frontend busca isto junto com as features (mesmo bbox/zoom) e aplica o estilo por
    cima via um `Map` de `id -> estado`."""
    return jsonify(obter_db().lotes.alterados_por_cidade(cidade_id))
