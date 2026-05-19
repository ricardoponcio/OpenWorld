from flask import Blueprint, render_template, jsonify, send_file
import numpy as np
import io
import os
import subprocess
import sys
from web.helpers import render_biomes_map_to_bytes

cartographer_bp = Blueprint('cartographer', __name__)

MAPA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'mapa_mundo.npz'))

# Cache autoinvalidável por mtime
_MAPA_MUNDO_CACHE = {}

def obter_mapa_do_cache(caminho_arquivo):
    caminho_abs = os.path.abspath(caminho_arquivo)
    if not os.path.exists(caminho_abs):
        return None
    try:
        mtime = os.path.getmtime(caminho_abs)
        if caminho_abs in _MAPA_MUNDO_CACHE:
            cached_mtime, mapa = _MAPA_MUNDO_CACHE[caminho_abs]
            if cached_mtime == mtime:
                return mapa
        dados = np.load(caminho_abs)
        mapa = dados["mapa"]
        _MAPA_MUNDO_CACHE[caminho_abs] = (mtime, mapa)
        return mapa
    except Exception as e:
        print(f"[CARTOGRAPHER CACHE] Erro: {e}")
        return None

@cartographer_bp.route('/mapa')
def mapa_view():
    return render_template('mapa.html')


@cartographer_bp.route('/api/mapa/imagem')
def api_mapa_imagem():
    try:
        img_io, mimetype = render_biomes_map_to_bytes(MAPA_PATH)
        return send_file(img_io, mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@cartographer_bp.route('/api/mapa/info/<int:x>/<int:y>')
def api_mapa_info(x, y):
    try:
        mapa = obter_mapa_do_cache(MAPA_PATH)
        if mapa is None:
            return jsonify({"error": "Mapa não encontrado"}), 404
        height, width, _ = mapa.shape
        
        if x < 0 or x >= width or y < 0 or y >= height:
            return jsonify({"error": "Coordenada fora dos limites"}), 400
            
        altitude = float(mapa[y, x, 0])
        temperatura = float(mapa[y, x, 1])
        umidade = float(mapa[y, x, 2])
        id_bioma = int(mapa[y, x, 3])
        
        NOME_BIOMAS = {
            1: "Oceano",
            2: "Deserto",
            3: "Mediterrâneo",
            4: "Floresta Temperada",
            5: "Montanha Rochosa"
        }
        nome_bioma = NOME_BIOMAS.get(id_bioma, "Desconhecido")
        
        return jsonify({
            "x": x, "y": y,
            "altitude": altitude,
            "temperatura": temperatura,
            "umidade": umidade,
            "bioma_id": id_bioma,
            "bioma_nome": nome_bioma
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
