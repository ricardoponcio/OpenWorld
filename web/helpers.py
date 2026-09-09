import numpy as np
import io
import os
from cartographer.math import ShadingProcessor, ColoringProcessor
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

def render_npz_map_to_bytes(npz_path):
    """
    Função utilitária e 100% reutilizável de renderização de mapas NumPy compactados (.npz).
    Garante que a renderização de biomas de terra firme (altitudes, biomas e hillshading)
    seja esteticamente consistente entre o Mapa Mundi e os continentes individuais.
    """
    if not os.path.exists(npz_path):
        # Fallback se o arquivo .npz não existir
        try:
            from PIL import Image
            img = Image.new("RGB", (768, 768), (20, 24, 33))
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            return img_io, 'image/png'
        except ImportError:
            transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
            return io.BytesIO(transparent_png), 'image/png'
            
    dados = np.load(npz_path)
    mapa = dados["mapa"]
    height, width, _ = mapa.shape

    biomas = mapa[:, :, 3].astype(int)
    altitudes = mapa[:, :, 0]
    cfg = CARTOGRAPHER_CONFIG
    nivel_mar = cfg_get(cfg, "nivel_mar")

    # 1. Renderiza o oceano dinâmico baseado na profundidade
    img_rgb = ColoringProcessor.render_ocean(altitudes, config=cfg, nivel_mar=nivel_mar)

    # 2. Renderizar biomas de terra firme com gradiente de altitude
    mask_terra = (biomas > 1)
    if np.any(mask_terra):
        alt_terra_norm = np.clip((altitudes - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)

        # Mapear biomas de terra firme (mesmos IDs de ClimateProcessor.BIOME_IDS, exceto Oceano)
        for b_id in (2, 3, 4, 5):
            mask_b = (biomas == b_id)
            if np.any(mask_b):
                r_c, g_c, b_c = ColoringProcessor.interpolate_land_biome(b_id, alt_terra_norm, config=cfg)
                img_rgb[mask_b, 0] = r_c[mask_b]
                img_rgb[mask_b, 1] = g_c[mask_b]
                img_rgb[mask_b, 2] = b_c[mask_b]

    # 3. Sombreamento 3D de Relevo (Hillshading) vindo de Noroeste
    # Escalamos a escala_terreno de forma proporcional à resolução da imagem (width) para
    # garantir que os gradientes de relevo permaneçam dramáticos e visíveis em qualquer zoom —
    # "shading_escala_terreno_resolucao_base" é a resolução na qual "shading_escala_terreno"
    # foi calibrado (o mapa mundi, hoje 768/3=256px por tile).
    escala_base = cfg_get(cfg, "shading_escala_terreno")
    resolucao_base = cfg_get(cfg, "shading_escala_terreno_resolucao_base")
    escala_dinamica = escala_base * (width / resolucao_base)
    fator_luz = ShadingProcessor.calculate_northwest_hillshade(altitudes, config=cfg, escala_terreno=escala_dinamica)
    
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
        return img_io, 'image/png'
    except ImportError:
        # Fallback manual em formato BMP de 24-bits em pura memória Python
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
        return io.BytesIO(header + bmp_pixels), 'image/bmp'


def render_biomes_map_to_bytes(npz_path):
    """
    Função utilitária de renderização de mapa de biomas simples.
    Usada principalmente no cartógrafo tradicional para exibir cores de biomas brutas.
    """
    if not os.path.exists(npz_path):
        # Fallback se o mapa não existir
        try:
            from PIL import Image
            img = Image.new("RGB", (500, 500), (20, 24, 33))
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            return img_io, 'image/png'
        except ImportError:
            transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
            return io.BytesIO(transparent_png), 'image/png'
            
    dados = np.load(npz_path)
    mapa = dados["mapa"]
    height, width, _ = mapa.shape
    
    # Paleta de cores para os biomas
    CORES = {
        1: (28, 107, 160),   # OCEANO (Azul)
        2: (224, 192, 114),  # DESERTO (Areia)
        3: (114, 166, 102),  # MEDITERRANEO (Verde Oliva)
        4: (43, 94, 60),     # FLORESTA_TEMPERADA (Verde Escuro)
        5: (110, 110, 110)   # MONTANHA_ROCHOSA (Cinza)
    }
    
    biomas = mapa[:, :, 3].astype(int)
    
    img_rgb = np.zeros((height, width, 3), dtype=np.uint8)
    for id_bioma, cor in CORES.items():
        img_rgb[biomas == id_bioma] = cor
        
    try:
        from PIL import Image
        img = Image.fromarray(img_rgb)
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        return img_io, 'image/png'
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
        return io.BytesIO(header + bmp_pixels), 'image/bmp'


def obter_manifesto():
    """
    Retorna o manifesto do mundo (world_manifest.json) parseado.
    Retorna None ou dict.
    """
    import json
    manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'world_manifest.json'))
    if not os.path.exists(manifest_path):
        return None
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def obter_continente_e_caminhos(uuid):
    """
    Busca um continente pelo UUID e calcula seus caminhos.
    Retorna (continente_dict, npz_path, manifest_dict) ou (None, None, None).
    """
    manifest = obter_manifesto()
    if not manifest:
        return None, None, None
        
    for c in manifest.get("continentes", []):
        if c["uuid"] == uuid:
            slug = c["nome"].lower().replace(" ", "_")
            npz_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'continentes'))
            npz_path = os.path.join(npz_dir, f"mapa_{slug}.npz")
            return c, npz_path, manifest
            
    return None, None, None
