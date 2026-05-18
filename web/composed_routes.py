from flask import Blueprint, render_template, jsonify, send_file
import numpy as np
import io
import os
from cartographer.math import ShadingProcessor, ColoringProcessor

composed_bp = Blueprint('composed', __name__)

MAPA_COMPOSTO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'mapa_composto.npz'))

@composed_bp.route('/mapa_composto')
def mapa_composto_view():
    return render_template('mapa_composto.html')

@composed_bp.route('/api/mapa_composto/imagem')
def api_mapa_composto_imagem():
    try:
        if not os.path.exists(MAPA_COMPOSTO_PATH):
            # Fallback se o mapa composto não existir
            try:
                from PIL import Image
                img = Image.new("RGB", (768, 768), (20, 24, 33))
                img_io = io.BytesIO()
                img.save(img_io, 'PNG')
                img_io.seek(0)
                return send_file(img_io, mimetype='image/png')
            except ImportError:
                transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
                return send_file(io.BytesIO(transparent_png), mimetype='image/png')
            
        dados = np.load(MAPA_COMPOSTO_PATH)
        mapa = dados["mapa"]
        height, width, _ = mapa.shape
        
        biomas = mapa[:, :, 3].astype(int)
        altitudes = mapa[:, :, 0]
        nivel_mar = 0.35
        
        # 1. Renderiza o oceano dinâmico baseado na profundidade
        img_rgb = ColoringProcessor.render_ocean(altitudes, nivel_mar=nivel_mar)
        
        # 2. Renderizar biomas de terra firme com gradiente de altitude (Verde -> Rocha -> Neve nos picos)
        mask_terra = (biomas > 1)
        if np.any(mask_terra):
            # Normaliza a altitude da terra firme
            alt_terra_norm = np.clip((altitudes - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)
            
            # Aplica a interpolação altitudinal de cor para cada bioma de terra
            for b_id in [2, 3, 4, 5]:
                mask_b = (biomas == b_id)
                if np.any(mask_b):
                    r_c, g_c, b_c = ColoringProcessor.interpolate_land_biome(b_id, alt_terra_norm)
                    img_rgb[mask_b, 0] = r_c[mask_b]
                    img_rgb[mask_b, 1] = g_c[mask_b]
                    img_rgb[mask_b, 2] = b_c[mask_b]
            
        # 3. Sombreamento 3D de Relevo (Hillshading) vindo de Noroeste
        fator_luz = ShadingProcessor.calculate_northwest_hillshade(altitudes, escala_terreno=48.0)
        
        # Aplicamos o sombreamento 3D exclusivamente na terra firme para destacar o relevo
        if np.any(mask_terra):
            for c in range(3):
                img_rgb[mask_terra, c] = np.clip(
                    img_rgb[mask_terra, c] * fator_luz[mask_terra], 
                    0, 255
                ).astype(np.uint8)
            
        try:
            from PIL import Image
            img = Image.fromarray(img_rgb)
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            return send_file(img_io, mimetype='image/png')
        except ImportError:
            # Gerador de BMP fallback de 24-bits em pura memória Python
            row_size = (width * 3 + 3) & ~3
            padding = row_size - width * 3
            bmp_pixels = bytearray()
            for y in range(height - 1, -1, -1):
                row = img_rgb[y]
                for x in range(width):
                    r, g, b = row[x]
                    bmp_pixels.append(b)  # BMP usa BGR
                    bmp_pixels.append(g)
                    bmp_pixels.append(r)
                bmp_pixels.extend([0] * padding)
                
            file_size = 54 + len(bmp_pixels)
            header = bytearray([
                66, 77,  # BM
                file_size & 255, (file_size >> 8) & 255, (file_size >> 16) & 255, (file_size >> 24) & 255,
                0, 0, 0, 0,
                54, 0, 0, 0,  # Offset
                40, 0, 0, 0,  # Header size
                width & 255, (width >> 8) & 255, (width >> 16) & 255, (width >> 24) & 255,
                height & 255, (height >> 8) & 255, (height >> 16) & 255, (height >> 24) & 255,
                1, 0,  # Planes
                24, 0,  # Bits per pixel
                0, 0, 0, 0,
                len(bmp_pixels) & 255, (len(bmp_pixels) >> 8) & 255, (len(bmp_pixels) >> 16) & 255, (len(bmp_pixels) >> 24) & 255,
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            ])
            return send_file(io.BytesIO(header + bmp_pixels), mimetype='image/bmp')
            
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
