"""
A01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): a espinha dorsal do Bloco A. Aplicar 480
minutos de metabolismo de uma vez tem que dar o MESMO resultado que aplicar 1 minuto
480 vezes — é o que permite ao Bloco A (agenda de decisões) pular tempo em vez de
processar todo NPC todo minuto (armadilha 11).

O sorteio de fome/social é mockado para um valor fixo: o objetivo aqui é provar que a
ARITMÉTICA da escala por `minutos` está certa, não comparar duas sequências de números
aleatórios independentes (que nunca seriam iguais — a redução de variância de um
sorteio só, em vez de N sorteios somados, é intencional e documentada em
`_aplicar_metabolismo`).
"""
import pytest

import engine.loop as loop_mod
from engine.config_loader import carregar_config_global
from engine.loop import GameLoop
from engine.models import Genero
from tests.mundo_sintetico import adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def _loop_com(npc_id, monkeypatch, valor_sorteio=0.02):
    monkeypatch.setattr(loop_mod.random, "uniform", lambda a, b: valor_sorteio)
    npc = adulto(npc_id, npc_id, genero=Genero.MASCULINO.value)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    return GameLoop(mundo, _config()), npc


def test_480_minutos_de_uma_vez_equivale_a_480_passos_de_um_minuto(monkeypatch):
    loop_salto, npc_salto = _loop_com("npc_salto", monkeypatch)
    loop_salto._aplicar_metabolismo(npc_salto, 480, [])

    loop_passos, npc_passos = _loop_com("npc_passos", monkeypatch)
    for _ in range(480):
        loop_passos._aplicar_metabolismo(npc_passos, 1, [])

    assert npc_salto.energia == pytest.approx(npc_passos.energia)
    assert npc_salto.fome == pytest.approx(npc_passos.fome)
    assert npc_salto.social == pytest.approx(npc_passos.social)


def test_gravidez_cruza_zero_mesmo_quando_o_salto_e_maior_que_o_restante(monkeypatch):
    monkeypatch.setattr(loop_mod.random, "uniform", lambda a, b: 0.0)
    npc = adulto("npc_gestante", "Gestante", genero=Genero.FEMININO.value, gravidez_ticks=3)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    loop = GameLoop(mundo, _config())

    maes_em_parto = []
    loop._aplicar_metabolismo(npc, 10, maes_em_parto)  # salto de 10 min, só 3 restavam

    assert npc.gravidez_ticks == 0
    assert maes_em_parto == [npc]


def test_gravidez_nao_dispara_parto_duas_vezes(monkeypatch):
    monkeypatch.setattr(loop_mod.random, "uniform", lambda a, b: 0.0)
    npc = adulto("npc_gestante", "Gestante", genero=Genero.FEMININO.value, gravidez_ticks=1)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    loop = GameLoop(mundo, _config())

    maes_em_parto = []
    loop._aplicar_metabolismo(npc, 1, maes_em_parto)
    loop._aplicar_metabolismo(npc, 1, maes_em_parto)  # já não está mais grávida

    assert maes_em_parto == [npc]
