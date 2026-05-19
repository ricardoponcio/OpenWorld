#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO DA CARTOGRAFIA COM IA

echo "🧨 Iniciando Reset da Cartografia..."
rm -f database/*.npz
rm -f database/continentes/*.npz
rm -f database/world_manifest.json

echo "🗺️  Gerando novo Mapa Mundi..."
python3 cartographer/generate_world.py

echo "🔍 Gerando Mapas de Zoom dos Continentes..."
python3 -c "import json, subprocess; [subprocess.run(['python3', 'cartographer/generate_continent_zoom.py', c['uuid']]) for c in json.load(open('database/world_manifest.json'))['continentes']]"

echo "✨ PROCESSO CONCLUÍDO! O mapa está pronto para uso."
