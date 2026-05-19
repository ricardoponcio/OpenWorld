#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO COM IA

echo "🧨 Iniciando Reset Total do Mundo..."
rm -f database/openworld.db

# Resetar e gerar novo mapa
bash cartographer/reset_cartography.sh

echo "🏗️  Construindo novo mundo com IA..."
python3 builder/manager.py --npcs 20 --ia --map-size 40 --ia-max-thread 3

echo "💼 Configurando Mercado de Trabalho..."
python3 builder/setup_jobs.py

echo "📊 Auditando Saúde do Mundo..."
python3 builder/fix/audit_market.py

echo "✨ PROCESSO CONCLUÍDO! O mundo está pronto para a simulação."
