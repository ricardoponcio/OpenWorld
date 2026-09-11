import os
import json
import numpy as np

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


# Cache em memória dos GeoJSON de camada, autoinvalidável por mtime (mesmo padrão de
# `obter_mapa_do_cache`). E5 (ESPEC_TECIDO_URBANO.md Seção 5.5): guarda também a bbox de
# CADA feição, calculada uma vez no carregamento — antes `_bbox_geometria` rodava a cada
# requisição para cada feição candidata (o gargalo medido na Seção 3.6).
_FEATURES_CACHE = {}


def bbox_geometria(geometry):
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


def carregar_geojson_cache(caminho):
    """Retorna `(geojson_dict, bboxes)`, onde `bboxes[i]` é a bbox (Seção 2.3) da feição
    `geojson_dict["features"][i]`, ou `None` se a feição não tiver coordenada."""
    if not os.path.exists(caminho):
        return {"type": "FeatureCollection", "features": []}, []
    mtime = os.path.getmtime(caminho)
    cache = _FEATURES_CACHE.get(caminho)
    if cache and cache[0] == mtime:
        return cache[1], cache[2]
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    bboxes = [bbox_geometria(f.get("geometry") or {}) for f in dados.get("features", [])]
    _FEATURES_CACHE[caminho] = (mtime, dados, bboxes)
    return dados, bboxes


# E5: índice por cidade (database/cidades/_indice.json, escrito por
# generate_city_geometry.py) — bbox de cada cidade em px de mundo, e por camada a
# contagem e o zoom_min. Permite descartar a cidade INTEIRA sem nem abrir o arquivo.
_INDICE_CIDADES_PATH = os.path.join(CIDADES_DIR, "_indice.json")
_INDICE_CIDADES_CACHE = {}


def carregar_indice_cidades():
    if not os.path.exists(_INDICE_CIDADES_PATH):
        return None
    mtime = os.path.getmtime(_INDICE_CIDADES_PATH)
    cache = _INDICE_CIDADES_CACHE.get(_INDICE_CIDADES_PATH)
    if cache and cache[0] == mtime:
        return cache[1]
    with open(_INDICE_CIDADES_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)
    cidades = dados.get("cidades", [])
    _INDICE_CIDADES_CACHE[_INDICE_CIDADES_PATH] = (mtime, cidades)
    return cidades
