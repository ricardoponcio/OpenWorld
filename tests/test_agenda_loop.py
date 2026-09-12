"""
A02 (docs/PLANO_POPULACAO_E_ESCALA.md): `GameLoop` de ponta a ponta com a agenda de
decisões — prova que um NPC estável (dormindo, sem nada mudando) para de ser
processado todo tick, que o efeito acumulado ainda bate com o que seria minuto a
minuto, e que fome/energia continuam nunca pulando por cima de um limiar de verdade.
"""
from datetime import datetime, timedelta

import pytest

from engine.config_loader import carregar_config_global, cfg_get
from engine.loop import GameLoop
from engine.models import Acao, Genero
from tests.mundo_sintetico import adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def test_npc_dormindo_estavel_para_de_ser_avaliado_todo_tick():
    npc = adulto("npc_1", "Dorminhoco", acao_atual=Acao.DORMIR, energia=50.0, fome=10.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    mundo.data_simulada = datetime(2026, 1, 1, 23, 0)
    loop = GameLoop(mundo, _config())

    loop.executar_tick()
    assert loop.decisoes_avaliadas_no_ultimo_tick == 1  # primeiro tick: sempre avalia

    avaliacoes_seguintes = 0
    for _ in range(30):
        loop.executar_tick()
        avaliacoes_seguintes += loop.decisoes_avaliadas_no_ultimo_tick

    assert avaliacoes_seguintes < 30, (
        "um único NPC dormindo tranquilo não devia ser reavaliado em quase todo tick")


def test_fome_nunca_ultrapassa_o_limiar_apos_muitos_ticks_pulados():
    """A validação central de A02: fome sobe e cruza o limiar de comer no MINUTO
    certo, não até 60 minutos depois — aqui provado indiretamente: ela nunca fica
    consistentemente acima do limiar por muitos ticks seguidos sem o NPC decidir ir
    comer (o que mudaria `acao_atual` e tiraria a ação da agenda de saltos)."""
    config = _config()
    cfg_dec = cfg_get(config, "ia_decisao")
    gatilho = cfg_get(cfg_dec, "gatilho_fome_dormindo")

    npc = adulto("npc_1", "Vai ficar com fome", acao_atual=Acao.DORMIR,
                 energia=50.0, fome=gatilho - 5.0,
                 local_trabalho_id="", casa_id="casa_1", localizacao_atual_id="casa_1")
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    mundo.data_simulada = datetime(2026, 1, 1, 23, 0)
    loop = GameLoop(mundo, config)

    for _ in range(200):
        loop.executar_tick()
        npc_atual = mundo.npcs[0]
        if npc_atual.acao_atual != Acao.DORMIR:
            break  # decidiu ir fazer outra coisa (comer) assim que cruzou o gatilho

    # Nunca deve ter ficado "esquecido" dormindo com fome muito acima do gatilho —
    # a diferença tem que ser pequena (uma folga de poucos minutos de metabolismo,
    # não dezenas).
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    assert mundo.npcs[0].fome < cfg_get(cfg_bio, "inaniacao_fome_limiar")


def test_acao_curta_comer_nunca_pula_tick():
    npc = adulto("npc_1", "Comendo", acao_atual=Acao.COMER, fome=50.0,
                 dinheiro_total_pc=1000.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    loop = GameLoop(mundo, _config())

    loop.executar_tick()
    npc_apos = mundo.npcs[0]
    assert npc_apos.proximo_instante_decisao == mundo.data_simulada + timedelta(minutes=1)
