"""
SCRIPT: populate.py
FUNÇÃO: CLI de povoamento inicial do mundo.
USO: venv/bin/python builder/populate.py --ia-max-thread 4 --tema "Fantasia Medieval"

DESCRIÇÃO:
    Ponto de entrada fino — a orquestração real mora em `builder/populador.py`
    (`PopuladorDeMundo`, R-D03 do 10_PLANO_REFATORACAO.md).

    P07 (docs/12_PLANO_CIDADE_VIVA.md, D1): a população nasce em TODAS as cidades ativas
    (config `cidades_ativas`). R03 (docs/13_PLANO_POPULACAO_E_ESCALA.md, Bloco R): não
    existe mais uma base de NPCs por cidade configurável aqui — o cartógrafo decide
    quantos domicílios cada cidade tem (R01/R02), o povoador conta as residências
    ocupadas e sorteia o tamanho de cada família (`npcs_por_familia_faixa`).

    Custo de IA: só a cidade em FOCO (a primeira de `cidades_ativas`) recebe DNA
    gerado por IA de verdade; as outras usam fallback procedural, sem chamada nenhuma
    — de 20 pra 750 NPCs seriam 750 chamadas de IA, e isso não pode aparecer só na
    fatura. `--desativar-ia` desliga IA em TODAS as cidades, inclusive a em foco.
"""
import os
import sys
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.database import DatabaseManager
from engine.repositorios.seed import SemeadorDeDominio
from builder.populador import PopuladorDeMundo

DB_PATH = "database/openworld.db"


def populate_world(tema="Fantasia Medieval", usar_ia=True, ia_max_thread=4):
    db = DatabaseManager(DB_PATH)
    SemeadorDeDominio.aplicar(db)
    populador = PopuladorDeMundo(db, tema, usar_ia, ia_max_thread)
    populador.executar()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tema", type=str, default="Fantasia Medieval", help="Tema criativo da simulação")
    parser.add_argument("--ia-max-thread", type=int, default=4, help="Threads simultâneas de IA via ThreadPool")
    parser.add_argument("--desativar-ia", action="store_true",
                        help="Gera NPCs de TODAS as cidades via fallback procedural rápido, "
                             "inclusive a cidade em foco (sem isto, só a cidade em foco usa IA)")
    args = parser.parse_args()

    populate_world(args.tema, not args.desativar_ia, args.ia_max_thread)
