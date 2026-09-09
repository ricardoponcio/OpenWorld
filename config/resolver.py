"""
MODULE: resolver.py
FUNÇÃO: Resolução central e estrita de configuração.

DESCRIÇÃO:
    Ponto único de acesso à configuração de todo o projeto (engine, cartografia,
    builder, web). Duas peças:

    - `get_config()`: retorna o dicionário raiz, carregado uma única vez por
      processo a partir da fonte configurada (ver `sources.py`). Trocar a fonte
      (JSON -> YAML/env/banco) não exige tocar em nenhum ponto de leitura.
    - `cfg_get()`: substituto de `dict.get(chave, default)` que NUNCA usa valores
      padrão silenciosos. Se a chave estiver ausente no caminho pedido, lança
      KeyError imediatamente — interrompendo a simulação com uma mensagem clara
      sobre o que falta corrigir, em vez de rodar silenciosamente com parâmetros
      errados/desatualizados.

USO:
    from config import cfg_get, get_config

    valor = cfg_get(get_config(), "biologia_e_sociedade", "concepcao_chance")
    bloco_cartografia = cfg_get(get_config(), "cartografia")

    # Para permitir fallback explícito (só em código de infraestrutura, nunca em
    # parâmetro de balanceamento):
    debug = cfg_get(get_config(), "debug_mode", default=False)
"""
import os
from .sources import ConfigSource, JsonFileConfigSource

_MISSING = object()  # Sentinela: distingue "não informado" de None explícito

_fonte: ConfigSource = None
_config_cache: dict = None


def _raiz_do_projeto() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def configurar_fonte(fonte: ConfigSource) -> None:
    """
    Troca a fonte de configuração usada por todo o projeto e invalida o cache,
    para que a próxima leitura já venha da nova fonte.
    """
    global _fonte, _config_cache
    _fonte = fonte
    _config_cache = None


def get_config() -> dict:
    """
    Retorna o dicionário raiz de configuração, carregado uma única vez por
    processo. Usa `JsonFileConfigSource(config.json)` por padrão se nenhuma
    fonte tiver sido configurada explicitamente via `configurar_fonte()`.
    """
    global _fonte, _config_cache
    if _fonte is None:
        _fonte = JsonFileConfigSource(os.path.join(_raiz_do_projeto(), "config.json"))
    if _config_cache is None:
        _config_cache = _fonte.carregar()
    return _config_cache


def carregar_config_global() -> dict:
    """Alias mantido pelo nome histórico usado pela engine antes desta migração."""
    return get_config()


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
        config:   Dicionário raiz do config (geralmente `get_config()` ou um sub-bloco).
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
