"""
SCRIPT: prewarm_cache.py
FUNÇÃO: Pré-aquece o cache de tiles sob demanda (Fase 0.4) para os zooms mais baixos,
        onde qualquer visita inicial ao Mapa Live passa primeiro.

USO:
    venv/bin/python cartographer/tiles/prewarm_cache.py

    Roda como último passo de reset_cartography.sh, depois que o mundo já foi gerado
    (precisa de world_manifest.json com `layout_continentes`).

NÃO pré-gera a pirâmide inteira (armadilha nº 14 do plano — medido: z0..z4 seriam 3069
tiles x 243ms = 12,4 min, pior que o reset inteiro de hoje). Só z0..`tile_prewarm_zoom_max`
(9+36+144 = 189 tiles nos valores atuais, ~46s), para a primeira abertura do mapa ser
instantânea. Zoom mais alto que isso é gerado sob demanda pela própria rota /tiles/.
"""
import os
import sys
import time

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.tiles.render import renderizar_tile_png, tiles_por_lado
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"


def prewarm():
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ Manifesto não encontrado em {MANIFEST_PATH}. Rode generate_world.py primeiro.")
        sys.exit(1)

    tile_size = cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px")
    zoom_max = cfg_get(CARTOGRAPHER_CONFIG, "tile_prewarm_zoom_max")

    import json
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    dimensao_global = manifest.get("dimensao_global", 768)
    if not manifest.get("layout_continentes"):
        print("❌ Manifesto sem 'layout_continentes' — rode generate_world.py (Fase 0.1) primeiro.")
        sys.exit(1)

    inicio = time.time()
    total = 0
    for z in range(zoom_max + 1):
        n = tiles_por_lado(z, dimensao_global, tile_size)
        for tx in range(n):
            for ty in range(n):
                renderizar_tile_png(z, tx, ty)
                total += 1
        print(f"🗺️  [PREWARM] Zoom {z}: {n}x{n} tiles aquecidos.")

    duracao = time.time() - inicio
    print(f"✅ [PREWARM] {total} tiles gerados em {duracao:.1f}s (z0..z{zoom_max}).")


if __name__ == "__main__":
    prewarm()
