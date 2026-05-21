#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO DA CARTOGRAFIA COM IA

echo "🧨 Iniciando Reset da Cartografia..."
rm -f database/*.npz
rm -f database/continentes/*.npz
rm -f database/cidades/*.npz
rm -f database/world_manifest.json

echo "🗺️  Gerando novo Mapa Mundi..."
venv/bin/python cartographer/world/generate_world.py

echo "🏰 Gerando Metadados das Cidades..."
venv/bin/python -c "import json, subprocess; [subprocess.run(['venv/bin/python', 'cartographer/cities/generate_cities_metadata.py', c['uuid']]) for c in json.load(open('database/world_manifest.json'))['continentes']]"

echo "🔍 Gerando Mapas de Zoom dos Continentes..."
venv/bin/python -c "import json, subprocess; [subprocess.run(['venv/bin/python', 'cartographer/continents/generate_continent_zoom.py', c['uuid']]) for c in json.load(open('database/world_manifest.json'))['continentes']]"

echo "🏰 Gerando Mapas de Zoom das Cidades..."
venv/bin/python -c "import json, subprocess; [subprocess.run(['venv/bin/python', 'cartographer/cities/city_roi_zoom.py', cid['nome']]) for c in json.load(open('database/world_manifest.json'))['continentes'] for cid in c.get('cidades', [])]"

echo "✨ PROCESSO CONCLUÍDO! O mapa está pronto para uso."

