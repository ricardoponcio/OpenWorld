"""
MODULE: config.py
FUNÇÃO: Compatibilidade — os parâmetros de cartografia agora moram em `config.json`,
sob a chave "cartografia", resolvidos pelo pacote `config/` da raiz do projeto
(ver docs/05_ROADMAP.md, Frente 1).

DESCRIÇÃO:
    Este arquivo mantém o nome `CARTOGRAPHER_CONFIG` só para não obrigar a reescrever
    todos os módulos que hoje recebem/indexam esse dict diretamente. O conteúdo em si
    não é mais um literal escrito à mão aqui — vem do config único do projeto, então
    editar `config.json` é o único lugar necessário para mudar esses valores.

    Não adicione chaves novas aqui — adicione em config.json["cartografia"].
"""
from config import cfg_get, get_config

CARTOGRAPHER_CONFIG = cfg_get(get_config(), "cartografia")
