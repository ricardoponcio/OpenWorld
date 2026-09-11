"""
SCRIPT: generate_city_features.py
FUNÇÃO: Gera database/features/cidades.geojson — a camada vetorial de cidades (Fase 3,
        P2.1) que o Leaflet desenha por cima do raster de terreno.

USO:
    venv/bin/python cartographer/features/generate_city_features.py

    Roda depois que o manifesto tem cidades (após generate_cities_metadata.py, no reset).

POR QUE GEOJSON EM DISCO (não computado por requisição): as cidades só mudam quando o
mundo é regerado — igual a `mapa_composto.npz`, é barato persistir uma vez e servir
estático depois. Coordenadas em `[x_mundo, -y_mundo]` (Seção 2.3 do plano): é
exatamente o que faz `L.geoJSON` plotar direto em `L.CRS.Simple` sem transformação
nenhuma no frontend (GeoJSON usa `[lng, lat]`, e a conversão do projeto é
`lat = -y, lng = x` — mesma fórmula de `pixelParaLatLng()` em mapa_leaflet.js).

`estradas`, `pois`, `fronteiras` ainda não têm gerador (nenhuma fase até aqui produz
esse dado) — a rota `/api/mapa/features` devolve `FeatureCollection` vazia pra essas
camadas quando o arquivo não existe, em vez de erro. Populam sozinhas quando uma fase
futura (rios=Fase 6, POIs de cidade=Fase 4/5) escrever o arquivo correspondente.
"""
import os
import sys
import json

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"
FEATURES_DIR = "database/features"


def gerar_features_cidades():
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ Manifesto não encontrado em {MANIFEST_PATH}. Rode generate_world.py primeiro.")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    zoom_min_por_tamanho = cfg_get(CARTOGRAPHER_CONFIG, "mapa_features_zoom_min_por_tamanho")

    features = []
    for cont in manifest.get("continentes", []):
        for cid in cont.get("cidades", []):
            x, y = cid.get("x_global"), cid.get("y_global")
            if x is None or y is None:
                continue
            tamanho = cid.get("tamanho", "pequeno").lower()
            slug = cid["nome"].lower().replace(" ", "_")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [x, -y]},
                "properties": {
                    "id": slug,
                    "nome": cid["nome"],
                    "tipo": cid.get("tipo", "desconhecido"),
                    "tamanho": tamanho,
                    "continente": cont["nome"],
                    "zoom_min": zoom_min_por_tamanho.get(tamanho, 0),
                    "x_global": x,
                    "y_global": y,
                    "descricao": f"Cidade {tamanho} de {cont['nome']} ({cid.get('tipo', 'desconhecido')}).",
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}

    os.makedirs(FEATURES_DIR, exist_ok=True)
    caminho = os.path.join(FEATURES_DIR, "cidades.geojson")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"✅ [FEATURES] {len(features)} cidade(s) escritas em '{caminho}'.")


if __name__ == "__main__":
    gerar_features_cidades()
