"""
MODULE: render.py
FUNÇÃO: Tile sob demanda (Fase 0, docs/06_PLANO_EVOLUCAO_V2.md, 0.4).

DESCRIÇÃO:
    Substitui o mosaico pré-renderizado (pyramid.py/generate_tile_pyramid.py, Frente 6 —
    deletados na Fase 0.5) por geração direta: cada tile é `TileCartographer.gerar_janela()`
    avaliada na bbox de mundo daquele (z,x,y), com mais oitavas conforme o zoom sobe (LOD).
    Resultado cacheado em disco, chaveado por `config_hash` do manifesto — mudar a config
    invalida o cache automaticamente (armadilha nº 16 do plano) em vez de servir tile velho
    em silêncio.
"""
import os
import json
import numpy as np
from PIL import Image

from cartographer.world.tile_cartographer import TileCartographer
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get
from web.helpers import render_npz_array

MANIFEST_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'world_manifest.json'))
CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'tiles_cache'))

# Estado de processo único (0.4: "o TileCartographer deve ser instanciado uma vez por
# processo, não por requisição" — o layout vem do manifesto, não muda entre requisições).
_cartografo = None
_manifest_mtime = None
_config_hash = None
_dimensao_global = None


def _carregar_cartografo():
    """Instancia (ou reaproveita) o TileCartographer a partir do layout persistido no
    manifesto (P0.5) — nunca chama a IA aqui. Recarrega sozinho se o manifesto mudar de
    mtime (ex.: reset rodou de novo com o servidor já de pé)."""
    global _cartografo, _manifest_mtime, _config_hash, _dimensao_global
    if not os.path.exists(MANIFEST_PATH):
        return None
    mtime = os.path.getmtime(MANIFEST_PATH)
    if _cartografo is not None and mtime == _manifest_mtime:
        return _cartografo

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    layout = manifest.get("layout_continentes")
    if not layout:
        return None

    _dimensao_global = manifest.get("dimensao_global", 768)
    _config_hash = manifest.get("config_hash", "semhash")
    _cartografo = TileCartographer(
        size=cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px"),
        seed=manifest.get("seed", 1337),
        config=CARTOGRAPHER_CONFIG,
        layout_continentes=layout,
        tamanho_global=_dimensao_global,
    )
    _manifest_mtime = mtime
    return _cartografo


def obter_cartografo():
    """Acesso público ao `TileCartographer` de processo único — reaproveitado por
    qualquer rota que precise de `gerar_janela` fora do endpoint de tile (ex.: imagem de
    continente/cidade em `web/rotas/mapa.py`). Retorna None se o mundo ainda não foi
    gerado ou o manifesto não tem `layout_continentes` persistido (P0.5)."""
    return _carregar_cartografo()


def config_hash_atual():
    """`config_hash` do manifesto carregado — chave de invalidação de qualquer cache que
    dependa da config de cartografia (não só o de tiles)."""
    _carregar_cartografo()
    return _config_hash


def oitavas_extra_por_zoom(z):
    """LOD (Fase 1.2 calibra o valor de `tile_oitavas_extra_por_zoom`; aqui só aplica a
    fórmula). Nunca deixa passar de `tile_oitavas_max` oitavas totais."""
    por_zoom = cfg_get(CARTOGRAPHER_CONFIG, "tile_oitavas_extra_por_zoom")
    maximo = cfg_get(CARTOGRAPHER_CONFIG, "tile_oitavas_max")
    oct_macro = cfg_get(CARTOGRAPHER_CONFIG, "ruido_macro_oitavas")
    return int(max(0, min(z * por_zoom, maximo - oct_macro)))


def bbox_do_tile(z, tx, ty, tile_size):
    """Bounding box do tile (z,tx,ty) em coordenada de MUNDO."""
    escala = 2 ** z
    wx0 = tx * tile_size / escala
    wx1 = (tx + 1) * tile_size / escala
    wy0 = ty * tile_size / escala
    wy1 = (ty + 1) * tile_size / escala
    return wx0, wy0, wx1, wy1


def tiles_por_lado(z, dimensao_global, tile_size):
    return int(np.ceil(dimensao_global * (2 ** z) / tile_size))


def _caminho_cache(z, tx, ty, config_hash):
    return os.path.join(CACHE_DIR, config_hash, str(z), str(tx), f"{ty}.png")


def renderizar_tile_png(z, tx, ty):
    """Gera (ou serve do cache) os bytes PNG do tile (z,tx,ty). Retorna None se o mundo
    ainda não foi gerado (manifesto ausente ou sem `layout_continentes`)."""
    cartografo = _carregar_cartografo()
    if cartografo is None:
        return None

    caminho = _caminho_cache(z, tx, ty, _config_hash)
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            return f.read()

    tile_size = cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px")
    wx0, wy0, wx1, wy1 = bbox_do_tile(z, tx, ty, tile_size)
    oitavas_extra = oitavas_extra_por_zoom(z)

    dados = cartografo.gerar_janela(wx0, wy0, wx1, wy1, tile_size, tile_size, oitavas_extra=oitavas_extra)
    mundo_px_por_img_px = (wx1 - wx0) / tile_size
    rgb = render_npz_array(dados, mundo_px_por_img_px=mundo_px_por_img_px)

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    img = Image.fromarray(rgb)
    caminho_tmp = caminho + f".tmp{os.getpid()}"
    img.save(caminho_tmp, format="PNG")
    os.replace(caminho_tmp, caminho)  # atômico — evita servir PNG parcial sob concorrência

    with open(caminho, "rb") as f:
        return f.read()
