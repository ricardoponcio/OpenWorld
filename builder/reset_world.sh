#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO COM IA

echo "🧨 Iniciando Reset Total do Mundo..."
rm -f database/openworld.db
rm -f database/*.npz
rm -f database/continentes/*.npz
rm -f database/world_manifest.json

echo "🗺️  Gerando novo Mapa Mundi..."
python3 cartographer/generate_world.py

echo "🔍 Gerando Mapas de Zoom dos Continentes..."
python3 -c "import json, subprocess; [subprocess.run(['python3', 'cartographer/generate_continent_zoom.py', c['uuid']]) for c in json.load(open('database/world_manifest.json'))['continentes']]"

echo "🏗️  Construindo novo mundo com IA..."
python3 builder/manager.py --npcs 20 --ia --map-size 40 --ia-max-thread 3

echo "💼 Configurando Mercado de Trabalho..."
python3 builder/setup_jobs.py

echo "📊 Auditando Saúde do Mundo..."
python3 builder/fix/audit_market.py

echo "✨ PROCESSO CONCLUÍDO! O mundo está pronto para a simulação."
