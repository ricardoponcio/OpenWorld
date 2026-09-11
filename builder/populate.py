"""
SCRIPT: populate.py
FUNÇÃO: CLI de povoamento inicial do mundo.
USO: venv/bin/python builder/populate.py --npcs 20 --ia-max-thread 4 --tema "Fantasia Medieval"

DESCRIÇÃO:
    Ponto de entrada fino — a orquestração real mora em `builder/populador.py`
    (`PopuladorDeMundo`, R-D03 do PLANO_REFATORACAO.md).
"""
import os
import sys
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.database import DatabaseManager
from builder.populador import PopuladorDeMundo

DB_PATH = "database/openworld.db"


def populate_world(num_npcs=20, tema="Fantasia Medieval", usar_ia=True, ia_max_thread=4):
    db = DatabaseManager(DB_PATH)
    populador = PopuladorDeMundo(db, tema, usar_ia, ia_max_thread)
    populador.executar(num_npcs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=20, help="Quantidade de NPCs para gerar")
    parser.add_argument("--tema", type=str, default="Fantasia Medieval", help="Tema criativo da simulação")
    parser.add_argument("--ia-max-thread", type=int, default=4, help="Threads simultâneas de IA via ThreadPool")
    parser.add_argument("--desativar-ia", action="store_true", help="Gera NPCs apenas via fallback procedural rápido")
    args = parser.parse_args()

    populate_world(args.npcs, args.tema, not args.desativar_ia, args.ia_max_thread)
