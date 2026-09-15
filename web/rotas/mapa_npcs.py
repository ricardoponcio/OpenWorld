"""
MODULE: mapa_npcs.py
FUNÇÃO: Camada de NPCs se locomovendo no Mapa Live (M04, docs/16_PLANO_PAINEL_E_IA.md
    — pedido explícito do dono do projeto, Seção 1.1).
"""
from flask import Blueprint, jsonify, request

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.escala import metros_por_pixel_mundo
from config import cfg_get, get_config
from web.banco import obter_db
from web.cache_locais import coordenada_do_local, locais_na_bbox
from web.rotas._erros import registrar_erro_handler
from web.serializadores import serializar_mapa_npcs

mapa_npcs_bp = Blueprint('mapa_npcs', __name__)
registrar_erro_handler(mapa_npcs_bp)


@mapa_npcs_bp.route('/api/mapa/npcs')
def api_mapa_npcs():
    cfg_painel = cfg_get(get_config(), "painel")
    if float(request.args.get("z", 0)) < cfg_get(cfg_painel, "mapa_npcs_zoom_min"):
        return jsonify({"npcs": [], "truncado": False})

    x0, y0, x1, y1 = (float(v) for v in request.args["bbox"].split(","))
    limite = cfg_get(cfg_painel, "mapa_npcs_max_pontos")
    linhas = obter_db().npcs.listar_posicoes(locais_na_bbox(x0, y0, x1, y1), limite + 1)
    raio_px = cfg_get(cfg_painel, "mapa_npcs_espalhamento_m") / metros_por_pixel_mundo(CARTOGRAPHER_CONFIG)
    return jsonify(serializar_mapa_npcs(linhas, limite, coordenada_do_local, raio_px))
