#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO DA CARTOGRAFIA COM IA
#
# Fase 0 (docs/06_PLANO_EVOLUCAO_V2.md): não há mais mapas de zoom de continente/cidade nem
# pirâmide de tiles pré-gerada — o tile é `TileCartographer.gerar_janela()` avaliada sob
# demanda (web/composed_routes.py, cartographer/tiles/render.py), com cache em disco
# chaveado por config_hash. Só pré-aquecemos os zooms mais baixos (prewarm_cache.py) pra
# a primeira abertura do Mapa Live ser instantânea.

echo "🧨 Iniciando Reset da Cartografia..."
rm -f database/*.npz
rm -f database/world_manifest.json
rm -rf database/tiles_cache
rm -rf database/features
rm -rf database/cidades

echo "🗺️  Gerando novo Mapa Mundi..."
venv/bin/python cartographer/world/generate_world.py

echo "🏰 Gerando Metadados das Cidades..."
venv/bin/python -c "import json, subprocess; [subprocess.run(['venv/bin/python', 'cartographer/cities/generate_cities_metadata.py', c['uuid']]) for c in json.load(open('database/world_manifest.json'))['continentes']]"

echo "📍 Gerando camada vetorial de cidades (Fase 3)..."
venv/bin/python cartographer/features/generate_city_features.py

echo "🏛️  Gerando geometria real das cidades — ruas, muralha, edifícios (Fase 4)..."
venv/bin/python cartographer/cities/generate_city_geometry.py

echo "🗺️  Pré-aquecendo cache de tiles do Mapa Live (zooms baixos)..."
venv/bin/python cartographer/tiles/prewarm_cache.py

echo "✨ PROCESSO CONCLUÍDO! O mapa está pronto para uso."

