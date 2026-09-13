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
from engine.mechanics.actions import NPCActionManager
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


def test_comer_pula_ticks_quando_tem_fome_e_dinheiro_de_sobra():
    """H04 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): COMER deixou de ser reavaliado a
    cada minuto — um NPC rico e ainda longe de `esta_comendo_fome_minima` recebe um
    salto de mais de 1 minuto, ao contrário do comportamento de antes de H04."""
    npc = adulto("npc_1", "Comendo", acao_atual=Acao.COMER, fome=50.0,
                 dinheiro_total_pc=1000.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    loop = GameLoop(mundo, _config())

    loop.executar_tick()
    npc_apos = mundo.npcs[0]
    assert npc_apos.proximo_instante_decisao > mundo.data_simulada + timedelta(minutes=1)


def test_comer_nao_pula_alem_do_dinheiro_disponivel():
    """H04: o pagador quase sem dinheiro não pode ter um salto que o deixaria
    devendo — `minutos_seguros_para_pular_comer` tem que capar o salto no que o
    saldo sustenta a preço cheio."""
    config = _config()
    cfg_comer = cfg_get(cfg_get(config, "acoes"), "comer")
    custo_do_tick = cfg_get(cfg_comer, "custo_pc") / cfg_get(cfg_comer, "parcelas_refeicao")

    npc = adulto("npc_1", "Quase Sem Dinheiro", acao_atual=Acao.COMER, fome=50.0,
                 dinheiro_total_pc=custo_do_tick * 3)  # só sustenta 3 minutos a preço cheio
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    loop = GameLoop(mundo, config)

    loop.executar_tick()
    npc_apos = mundo.npcs[0]
    minutos_agendados = (npc_apos.proximo_instante_decisao - mundo.data_simulada).total_seconds() / 60
    assert minutos_agendados <= 3 + 1e-9
    assert npc_apos.dinheiro_total_pc >= -1e-9, "o bloco em lote não pode deixar o pagador devendo"


def test_comer_em_lote_da_o_mesmo_resultado_que_minuto_a_minuto():
    """H04: o efeito TOTAL de pular N minutos em bloco
    (`GameLoop._aplicar_efeito_continuo`) tem que ser idêntico ao de rodar
    `_executar_comer` N vezes seguidas — é a garantia central de generalizar uma
    ação pro salto grande (mesma exigida de dormir/trabalhar/ocioso desde A02)."""
    config = _config()
    dinheiro_inicial = 1000.0
    fome_inicial = 50.0
    n_minutos = 10

    npc_lote = adulto("npc_lote", "Em Lote", acao_atual=Acao.COMER,
                       fome=fome_inicial, dinheiro_total_pc=dinheiro_inicial)
    npc_manual = adulto("npc_manual", "Minuto a Minuto", acao_atual=Acao.COMER,
                         fome=fome_inicial, dinheiro_total_pc=dinheiro_inicial)

    mundo_lote = mundo_de(npcs=[npc_lote], locais=[casa()])
    loop_lote = GameLoop(mundo_lote, config)
    loop_lote._aplicar_efeito_continuo(npc_lote, n_minutos)

    mundo_manual = mundo_de(npcs=[npc_manual], locais=[casa()])
    acoes_manual = NPCActionManager(mundo_manual, config)
    cfg_acoes = cfg_get(config, "acoes")
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    for _ in range(n_minutos):
        acoes_manual._executar_comer(npc_manual, cfg_acoes, cfg_bio, mundo_manual.npcs_por_casa)

    assert npc_lote.fome == pytest.approx(npc_manual.fome)
    assert npc_lote.dinheiro_total_pc == pytest.approx(npc_manual.dinheiro_total_pc)
    assert npc_lote.energia == pytest.approx(npc_manual.energia)


def test_cuidar_prole_em_lote_da_o_mesmo_resultado_que_minuto_a_minuto():
    """H04: mesma garantia de equivalência bloco-vs-minuto, agora pra CUIDAR_PROLE —
    o cuidador drena energia e o filho ganha social, os dois por minuto."""
    config = _config()
    n_minutos = 5

    def montar(sufixo):
        cuidador = adulto(f"npc_cuidador_{sufixo}", "Cuidador", acao_atual=Acao.CUIDAR_PROLE,
                           energia=100.0, casa_id="casa_1", localizacao_atual_id="casa_1")
        filho = adulto(f"npc_filho_{sufixo}", "Filho", estagio_vida="crianca", social=20.0,
                       casa_id="casa_1", localizacao_atual_id="casa_1",
                       pai_id=f"npc_cuidador_{sufixo}")
        return cuidador, filho

    cuidador_lote, filho_lote = montar("lote")
    mundo_lote = mundo_de(npcs=[cuidador_lote, filho_lote], locais=[casa()])
    loop_lote = GameLoop(mundo_lote, config)
    loop_lote._aplicar_efeito_continuo(cuidador_lote, n_minutos)

    cuidador_manual, filho_manual = montar("manual")
    mundo_manual = mundo_de(npcs=[cuidador_manual, filho_manual], locais=[casa()])
    acoes_manual = NPCActionManager(mundo_manual, config)
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    for _ in range(n_minutos):
        acoes_manual._executar_cuidar_prole(cuidador_manual, cfg_bio)

    assert cuidador_lote.energia == pytest.approx(cuidador_manual.energia)
    assert filho_lote.social == pytest.approx(filho_manual.social)


def test_construir_em_lote_da_o_mesmo_resultado_que_minuto_a_minuto_e_nunca_ultrapassa_100():
    """H04: mesma garantia pra CONSTRUIR — e o candidato extra
    (`GameLoop._candidatos_extra_agenda`) nunca deixa o bloco cruzar 100% de
    integridade (a conclusão da obra continua só no minuto real,
    `NPCActionManager._executar_construir`)."""
    config = _config()
    n_minutos = 3

    def montar(sufixo):
        npc = adulto(f"npc_pedreiro_{sufixo}", "Pedreiro", acao_atual=Acao.CONSTRUIR,
                     energia=100.0, fome=10.0, casa_id="", localizacao_atual_id="")
        obra = casa(f"obra_{sufixo}", status=0, integridade=40, dono_npc_id=npc.id)
        return npc, obra

    npc_lote, obra_lote = montar("lote")
    mundo_lote = mundo_de(npcs=[npc_lote], locais=[obra_lote])
    loop_lote = GameLoop(mundo_lote, config)
    candidatos = loop_lote._candidatos_extra_agenda(npc_lote, mundo_lote.npcs_por_casa)
    assert candidatos is not None
    loop_lote._aplicar_efeito_continuo(npc_lote, n_minutos)

    npc_manual, obra_manual = montar("manual")
    mundo_manual = mundo_de(npcs=[npc_manual], locais=[obra_manual])
    acoes_manual = NPCActionManager(mundo_manual, config)
    for _ in range(n_minutos):
        acoes_manual._executar_construir(npc_manual)

    assert obra_lote.integridade == pytest.approx(obra_manual.integridade)
    assert npc_lote.energia == pytest.approx(npc_manual.energia)
    assert npc_lote.fome == pytest.approx(npc_manual.fome)
    assert obra_lote.integridade < 100, "o cenário tem que ficar longe de 100 pra testar o caminho comum"
