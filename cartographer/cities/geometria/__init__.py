"""
Pacote de geometria de cidade (Q02, docs/PLANO_CIDADE_VIVA.md) — era
`cartographer/cities/generate_city_geometry.py` (638 linhas, acima do limite de 400 do
ARQUITETURA.md Seção 4). Dividido por assunto:

    gerador.py        GeradorCidade — emissão da malha, inset de quadra, muralha, índice
    quad.py           geometria pura de quadrilátero (área, inset, simples, subdivisão)
    distribuicao.py   F2/F3 — distribuição dirigida de marcos e comércio de bairro
    manifesto.py       laço sobre world_manifest.json, escrita de arquivo + índice

`generate_city_geometry.py` continua existindo como shim de compatibilidade.
"""
from .gerador import GeradorCidade
from .manifesto import gerar_geometria_para_manifesto, MANIFEST_PATH, OUTPUT_DIR

__all__ = ["GeradorCidade", "gerar_geometria_para_manifesto", "MANIFEST_PATH", "OUTPUT_DIR"]
