"""
M01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): `sincronizar_locais_se_mudou` só chama
`SimulationEngine.recarregar_locais()` quando `MetaChave.LOCAIS_VERSAO` de fato mudou
desde a última checagem — um `SELECT` de uma linha todo tick é ruído; recarregar 24 mil
locais quando nada mudou não seria.
"""
from types import SimpleNamespace

import pytest

from run_simulation import RitmoDoLaco, sincronizar_locais_se_mudou


def _engine_com_versao(versao):
    recarregamentos = []
    engine = SimpleNamespace(
        mundo=SimpleNamespace(db=SimpleNamespace(meta=SimpleNamespace(carregar=lambda chave: versao))),
        recarregar_locais=lambda: recarregamentos.append(1),
    )
    engine.recarregamentos = recarregamentos
    return engine


def test_nao_recarrega_quando_versao_nao_muda():
    engine = _engine_com_versao("3")

    resultado = sincronizar_locais_se_mudou(engine, "3")

    assert resultado == "3"
    assert engine.recarregamentos == []


def test_recarrega_quando_versao_muda():
    engine = _engine_com_versao("4")

    resultado = sincronizar_locais_se_mudou(engine, "3")

    assert resultado == "4"
    assert engine.recarregamentos == [1]


# ----------------------------------------------------------------------
# RitmoDoLaco (D03, docs/16_PLANO_PAINEL_E_IA.md)
# ----------------------------------------------------------------------

def test_espera_desconta_duracao_do_tick():
    """Pedida 60× (1 s por minuto simulado): um tick de 0,3 s só precisa de mais
    0,7 s de espera pra fechar o segundo — não 1 s cheio como o laço antigo dormia."""
    assert RitmoDoLaco.espera_s(60.0, 0.3) == pytest.approx(0.7)


def test_espera_nunca_negativa():
    """Em velocidade alta o próprio tick já estoura o orçamento (60/21600 ≈ 2,8 ms);
    não dá pra "dormir menos que zero" pra compensar."""
    assert RitmoDoLaco.espera_s(21600.0, 0.1) == 0.0


def test_velocidade_efetiva_com_ticks_de_100ms_sem_espera_e_600x():
    ritmo = RitmoDoLaco(janela_ticks=120)
    for _ in range(10):
        ritmo.registrar_tick(0.1)

    assert ritmo.velocidade_efetiva() == pytest.approx(600.0)
    assert ritmo.ms_por_tick_medio() == pytest.approx(100.0)


def test_ritmo_sem_ticks_registrados_nao_quebra():
    """Antes do primeiro tick (ou logo após reiniciar o processo), a janela está
    vazia — nenhum método deve levantar exceção nem dividir por zero."""
    ritmo = RitmoDoLaco(janela_ticks=120)

    assert ritmo.velocidade_efetiva() == 0.0
    assert ritmo.ms_por_tick_medio() == 0.0
    assert ritmo.ms_por_tick_p95() == 0.0
