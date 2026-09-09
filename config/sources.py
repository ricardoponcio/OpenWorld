"""
MODULE: sources.py
FUNÇÃO: Fontes de configuração intercambiáveis.

DESCRIÇÃO:
    Cada fonte só sabe produzir o dicionário bruto de configuração — de onde quer
    que ele venha. Trocar de onde a configuração é lida (JSON local, YAML,
    variáveis de ambiente, uma tabela de banco de dados) é escrever uma nova
    classe aqui e apontar `resolver.configurar_fonte()` para ela; nenhum outro
    módulo do projeto (engine, cartografia, builder, web) precisa mudar.
"""
import json
from abc import ABC, abstractmethod


class ConfigSource(ABC):
    """Contrato mínimo que qualquer fonte de configuração deve cumprir."""

    @abstractmethod
    def carregar(self) -> dict:
        """Retorna o dicionário completo e atual de configuração."""
        raise NotImplementedError


class JsonFileConfigSource(ConfigSource):
    """Fonte padrão do projeto hoje: um único arquivo JSON no disco."""

    def __init__(self, caminho: str):
        self.caminho = caminho

    def carregar(self) -> dict:
        with open(self.caminho, "r", encoding="utf-8") as f:
            return json.load(f)
