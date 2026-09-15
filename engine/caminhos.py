"""
MODULE: caminhos.py
FUNÇÃO: Resolução de caminho a partir da raiz do projeto (I06, docs/
    16_PLANO_PAINEL_E_IA.md) — ponto único, pra nenhum módulo novo montar
    `os.path.join(os.path.dirname(...), "..", ...)` à mão (ARQUITETURA §15
    item 24). Não migra os módulos já existentes agora — só código novo usa.
"""
import os

RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def na_raiz(caminho_relativo: str) -> str:
    """Resolve um caminho do config (relativo à raiz do projeto)."""
    return os.path.join(RAIZ_PROJETO, caminho_relativo)
