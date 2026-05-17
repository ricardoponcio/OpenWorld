#!/bin/bash
# SCRIPT DE RESET TOTAL E RECONSTRUÇÃO COM IA

echo "🧨 Iniciando Reset Total do Mundo..."
rm -f database/openworld.db

echo "🏗️  Construindo novo mundo com IA (15 NPCs)..."
python3 builder/manager.py --npcs 15 --ia

echo "💼 Configurando Mercado de Trabalho..."
python3 builder/setup_jobs.py

echo "📊 Auditando Saúde do Mundo..."
python3 builder/fix/audit_market.py

echo "✨ PROCESSO CONCLUÍDO! O mundo está pronto para a simulação."
