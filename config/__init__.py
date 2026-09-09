"""
Pacote de configuração central do OpenWorld.

Ponto único de resolução de parâmetros para engine, cartografia, builder e web.
A FONTE dos dados (hoje um único arquivo `config.json` na raiz) é intercambiável
sem tocar em nenhum outro módulo do projeto: implemente uma nova `ConfigSource`
em `sources.py` e troque-a via `configurar_fonte()` — todo o resto do código
continua lendo através de `cfg_get`/`get_config`, sem saber de onde os dados vêm.
"""
from .resolver import cfg_get, get_config, carregar_config_global, configurar_fonte
from .sources import ConfigSource, JsonFileConfigSource

__all__ = [
    "cfg_get",
    "get_config",
    "carregar_config_global",
    "configurar_fonte",
    "ConfigSource",
    "JsonFileConfigSource",
]
