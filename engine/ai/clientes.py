"""
MODULE: clientes.py
FUNÇÃO: Vocabulário fechado de quem chama a IA, e a regra de resolução da
    config efetiva de cada cliente (I01, docs/16_PLANO_PAINEL_E_IA.md).
"""
from enum import Enum


class ClienteIA(Enum):
    """I01: quem está chamando a IA. O valor é a chave do cliente em
    config.json["ia"]["clientes"] e o campo `cliente` do registro de uso
    (logs/ia_uso.jsonl)."""
    MESTRE                   = "mestre"
    NOME_BEBE                = "nome_bebe"
    DNA_NPC                  = "dna_npc"
    BACKGROUND_NPC           = "background_npc"      # sem chamador hoje — mantido de propósito (decisão ⓫)
    LOCAIS_CIDADE            = "locais_cidade"       # sem chamador hoje — mantido de propósito (decisão ⓫)
    EVENTO_GLOBAL            = "evento_global"
    PLANEJAMENTO_CONTINENTES = "planejamento_continentes"
    FUNDACAO_CIDADES         = "fundacao_cidades"


def resolver_config_cliente(config_ia: dict, cliente: ClienteIA) -> dict:
    """A config efetiva de um cliente é `{**padrao, **clientes[cliente.value]}` —
    sobrescrita RASA, por chave (`cadeia` sobrescrita substitui a lista inteira,
    nunca concatena com a do padrão). Falha alto (ARQUITETURA P5) se o cliente
    não tiver entrada nenhuma em `clientes` — um objeto vazio `{}` é uma entrada
    válida (herda tudo do padrão); a chave ausente não é."""
    if cliente.value not in config_ia["clientes"]:
        raise ValueError(
            f"[IA] cliente '{cliente.value}' sem entrada em config.json['ia']['clientes'] "
            "— todo membro de ClienteIA precisa de uma entrada (mesmo que vazia).")
    return {**config_ia["padrao"], **config_ia["clientes"][cliente.value]}


def validar_config_ia(config_ia: dict) -> None:
    """Validação na construção (I01 passo 4, ARQUITETURA P5 "falhar alto"): todo
    membro de ClienteIA tem entrada em `clientes`; toda entrada de `cadeia`
    aponta pra um provedor existente; `timeout_s > 0`; `tentativas_por_provedor
    >= 1`. Levanta ValueError com a chave exata — nunca um valor default
    silencioso pra um cliente mal configurado."""
    provedores = config_ia["provedores"]
    for cliente in ClienteIA:
        efetiva = resolver_config_cliente(config_ia, cliente)
        for passo in efetiva["cadeia"]:
            if passo["provedor"] not in provedores:
                raise ValueError(
                    f"[IA] cliente '{cliente.value}': provedor '{passo['provedor']}' "
                    "não existe em config.json['ia']['provedores'].")
        if efetiva["timeout_s"] <= 0:
            raise ValueError(f"[IA] cliente '{cliente.value}': timeout_s deve ser > 0.")
        if efetiva["tentativas_por_provedor"] < 1:
            raise ValueError(f"[IA] cliente '{cliente.value}': tentativas_por_provedor deve ser >= 1.")
