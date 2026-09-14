"""
Testes de observabilidade — docs/16_PLANO_PAINEL_E_IA.md, Bloco O.

Cobre O01 (níveis de log vêm do config, e valor inválido derruba alto — ARQUITETURA
P4/P5), O02 (avisos por NPC viram contadores agregados do mundo) e O03 (coletor de
estatísticas e a formatação da linha de resumo do console).
"""
import copy
from datetime import datetime

import pytest

from config import configurar_fonte, ConfigSource
from engine.config_loader import carregar_config_global, cfg_get
from engine.loop import GameLoop
from engine.logger import WorldLogger
from engine.mechanics.estatisticas import ColetorDeEstatisticas, formatar_resumo_console
from engine.models import Acao, Cidade, ContadorMundo
from tests.mundo_sintetico import adulto, casa, mundo_de


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


def test_inanicao_conta_em_vez_de_logar(config):
    """O02: 42.476 linhas de warning de inanição numa amostra de log — uma por NPC
    faminto, por tick. Vira estatística agregada (`ContadorMundo.MINUTO_EM_INANICAO`),
    lida pelo coletor (O03); o NPC continua perdendo saúde igual."""
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    limiar = cfg_get(cfg_bio, "inaniacao_fome_limiar")

    faminto = adulto("npc_1", "Faminto", acao_atual=Acao.DORMIR, fome=limiar + 5.0)
    mundo = mundo_de(npcs=[faminto], locais=[casa()])
    mundo.data_simulada = datetime(2026, 1, 1, 23, 0)
    loop = GameLoop(mundo, config)

    loop.executar_tick()  # primeiro tick: NPC novo está sempre em npcs_sem_agenda

    assert mundo.contadores[ContadorMundo.MINUTO_EM_INANICAO] == 1


def test_coletor_conta_desempregados_por_cidade(config):
    cidade1 = Cidade(1, "uuid", "Cidade Um", "pequena", "vila", 0, 0)
    cidade2 = Cidade(2, "uuid", "Cidade Dois", "pequena", "vila", 100, 100)
    empregado_a = adulto("npc_1", "Empregado A", cidade_id=1, local_trabalho_id="loc_forja")
    empregado_b = adulto("npc_2", "Empregado B", cidade_id=1, local_trabalho_id="loc_forja")
    desempregado = adulto("npc_3", "Desempregado", cidade_id=2, local_trabalho_id="")
    mundo = mundo_de(npcs=[empregado_a, empregado_b, desempregado], locais=[casa()],
                     cidades=[cidade1, cidade2])

    stats = ColetorDeEstatisticas(mundo, config).montar()

    assert stats["por_cidade"][1]["empregados"] == 2
    assert stats["por_cidade"][1]["desempregados"] == 0
    assert stats["por_cidade"][2]["empregados"] == 0
    assert stats["por_cidade"][2]["desempregados"] == 1
    assert stats["total"]["empregados"] == 2
    assert stats["total"]["desempregados"] == 1


def test_formatar_resumo_console_mostra_velocidade_pedida_e_efetiva():
    estatisticas = {
        "total": {"vivos_por_estagio": {"adulto": 10}, "desempregados": 3, "famintos": 1},
        "hoje": {"nascimento": 2, "obito_velhice": 1, "obito_saude": 0},
        "desempenho": {"velocidade_pedida": 21600.0, "velocidade_efetiva": 153.0,
                       "ms_por_tick_medio": 392.0},
    }

    linha = formatar_resumo_console(estatisticas)

    assert "153× efetivo (pedido 21600×)" in linha
    assert "392 ms/tick" in linha
    assert "vivos 10" in linha
    assert "desempregados 3" in linha
    assert "famintos 1" in linha
    assert "hoje: +2 nasc. / -1 óbitos" in linha


def test_formatar_resumo_console_sem_desempenho_ainda_nao_quebra():
    """Antes de D03 entregar ms_por_tick/velocidade_efetiva, `desempenho` só tem
    `velocidade_pedida` (ou nem existe) — a linha mostra um placeholder, não lança."""
    estatisticas = {
        "total": {"vivos_por_estagio": {"adulto": 1}, "desempregados": 0, "famintos": 0},
        "hoje": {},
    }

    linha = formatar_resumo_console(estatisticas)

    assert "medindo…" in linha
