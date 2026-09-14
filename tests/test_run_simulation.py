"""
M01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): `sincronizar_locais_se_mudou` só chama
`SimulationEngine.recarregar_locais()` quando `MetaChave.LOCAIS_VERSAO` de fato mudou
desde a última checagem — um `SELECT` de uma linha todo tick é ruído; recarregar 24 mil
locais quando nada mudou não seria.
"""
from types import SimpleNamespace

from run_simulation import sincronizar_locais_se_mudou


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
