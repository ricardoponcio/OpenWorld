#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO COM IA

echo "🧨 Iniciando Reset Total do Mundo..."
rm -f database/openworld.db

# Resetar e gerar novo mapa
bash cartographer/reset_cartography.sh

echo "👥 Povoando o mundo com IA..."
venv/bin/python builder/populate.py --npcs 20 --ia-max-thread 4

echo "✨ PROCESSO CONCLUÍDO! O mundo está povoado e pronto."
echo "💡 Para iniciar a simulação, execute: python3 run_simulation.py"
