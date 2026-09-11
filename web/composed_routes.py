from flask import Blueprint, render_template, jsonify, send_file, send_from_directory, abort, request
import numpy as np
import io
import os
import json
import math
from web.helpers import render_npz_map_to_bytes, render_npz_array, obter_manifesto
from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.tiles.render import obter_cartografo, config_hash_atual, oitavas_extra_por_zoom
from cartographer.cities.escala import metros_por_pixel_mundo, tabela_zoom_min
from config import cfg_get

composed_bp = Blueprint('composed', __name__)

MAPA_COMPOSTO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'mapa_composto.npz'))
FEATURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'features'))
CIDADES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'cidades'))

# Cache em memória autoinvalidável por mtime do arquivo para evitar I/O redundante de disco
_MAP_DATA_CACHE = {}

def obter_mapa_do_cache(caminho_arquivo):
    """Carrega o array de dados 'mapa' do NPZ usando cache em memória autoinvalidável."""
    caminho_abs = os.path.abspath(caminho_arquivo)
    if not os.path.exists(caminho_abs):
        return None
    try:
        mtime = os.path.getmtime(caminho_abs)
        if caminho_abs in _MAP_DATA_CACHE:
            cached_mtime, mapa = _MAP_DATA_CACHE[caminho_abs]
            if cached_mtime == mtime:
                return mapa
        dados = np.load(caminho_abs)
        mapa = dados["mapa"]
        _MAP_DATA_CACHE[caminho_abs] = (mtime, mapa)
        return mapa
    except Exception as e:
        print(f"[CACHE] Erro ao carregar mapa {caminho_abs}: {e}")
        return None

# Cache em memória das janelas de continente/cidade geradas sob demanda (Fase 0.5):
# substitui os .npz de database/continentes|cidades. Chave inclui config_hash — muda a
# config, o cache velho vira lixo automaticamente (armadilha nº 16 do plano).
_JANELA_CACHE = {}


def _gerar_janela_com_cache(cache_key, x0, y0, x1, y1, largura, altura):
    """Gera (ou reaproveita do cache em memória do processo) a janela de mundo pedida.
    Retorna (dados, mundo_px_por_img_px) ou (None, None) se o mundo ainda não existe."""
    cartografo = obter_cartografo()
    if cartografo is None:
        return None, None

    chave = (cache_key, config_hash_atual())
    if chave in _JANELA_CACHE:
        return _JANELA_CACHE[chave]

    mundo_px_por_img_px = (x1 - x0) / largura
    # Escolhe oitavas extras pela densidade efetiva da janela (px de imagem por px de
    # mundo), reaproveitando a mesma curva de LOD por zoom do servidor de tiles — quanto
    # mais ampliado, mais oitavas, nunca reescalando o que já foi decidido (F3).
    densidade = largura / max(1e-6, (x1 - x0))
    z_equivalente = max(0, round(math.log2(max(densidade, 1e-6))))
    oitavas_extra = oitavas_extra_por_zoom(z_equivalente)

    dados = cartografo.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=oitavas_extra)
    resultado = (dados, mundo_px_por_img_px)
    if len(_JANELA_CACHE) >= 8:  # teto simples — é só pra evitar hover recalcular a cada pixel
        _JANELA_CACHE.pop(next(iter(_JANELA_CACHE)))
    _JANELA_CACHE[chave] = resultado
    return resultado


# Removed /mapa_composto route

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
        mapa = obter_mapa_do_cache(MAPA_COMPOSTO_PATH)
        if mapa is None:
            return jsonify({"error": "Mapa Composto não encontrado"}), 404
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
    Retorna a lista de continentes do world_manifest.json. Fase 0: a imagem de zoom do
    continente é gerada sob demanda por `gerar_janela()` (não mais um `.npz` pré-gerado),
    então todo continente listado já está "pronto" — a geração acontece na primeira
    requisição de `/api/continente/<uuid>/imagem` e é rápida (~250ms sem cache).
    """
    try:
        manifest = obter_manifesto()
        if not manifest:
            # Fase 1.5: o early-return devolvia só "continentes", forçando o frontend a
            # tratar esse caso como um formato de resposta diferente do normal. Devolve
            # sempre a mesma forma, com os defaults de config novos da Fase 0.
            return jsonify({
                "continentes": [],
                "dimensao_global": cfg_get(CARTOGRAPHER_CONFIG, "mundo_tiles_por_lado") * cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px"),
                "janela_padding_px": cfg_get(CARTOGRAPHER_CONFIG, "janela_padding_px"),
                "tile_zoom_maximo_ui": cfg_get(CARTOGRAPHER_CONFIG, "tile_zoom_maximo_ui"),
                "tile_max_native_zoom": cfg_get(CARTOGRAPHER_CONFIG, "tile_max_native_zoom"),
                "mapa_features_tooltip_zoom_min": cfg_get(CARTOGRAPHER_CONFIG, "mapa_features_tooltip_zoom_min"),
                "cidade_zoom_min_por_tamanho": tabela_zoom_min(CARTOGRAPHER_CONFIG),
                "metros_por_pixel_mundo": metros_por_pixel_mundo(CARTOGRAPHER_CONFIG),
                "cidade_via_largura_m_por_classe": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_m_por_classe"),
                "cidade_via_largura_min_px": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_min_px"),
            })

        continentes = []
        for c in manifest.get("continentes", []):
            continentes.append({
                "uuid": c["uuid"],
                "nome": c["nome"],
                "area_real_km2": c.get("area_real_km2", 0),
                "biomas_predominantes": c.get("biomas_predominantes", []),
                "bounding_box": c.get("bounding_box", {}),
                "cidades": c.get("cidades", []),
                "gerado": True
            })

        return jsonify({
            "continentes": continentes,
            # Tamanho real do mapa mundi (lado do quadrado, em pixels) — vem do manifesto,
            # não é mais hardcoded no frontend (mesma lição da Frente 1: ver docs/ROADMAP.md).
            "dimensao_global": manifest.get("dimensao_global", 768),
            # A imagem de zoom do continente cobre bounding_box + essa margem de cada lado
            # (Fase 0: `_janela_continente` usa o mesmo padding) — o frontend precisa saber
            # disso pra posicionar o overlay nos limites certos (Frente 6, achado de bug).
            "janela_padding_px": cfg_get(CARTOGRAPHER_CONFIG, "janela_padding_px"),
            # Zoom máximo do Leaflet (Fase 0.6): decisão de custo/UI, não limite técnico —
            # o raster pode ser gerado em qualquer zoom (`gerar_janela` é resolução-livre).
            "tile_zoom_maximo_ui": cfg_get(CARTOGRAPHER_CONFIG, "tile_zoom_maximo_ui"),
            # D5/D2 do DIAGNOSTICO_V3: acima deste zoom o raster não tem detalhe NOVO — o
            # Leaflet estica em vez de pedir tile novo ao servidor (ver maxNativeZoom).
            "tile_max_native_zoom": cfg_get(CARTOGRAPHER_CONFIG, "tile_max_native_zoom"),
            # Fase 3: acima deste zoom, o nome da cidade fica permanentemente visível
            # (sem precisar de hover) — antes um número solto no JS.
            "mapa_features_tooltip_zoom_min": cfg_get(CARTOGRAPHER_CONFIG, "mapa_features_tooltip_zoom_min"),
            # `{tamanho: {camada: zoom_min}}`, a MESMA tabela que o gerador grava em cada
            # feature de cidade (cartographer/cities/escala.py). O frontend precisa
            # dela pra dizer ao usuário a que zoom as ruas e os edifícios aparecem e pra
            # levá-lo até lá — antes eram dois números escritos à mão no popup, que já
            # estavam errados em relação ao config.
            "cidade_zoom_min_por_tamanho": tabela_zoom_min(CARTOGRAPHER_CONFIG),
            # Lado do pixel de mundo em metros. É o que deixa o frontend desenhar em
            # unidade real: largura de rua, recuo, footprint. Sem isso ele só conhece px de
            # tela, e foi assim que a rua acabou com largura inversamente proporcional ao
            # zoom. Derivado da ÁREA do pixel (D1), nunca escrito à mão.
            "metros_por_pixel_mundo": metros_por_pixel_mundo(CARTOGRAPHER_CONFIG),
            # Largura das vias em metros por classe, e o piso em px de tela pra via não
            # sumir no zoom em que a camada acende. Servido (não gravado na feature) pra
            # calibrar sem regerar as cidades.
            "cidade_via_largura_m_por_classe": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_m_por_classe"),
            "cidade_via_largura_min_px": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_min_px"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _janela_continente(continente, manifest):
    """Bbox do continente + padding, em coordenada de MUNDO, e a resolução de imagem
    proporcional ao aspecto real (Fase 0.5 — isotropia sai de graça: nunca força quadrado)."""
    bbox = continente["bounding_box"]
    padding = cfg_get(CARTOGRAPHER_CONFIG, "janela_padding_px")
    dimensao_global = manifest.get("dimensao_global", 768)
    x0 = max(0, bbox["min_x"] - padding)
    y0 = max(0, bbox["min_y"] - padding)
    x1 = min(dimensao_global, bbox["max_x"] + padding)
    y1 = min(dimensao_global, bbox["max_y"] + padding)

    alvo_maior_lado_px = cfg_get(CARTOGRAPHER_CONFIG, "imagem_janela_resolucao_alvo_px")
    largura_mundo, altura_mundo = max(1.0, x1 - x0), max(1.0, y1 - y0)
    fator = alvo_maior_lado_px / max(largura_mundo, altura_mundo)
    largura_img = max(1, int(round(largura_mundo * fator)))
    altura_img = max(1, int(round(altura_mundo * fator)))
    return x0, y0, x1, y1, largura_img, altura_img


@composed_bp.route('/api/continente/<uuid>/imagem')
def api_continente_imagem(uuid):
    """
    Retorna a imagem renderizada do continente: janela de mundo (bbox + padding) avaliada
    por `TileCartographer.gerar_janela()` sob demanda — Fase 0, não é mais um recorte de
    `.npz` pré-gerado (a fonte antiga usava índice local, P0.4).
    """
    try:
        manifest = obter_manifesto()
        if not manifest:
            return jsonify({"error": "Mundo não gerado"}), 404
        continente = next((c for c in manifest.get("continentes", []) if c["uuid"] == uuid), None)
        if not continente:
            return jsonify({"error": "Continente não encontrado"}), 404

        x0, y0, x1, y1, largura_img, altura_img = _janela_continente(continente, manifest)
        dados, mundo_px_por_img_px = _gerar_janela_com_cache(
            f"continente:{uuid}", x0, y0, x1, y1, largura_img, altura_img)
        if dados is None:
            return jsonify({"error": "Mundo não gerado"}), 404

        rgb = render_npz_array(dados, mundo_px_por_img_px=mundo_px_por_img_px)
        img_io = io.BytesIO()
        from PIL import Image
        Image.fromarray(rgb).save(img_io, format='PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/api/continente/<uuid>/info/<int:x>/<int:y>')
def api_continente_info(uuid, x, y):
    """
    Retorna detalhes de bioma, altitude, temperatura e umidade da coordenada (x,y) da
    imagem retornada por `/api/continente/<uuid>/imagem` — mesma janela, reaproveitada do
    cache em memória do processo (`_gerar_janela_com_cache`) para não regerar a cada hover.
    """
    try:
        manifest = obter_manifesto()
        if not manifest:
            return jsonify({"error": "Mundo não gerado"}), 404
        continente = next((c for c in manifest.get("continentes", []) if c["uuid"] == uuid), None)
        if not continente:
            return jsonify({"error": "Continente não encontrado"}), 404

        wx0, wy0, wx1, wy1, largura_img, altura_img = _janela_continente(continente, manifest)
        mapa, _ = _gerar_janela_com_cache(f"continente:{uuid}", wx0, wy0, wx1, wy1, largura_img, altura_img)
        if mapa is None:
            return jsonify({"error": "Zoom do continente não gerado"}), 404
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

def _encontrar_cidade(manifest, nome):
    needle = nome.strip().lower()
    for cont in manifest.get("continentes", []):
        for cid in cont.get("cidades", []):
            if cid["nome"].lower() == needle:
                return cid
    return None


def _janela_regiao(cidade, manifest):
    """Bbox de mundo (raio fixo ao redor do pixel-âncora) + resolução de imagem alvo
    para a vista REGIONAL da cidade — mesma janela usada por `/imagem` e `/entities`, pra
    bbox e imagem nunca divergirem (Fase 2.1). D7 do DIAGNOSTICO_V3 (2026-09-11): esta é a
    janela de 'onde a cidade fica no continente' (raio regional, ~190km) — não confundir
    com a cidade em si, que é sub-pixel nessa escala (Seção 2.4) e só existe como geometria
    vetorial (ver /api/mapa/features, camada de detalhe de cidade, D3)."""
    raio = cfg_get(CARTOGRAPHER_CONFIG, "regiao_janela_raio_px")
    cx, cy = cidade["x_global"], cidade["y_global"]
    dimensao_global = manifest.get("dimensao_global", 768)
    x0, y0 = max(0, cx - raio), max(0, cy - raio)
    x1, y1 = min(dimensao_global, cx + raio), min(dimensao_global, cy + raio)

    alvo = cfg_get(CARTOGRAPHER_CONFIG, "imagem_janela_resolucao_alvo_px")
    largura_mundo, altura_mundo = max(1.0, x1 - x0), max(1.0, y1 - y0)
    fator = alvo / max(largura_mundo, altura_mundo)
    largura_img = max(1, int(round(largura_mundo * fator)))
    altura_img = max(1, int(round(altura_mundo * fator)))
    return x0, y0, x1, y1, largura_img, altura_img


@composed_bp.route('/api/regiao/<nome>/imagem')
def api_regiao_imagem(nome):
    """
    D7 do DIAGNOSTICO_V3 (2026-09-11): renomeado de `/api/cidade/<nome>/imagem` — o nome
    antigo prometia "a cidade" e entregava 380km de terreno regional (Seção 9), o que o
    usuário reportou como "ainda é 1px na cidade". Esta rota é explicitamente a vista
    REGIONAL: onde a cidade fica no continente, não o que tem dentro dela (isso é a camada
    vetorial de detalhe de cidade, D3, visível no Mapa Live).

    Retorna a imagem renderizada da região ao redor da cidade: janela de mundo centrada em
    `(x_global, y_global)` com raio `regiao_janela_raio_px`, avaliada por
    `TileCartographer.gerar_janela()` sob demanda — Fase 0, não é mais um recorte de
    `.npz` pré-gerado (a fonte antiga usava índice local, P0.4).

    ⚠️ A cidade é sub-pixel nesta escala de mundo (1 px = 15,81 km, Seção 2.2/2.4) — esta
    imagem mostra o TERRENO ao redor da cidade, não a cidade em si (ruas/muralha/edifícios).
    """
    try:
        manifest = obter_manifesto()
        if not manifest:
            return jsonify({"error": "Mundo não gerado"}), 404
        cidade = _encontrar_cidade(manifest, nome)
        if not cidade:
            return jsonify({"error": "Cidade não encontrada"}), 404

        x0, y0, x1, y1, largura_img, altura_img = _janela_regiao(cidade, manifest)

        dados, mundo_px_por_img_px = _gerar_janela_com_cache(
            f"cidade:{nome.lower()}", x0, y0, x1, y1, largura_img, altura_img)
        if dados is None:
            return jsonify({"error": "Mundo não gerado"}), 404

        rgb = render_npz_array(dados, mundo_px_por_img_px=mundo_px_por_img_px)
        img_io = io.BytesIO()
        from PIL import Image
        Image.fromarray(rgb).save(img_io, format='PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@composed_bp.route('/api/regiao/<nome>/entities')
def api_regiao_entities(nome):
    """
    D7 do DIAGNOSTICO_V3: renomeado de `/api/cidade/<nome>/entities`, mesma razão da rota
    de imagem acima — isto é a vista REGIONAL.

    Retorna locais e NPCs para serem renderizados sobre o mapa da região na UI.

    Fase 2.1 (P0.3): `locais.coordenadas` agora é pixel de MUNDO (Seção 2.3), não mais
    um par 5-35 numa grade local sem relação com o mapa real. O frontend precisa saber
    a janela (bbox em mundo) e a resolução em que `/api/regiao/<nome>/imagem` foi
    renderizada pra poder converter mundo -> pixel de imagem (mesma fórmula da Seção
    2.3: `ix = (x-mnx)/(mxx-mnx)*w`) — por isso a bbox e a resolução vêm aqui, e não
    são mais um número solto no JS.
    """
    try:
        from engine.database import DatabaseManager
        import os
        import sqlite3
        import json

        manifest = obter_manifesto()
        if not manifest:
            return jsonify({"locais": [], "npcs": [], "bbox": None})
        cidade_manifesto = _encontrar_cidade(manifest, nome)

        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'openworld.db'))
        if not os.path.exists(db_path):
            return jsonify({"locais": [], "npcs": [], "bbox": None})

        db = DatabaseManager(db_path)
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cidade_row = cursor.execute('SELECT id FROM cidades WHERE nome = ?', (nome,)).fetchone()
        if not cidade_row:
            conn.close()
            return jsonify({"locais": [], "npcs": [], "bbox": None})

        cidade_id = cidade_row['id']

        locais = []
        for r in cursor.execute('SELECT id, nome, tipo, categoria, coordenadas FROM locais WHERE cidade_id = ?', (cidade_id,)).fetchall():
            d = dict(r)
            d['coordenadas'] = json.loads(d['coordenadas']) if d['coordenadas'] else [0,0]
            locais.append(d)

        npcs = []
        for r in cursor.execute('SELECT id, nome, profissao, genero, localizacao_atual_id, acao_atual FROM npcs WHERE cidade_id = ?', (cidade_id,)).fetchall():
            npcs.append(dict(r))

        conn.close()

        bbox = None
        if cidade_manifesto:
            x0, y0, x1, y1, largura_img, altura_img = _janela_regiao(cidade_manifesto, manifest)
            bbox = {"min_x": x0, "min_y": y0, "max_x": x1, "max_y": y1,
                    "largura_img": largura_img, "altura_img": altura_img}

        return jsonify({"locais": locais, "npcs": npcs, "bbox": bbox})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@composed_bp.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def get_tile(z, x, y):
    """
    Serve o tile (z,x,y) do Mapa Live. Fase 0 (docs/PLANO_EVOLUCAO_V2.md): não é mais um
    recorte de mosaico pré-renderizado — é `TileCartographer.gerar_janela()` avaliada na
    bbox de mundo daquele tile, gerada na primeira vista e servida do cache em disco depois
    (chave = config_hash do manifesto, ver cartographer/tiles/render.py). Tile fora do
    mundo (manifesto ausente/incompleto) = 404; o Leaflet trata isso mostrando aquele
    quadrado em branco, sem quebrar o resto do mapa.
    """
    from cartographer.tiles.render import renderizar_tile_png
    import io as _io
    png_bytes = renderizar_tile_png(z, x, y)
    if png_bytes is None:
        abort(404)
    return send_file(_io.BytesIO(png_bytes), mimetype='image/png')


# Cache em memória dos GeoJSON de camada, autoinvalidável por mtime (mesmo padrão de
# `obter_mapa_do_cache`). Cada camada é um arquivo pequeno (< algumas centenas de
# features nesta fase) — cache é só pra não reabrir/reparsear o arquivo a cada request.
_FEATURES_CACHE = {}


def _carregar_geojson_cache(caminho):
    if not os.path.exists(caminho):
        return {"type": "FeatureCollection", "features": []}
    mtime = os.path.getmtime(caminho)
    cache = _FEATURES_CACHE.get(caminho)
    if cache and cache[0] == mtime:
        return cache[1]
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    _FEATURES_CACHE[caminho] = (mtime, dados)
    return dados


# Fase 4 (P2.2): geometria interna de cidade (ruas, quarteirões, lotes, edifícios,
# muralha) — um arquivo por cidade em `database/cidades/<slug>.geojson`, agregados
# aqui por `properties.camada` (não por arquivo) pra virar UMA camada Leaflet só
# ("rua" mostra as ruas de todas as cidades visíveis no bbox, não uma por cidade).
CAMADAS_INTERNAS_CIDADE = {"rua", "quarteirao", "lote", "edificio", "muralha", "torre", "portao", "praca"}


def _listar_arquivos_geojson_cidades():
    if not os.path.isdir(CIDADES_DIR):
        return []
    return [os.path.join(CIDADES_DIR, nome) for nome in os.listdir(CIDADES_DIR) if nome.endswith(".geojson")]


def _bbox_geometria(geometry):
    """Bbox em MUNDO (min_x,min_y,max_x,max_y) de qualquer geometry GeoJSON — desfaz
    [lng,lat]=[x_mundo,-y_mundo] (Seção 2.3) ponto a ponto, não só pro caso Point."""
    def achatar(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            yield coords
        else:
            for c in coords:
                yield from achatar(c)

    xs, ys = [], []
    for lng, lat in achatar(geometry.get("coordinates")):
        xs.append(lng)
        ys.append(-lat)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_intersecta(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _coletar_features_camada(camada):
    if camada in CAMADAS_INTERNAS_CIDADE:
        feats = []
        for caminho in _listar_arquivos_geojson_cidades():
            geojson = _carregar_geojson_cache(caminho)
            feats.extend(f for f in geojson.get("features", []) if f.get("properties", {}).get("camada") == camada)
        return feats
    caminho = os.path.join(FEATURES_DIR, f"{camada}.geojson")
    return _carregar_geojson_cache(caminho).get("features", [])


@composed_bp.route('/api/mapa/features')
def api_mapa_features():
    """
    Fase 3 (P2.1): camada vetorial sobre o Leaflet — `GET
    /api/mapa/features?camadas=cidades,pois&bbox=x0,y0,x1,y1&z=<n>`. Devolve um dict
    `{camada: FeatureCollection}` (uma coleção por camada, não uma única mesclada — o
    frontend cria um `L.geoJSON` por camada para o `L.control.layers` funcionar).

    Filtra por `properties.zoom_min <= z` (cidade grande aparece de longe, pequena só
    perto — Fase 1.4 definiu `tamanho`, esta fase usa) e por interseção com `bbox`, se
    fornecida. Camada sem arquivo em `database/features/<camada>.geojson` ainda (ex.:
    `estradas`, `pois`, `fronteiras` — nenhuma fase até aqui gera esse dado) devolve
    `FeatureCollection` vazia, não erro.
    """
    try:
        camadas = [c.strip() for c in request.args.get('camadas', 'cidades').split(',') if c.strip()]
        z = request.args.get('z', default=0, type=int)

        bbox = None
        bbox_str = request.args.get('bbox')
        if bbox_str:
            try:
                x0, y0, x1, y1 = (float(v) for v in bbox_str.split(','))
                bbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            except (ValueError, TypeError):
                bbox = None  # bbox malformada — ignora o filtro em vez de quebrar a resposta

        resultado = {}
        for camada in camadas:
            feats = []
            for feat in _coletar_features_camada(camada):
                props = feat.get("properties", {})
                if props.get("zoom_min", 0) > z:
                    continue
                if bbox is not None:
                    bbox_feat = _bbox_geometria(feat.get("geometry") or {})
                    if bbox_feat is not None and not _bbox_intersecta(bbox_feat, bbox):
                        continue
                feats.append(feat)

            resultado[camada] = {"type": "FeatureCollection", "features": feats}

        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
