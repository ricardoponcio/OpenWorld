"""
MODULE: config_loader.py
FUNÇÃO: Leitura estrita de configuração do mundo.

DESCRIÇÃO:
    Fornece a função `cfg_get` como substituto de `dict.get(chave, default)`.
    A principal diferença: NUNCA usa valores padrão silenciosos.
    Se a chave estiver ausente no config.json, um KeyError é lançado imediatamente,
    interrompendo a simulação com uma mensagem clara sobre o que falta corrigir.

    Isso evita que a simulação rode com parâmetros errados/desatualizados sem aviso,
    o que seria muito pior do que um crash explícito.

USO:
    from engine.config_loader import cfg_get

    # Em vez de:
    valor = engine.config.get("biologia_e_sociedade", {}).get("concepcao_chance", 0.20)

    # Use:
    valor = cfg_get(engine.config, "biologia_e_sociedade", "concepcao_chance")

    # Para chave de primeiro nível:
    bloco = cfg_get(engine.config, "biologia_e_sociedade")
"""


_MISSING = object()  # Sentinela: distingue "não informado" de None explícito


def cfg_get(config: dict, *keys: str, default=_MISSING):
    """
    Navega hierarquicamente pelo dicionário de configuração e retorna o valor final.

    Comportamento ESTRITO (padrão — use para parâmetros de simulação):
        Lança KeyError com mensagem detalhada se qualquer chave do caminho estiver ausente.
        É intencional: a simulação deve parar em vez de rodar com valores errados.

    Comportamento PERMISSIVO (use APENAS para código de infraestrutura/sistema):
        Passe `default=<valor>` explicitamente. Isso documenta no próprio código que o
        fallback é intencional e não uma preguiça de configuração.

        Exemplos válidos:
            cfg_get(cfg, "salvar_logs_npc_no_banco", default=True)   # logger sem engine
            cfg_get(cfg, "debug_mode", default=False)                 # flag opcional de dev

        Exemplos INVÁLIDOS (use cfg_get sem default):
            cfg_get(cfg, "concepcao_chance", default=0.20)  ← ERRADO: parâmetro de simulação

    Parâmetros:
        config:   Dicionário raiz do config (engine.config ou sub-bloco).
        *keys:    Sequência de chaves do caminho. Ex: "biologia_e_sociedade", "concepcao_chance"
        default:  Se fornecido explicitamente, é retornado quando a chave não existe.
                  Omitir este parâmetro ativa o comportamento estrito (KeyError).

    Retorna:
        O valor encontrado no caminho especificado, ou `default` se fornecido e ausente.

    Lança:
        KeyError: Se qualquer parte do caminho não existir e `default` não foi fornecido.
    """
    current = config
    path = []
    for key in keys:
        path.append(key)
        if not isinstance(current, dict):
            if default is not _MISSING:
                return default
            raise KeyError(
                f"[CONFIG] Caminho '{' → '.join(path[:-1])}' não é um dicionário. "
                f"Verifique config.json."
            )
        if key not in current:
            if default is not _MISSING:
                return default
            raise KeyError(
                f"[CONFIG] Chave obrigatória '{' → '.join(path)}' não encontrada em config.json. "
                f"Adicione esta chave antes de iniciar a simulação."
            )
        current = current[key]
    return current

