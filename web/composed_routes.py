from flask import Blueprint, render_template, jsonify, send_file
import numpy as np
import io
import os
import json
from web.helpers import render_npz_map_to_bytes, obter_manifesto, obter_continente_e_caminhos

composed_bp = Blueprint('composed', __name__)

MAPA_COMPOSTO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'mapa_composto.npz'))

@composed_bp.route('/mapa_composto')
def mapa_composto_view():
    return render_template('mapa_composto.html')


@composed_bp.route('/api/mapa_composto/imagem')
def api_mapa_composto_imagem():
    try:
        img_io, mimetype = render_npz_map_to_bytes(MAPA_COMPOSTO_PATH)
        return send_file(img_io, mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/api/mapa_composto/info/<int:x>/<int:y>')
def api_mapa_composto_info(x, y):
    try:
        if not os.path.exists(MAPA_COMPOSTO_PATH):
            return jsonify({"error": "Mapa Composto não encontrado"}), 404
            
        dados = np.load(MAPA_COMPOSTO_PATH)
        mapa = dados["mapa"]
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
        
        # Calcula a qual tile (tx, ty) de 256x256 pertence
        tile_x = x // 256
        tile_y = y // 256
        
        return jsonify({
            "x": x,
            "y": y,
            "altitude": altitude,
            "temperatura": temperatura,
            "umidade": umidade,
            "bioma_id": id_bioma,
            "bioma_nome": nome_bioma,
            "tile_x": tile_x,
            "tile_y": tile_y
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/api/continentes')
def api_continentes():
    """
    Retorna a lista de continentes do world_manifest.json indicando o status
    de geração do arquivo NPZ de zoom para cada um.
    """
    try:
        manifest = obter_manifesto()
        if not manifest:
            return jsonify({"continentes": []})
            
        continentes = []
        for c in manifest.get("continentes", []):
            slug = c["nome"].lower().replace(" ", "_")
            npz_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'continentes'))
            npz_path = os.path.join(npz_dir, f"mapa_{slug}.npz")
            gerado = os.path.exists(npz_path)
            
            continentes.append({
                "uuid": c["uuid"],
                "nome": c["nome"],
                "area_real_km2": c.get("area_real_km2", 0),
                "biomas_predominantes": c.get("biomas_predominantes", []),
                "bounding_box": c.get("bounding_box", {}),
                "gerado": gerado
            })
            
        return jsonify({"continentes": continentes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/api/continente/<uuid>/imagem')
def api_continente_imagem(uuid):
    """
    Retorna a imagem renderizada do continente. Se o arquivo NPZ de zoom do continente
    ainda não existir, ele é gerado dinamicamente sob demanda (ROI Zoom) de forma transparente!
    """
    try:
        continente, npz_path, manifest = obter_continente_e_caminhos(uuid)
        if not continente:
            return jsonify({"error": "Continente não encontrado"}), 404
            
        # Geração dinâmica sob demanda se não existir
        if not os.path.exists(npz_path):
            from cartographer.roi_zoom import ROIZoomGenerator
            npz_dir = os.path.dirname(npz_path)
            global_npz_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'mapa_composto.npz'))
            manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'world_manifest.json'))
            
            # Usando uma resolução amigável para a web (1200x1200px) para geração ultra veloz em tempo real
            generator = ROIZoomGenerator(
                manifest_path=manifest_path,
                npz_path=global_npz_path,
                output_dir=npz_dir,
                target_resolution=1200,
                seed=manifest.get("seed", 1337),
                config={"nivel_mar": 0.35, "nivel_montanha": 0.80}
            )
            generator.generate(uuid)
            
        img_io, mimetype = render_npz_map_to_bytes(npz_path)
        return send_file(img_io, mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/api/continente/<uuid>/info/<int:x>/<int:y>')
def api_continente_info(uuid, x, y):
    """
    Retorna detalhes de bioma, altitude, temperatura e umidade da coordenada do mapa de zoom do continente.
    """
    try:
        continente, npz_path, _ = obter_continente_e_caminhos(uuid)
        if not continente:
            return jsonify({"error": "Continente não encontrado"}), 404
            
        if not os.path.exists(npz_path):
            return jsonify({"error": "Zoom do continente não gerado"}), 404
            
        dados = np.load(npz_path)
        mapa = dados["mapa"]
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
            "x": x,
            "y": y,
            "altitude": altitude,
            "temperatura": temperatura,
            "umidade": umidade,
            "bioma_id": id_bioma,
            "bioma_nome": nome_bioma,
            "map_width": width,
            "map_height": height
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
