"""
MODULE: config_loader.py
FUNÇÃO: Compatibilidade — a implementação real mora no pacote `config/` (raiz do projeto).

DESCRIÇÃO:
    Este arquivo existe só para não obrigar a reescrever todos os
    `from ..config_loader import cfg_get` / `from .config_loader import ...`
    já espalhados pela engine. A fonte de verdade, a lógica de resolução estrita
    (`cfg_get`) e a troca de fonte de configuração (JSON hoje; YAML/env/banco no
    futuro) vivem em `config/resolver.py` e `config/sources.py`.

    Não adicione lógica nova aqui — mexa em `config/`.
"""
from config import cfg_get, carregar_config_global  # noqa: F401
