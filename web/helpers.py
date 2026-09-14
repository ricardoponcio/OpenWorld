import numpy as np
import io
import os
from cartographer.math import ShadingProcessor, ColoringProcessor
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

def render_npz_array(npz_path_or_data, mundo_px_por_img_px=None):
    """
    Núcleo de renderização, reaproveitável por qualquer consumidor que precise do array
    RGB puro em vez de bytes PNG (ex.: cartographer/tiles/render.py, o servidor de tiles
    sob demanda da Fase 0). Extraído de render_npz_map_to_bytes (antes só produzia PNG)
    para não haver duas implementações do mesmo pipeline de cor/hillshading — ver
    docs/05_ROADMAP.md, Frente 6.

    Aceita um caminho de arquivo .npz OU o array de dados já carregado (4 canais:
    altitude/temperatura/umidade/bioma). Retorna None se o caminho não existir.

    `mundo_px_por_img_px` (Fase 0.4, armadilha nº 15 do plano): quantas unidades de
    mundo cada pixel da imagem renderizada cobre. Como todo tile tem `width=256`
    independente do zoom, derivar a escala do hillshading de `width` (comportamento
    antigo, mantido só por compatibilidade quando este parâmetro não é passado) fazia a
    escala ficar CONSTANTE enquanto o gradiente de altitude por pixel encolhe com o
    zoom — o relevo achatava ao aproximar. Quem sabe a janela pedida (o servidor de
    tiles) DEVE passar este parâmetro explicitamente.
    """
    if isinstance(npz_path_or_data, str):
        if not os.path.exists(npz_path_or_data):
            return None
        mapa = np.load(npz_path_or_data)["mapa"]
    else:
        mapa = npz_path_or_data

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
    if mundo_px_por_img_px is not None:
        # `ShadingProcessor.calculate_northwest_hillshade` calcula `np.gradient(heightmap)`
        # POR PASSO DE PIXEL DE IMAGEM, não por unidade de mundo. Como o terreno é uma
        # função suave em coordenada de mundo, quanto mais perto de zoom (menor
        # `mundo_px_por_img_px` — pixels de imagem cada vez mais próximos em mundo), MENOR
        # fica a diferença de altitude entre pixels vizinhos, e o relevo aparente
        # achataria se `escala_terreno` ficasse constante. `escala_base` foi calibrado
        # para 1 unidade de mundo por pixel de imagem; dividir (não multiplicar) por
        # `mundo_px_por_img_px` amplifica o gradiente na mesma proporção em que ele
        # encolhe, mantendo a inclinação aparente do relevo constante em qualquer zoom.
        escala_dinamica = escala_base / mundo_px_por_img_px
    else:
        # Compatibilidade: chamador antigo que ainda não migrou para passar a janela
        # explicitamente. Mantido só para não quebrar rotas que a Fase 0.5 ainda vai
        # reapontar — não use em código novo.
        resolucao_base = cfg_get(cfg, "shading_escala_terreno_resolucao_base")
        escala_dinamica = escala_base * (width / resolucao_base)
    fator_luz = ShadingProcessor.calculate_northwest_hillshade(altitudes, config=cfg, escala_terreno=escala_dinamica)

    if np.any(mask_terra):
        for c in range(3):
            img_rgb[mask_terra, c] = np.clip(
                img_rgb[mask_terra, c] * fator_luz[mask_terra],
                0, 255
            ).astype(np.uint8)

    return img_rgb


def render_npz_map_to_bytes(npz_path):
    """
    Função utilitária e 100% reutilizável de renderização de mapas NumPy compactados (.npz).
    Garante que a renderização de biomas de terra firme (altitudes, biomas e hillshading)
    seja esteticamente consistente entre o Mapa Mundi e os continentes individuais.
    """
    img_rgb = render_npz_array(npz_path)
    if img_rgb is None:
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

    height, width, _ = img_rgb.shape
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
