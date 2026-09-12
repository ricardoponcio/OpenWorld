"""
SHIM DE COMPATIBILIDADE (Q02, docs/PLANO_CIDADE_VIVA.md).

A implementação mora em `cartographer/cities/geometria/` (virou pacote: o arquivo tinha
638 linhas, acima do limite de 400 do ARQUITETURA.md Seção 4). Este arquivo existe só
pra quem ainda importa pelo caminho antigo (`tests/test_cidades.py`) e pra continuar
executável como script:

    venv/bin/python cartographer/cities/generate_city_geometry.py [nome_da_cidade]
"""
import os
import sys

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.cities.geometria import *  # noqa: F401,F403
from cartographer.cities.geometria import gerar_geometria_para_manifesto

if __name__ == "__main__":
    nome_filtro = sys.argv[1] if len(sys.argv) > 1 else None
    gerar_geometria_para_manifesto(nome_filtro)
