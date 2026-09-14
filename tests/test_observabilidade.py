"""
Testes de observabilidade — docs/16_PLANO_PAINEL_E_IA.md, Bloco O.

Cobre O01 (níveis de log vêm do config, e valor inválido derruba alto — ARQUITETURA
P4/P5), O02 (avisos por NPC viram contadores agregados do mundo) e O03 (coletor de
estatísticas e a formatação da linha de resumo do console).
"""
import copy

import pytest

from config import configurar_fonte, ConfigSource
from engine.config_loader import carregar_config_global, cfg_get
from engine.logger import WorldLogger


class _ConfigDeTeste(ConfigSource):
    """Fonte de config em memória — só para injetar um valor inválido sem tocar
    config.json nem depender de I/O."""

    def __init__(self, dados: dict):
        self._dados = dados

    def carregar(self) -> dict:
        return self._dados


@pytest.fixture
def config():
    return carregar_config_global()


def test_nivel_de_log_invalido_falha_alto(monkeypatch):
    """O01: `NivelLog(valor)` levanta na construção do logger quando o config traz
    um nível fora de DEBUG/INFO/WARNING/ERROR — falhar alto (ARQUITETURA P5), nunca
    rodar silenciosamente com um nível qualquer."""
    cfg_invalido = copy.deepcopy(carregar_config_global())
    cfg_invalido["observabilidade"]["log_arquivo_nivel"] = "VERBOSO"
    configurar_fonte(_ConfigDeTeste(cfg_invalido))
    WorldLogger._logger = None

    try:
        with pytest.raises(ValueError):
            WorldLogger.get_logger()
    finally:
        WorldLogger._logger = None
        configurar_fonte(None)
        carregar_config_global()  # força reler config.json de verdade antes do próximo teste
