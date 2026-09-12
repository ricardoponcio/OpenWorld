from flask import Blueprint, jsonify, request
import os
from web.cache_mapa import CIDADES_DIR, FEATURES_DIR, carregar_geojson_cache, carregar_indice_cidades
from web.rotas._erros import registrar_erro_handler

features_bp = Blueprint('features', __name__)
registrar_erro_handler(features_bp)


# Fase 4 (P2.2): geometria interna de cidade (ruas, quarteirões, lotes, edifícios,
# muralha) — um arquivo por cidade em `database/cidades/<slug>.geojson`, agregados
# aqui por `properties.camada` (não por arquivo) pra virar UMA camada Leaflet só
# ("rua" mostra as ruas de todas as cidades visíveis no bbox, não uma por cidade).
CAMADAS_INTERNAS_CIDADE = {"rua", "quarteirao", "patio", "lote", "edificio", "muralha", "torre", "portao", "praca"}


def _bbox_intersecta(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _listar_arquivos_geojson_cidades():
    if not os.path.isdir(CIDADES_DIR):
        return []
    return [os.path.join(CIDADES_DIR, nome) for nome in os.listdir(CIDADES_DIR) if nome.endswith(".geojson")]


def _coletar_features_camada(camada, bbox=None, z=None):
    """Retorna `[(feature, bbox_da_feature), ...]` da camada pedida.

    E5 (Seção 5.5): pra camada interna de cidade, usa o índice pra descartar a cidade
    INTEIRA sem abrir o arquivo — quando a bbox da cidade não intersecta a bbox pedida, ou
    quando a camada nem existe/nem atingiu seu `zoom_min` naquela cidade. Só abre (e só
    então usa o cache de `carregar_geojson_cache`, que já vem com bbox por feição
    pré-calculada) as cidades que sobrevivem ao filtro."""
    if camada in CAMADAS_INTERNAS_CIDADE:
        feats = []
        indice = carregar_indice_cidades()
        if indice is not None:
            for cidade_idx in indice:
                info_camada = cidade_idx.get("camadas", {}).get(camada)
                if not info_camada or not info_camada.get("n"):
                    continue
                if z is not None and info_camada.get("zoom_min", 0) > z:
                    continue
                cidade_bbox = cidade_idx.get("bbox")
                if bbox is not None and cidade_bbox is not None:
                    cbbox = (cidade_bbox["min_x"], cidade_bbox["min_y"], cidade_bbox["max_x"], cidade_bbox["max_y"])
                    if not _bbox_intersecta(cbbox, bbox):
                        continue
                caminho = os.path.join(CIDADES_DIR, f"{cidade_idx['slug']}.geojson")
                geojson, bboxes = carregar_geojson_cache(caminho)
                for feat, bbox_feat in zip(geojson.get("features", []), bboxes):
                    if feat.get("properties", {}).get("camada") == camada:
                        feats.append((feat, bbox_feat))
        else:
            # Mundo sem índice ainda gerado (geometria antiga) — cai no caminho antigo,
            # abrindo todos os arquivos. `generate_city_geometry.py` sempre escreve o
            # índice hoje; isto é só pra não quebrar um `database/cidades/` velho.
            for caminho in _listar_arquivos_geojson_cidades():
                geojson, bboxes = carregar_geojson_cache(caminho)
                for feat, bbox_feat in zip(geojson.get("features", []), bboxes):
                    if feat.get("properties", {}).get("camada") == camada:
                        feats.append((feat, bbox_feat))
        return feats
    caminho = os.path.join(FEATURES_DIR, f"{camada}.geojson")
    geojson, bboxes = carregar_geojson_cache(caminho)
    return list(zip(geojson.get("features", []), bboxes))


@features_bp.route('/api/mapa/features')
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
        # E5: bbox da cidade já filtrou a maior parte do trabalho em
        # `_coletar_features_camada` (sem abrir arquivo); a bbox de cada feição aqui
        # vem pré-calculada do cache de carregamento, nunca recalculada por requisição.
        for feat, bbox_feat in _coletar_features_camada(camada, bbox=bbox, z=z):
            props = feat.get("properties", {})
            if props.get("zoom_min", 0) > z:
                continue
            if bbox is not None and bbox_feat is not None and not _bbox_intersecta(bbox_feat, bbox):
                continue
            feats.append(feat)

        resultado[camada] = {"type": "FeatureCollection", "features": feats}

    return jsonify(resultado)
