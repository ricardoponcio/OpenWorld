"""
N04 (docs/13_PLANO_POPULACAO_E_ESCALA.md): `GameLoop._atualizar_dependentes` só recalcula
`num_dependentes` para as casas cuja composição mudou desde o fim do tick anterior — e
não é um "cache entre ticks" na acepção proibida (Anexo 3, docs/
13_PLANO_POPULACAO_E_ESCALA.md): é escopo de tick, como `npcs_por_casa` (P03). Escrito
antes de considerar a tarefa terminada, como o plano pede para qualquer coisa "onde um
bug fica escondido por muitos ticks antes de aparecer".

A correção do parto-no-mesmo-tick é validada em `tests/test_persistencia.py`, com
SQLite de verdade (cobre também a persistência, N02/W03)."""
from datetime import datetime, timedelta

from engine.config_loader import carregar_config_global, cfg_get
from engine.loop import GameLoop
from engine.models import EstagioVida, Genero

from tests.mundo_sintetico import adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def test_casa_sem_mudanca_mantem_num_dependentes_entre_ticks():
    mae = adulto("npc_mae", "Mãe Estável", genero=Genero.FEMININO.value,
                 data_nascimento="1980-01-01T00:00:00")
    bebe = adulto("npc_bebe", "Bebê Estável", estagio_vida="bebe",
                  data_nascimento="2026-08-01T00:00:00", mae_id="npc_mae")
    mundo = mundo_de(npcs=[mae, bebe], locais=[casa(capacidade=5)])

    loop = GameLoop(mundo, _config())
    loop.executar_tick()
    primeiro = next(n for n in mundo.npcs if n.id == "npc_mae").num_dependentes
    assert primeiro == 1

    for _ in range(5):
        loop.executar_tick()
    depois = next(n for n in mundo.npcs if n.id == "npc_mae").num_dependentes
    assert depois == 1


def test_lista_de_npcs_trocada_forca_recalculo_total():
    """Simula o que `SimulationEngine.recarregar_habitantes()` faz: substitui
    `mundo.npcs` por uma lista de objetos NOVOS (como se tivessem vindo de um
    `carregar_todos()`), todos com `num_dependentes` no default 0, e reconstrói os
    índices mantidos (A04) — é o que `recarregar_habitantes()` faz de verdade desde
    A04, exatamente para evitar o que este teste prova: mesmo sem nenhuma mudança de
    composição real, a troca de lista tem que forçar um recálculo, senão o valor fica
    preso em 0 pra sempre."""
    mae = adulto("npc_mae", "Mãe Realocada", genero=Genero.FEMININO.value,
                 data_nascimento="1980-01-01T00:00:00")
    bebe = adulto("npc_bebe", "Bebê Realocado", estagio_vida="bebe",
                  data_nascimento="2026-08-01T00:00:00", mae_id="npc_mae")
    mundo = mundo_de(npcs=[mae, bebe], locais=[casa(capacidade=5)])

    loop = GameLoop(mundo, _config())
    loop.executar_tick()
    assert next(n for n in mundo.npcs if n.id == "npc_mae").num_dependentes == 1

    # "Reload": mesmos dados, objetos NPC novos — num_dependentes volta ao default.
    mae_recarregada = adulto("npc_mae", "Mãe Realocada", genero=Genero.FEMININO.value,
                              data_nascimento="1980-01-01T00:00:00")
    bebe_recarregado = adulto("npc_bebe", "Bebê Realocado", estagio_vida="bebe",
                               data_nascimento="2026-08-01T00:00:00", mae_id="npc_mae")
    mundo.npcs = [mae_recarregada, bebe_recarregado]
    mundo._reconstruir_indices_de_npc()  # A04: o que recarregar_habitantes() faz
    assert mae_recarregada.num_dependentes == 0

    loop.executar_tick()
    assert next(n for n in mundo.npcs if n.id == "npc_mae").num_dependentes == 1


def test_crescer_para_adulto_suja_a_casa_sem_passar_pelas_portas_de_mundo():
    """H02 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 15): a única mutação que
    muda `NPC.eh_dependente()` sem passar por `mudar_casa`/`registrar_npc`/
    `remover_npc` é o crescimento (criança vira adulto, `NPCLifecycleManager.
    processar_crescimento`) — se ele esquecesse de marcar a casa suja, o
    `num_dependentes` da mãe ficaria travado em 1 pra sempre, mesmo com o filho já
    adulto e morando na mesma casa."""
    config = _config()
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    hora_crescimento = cfg_get(cfg_bio, "crescimento_hora")
    dias_para_adulto = cfg_get(cfg_bio, "crescimento_dias_crianca_para_adulto")

    mae = adulto("npc_mae", "Mãe", genero=Genero.FEMININO.value,
                 data_nascimento="1980-01-01T00:00:00")
    filho = adulto("npc_filho", "Filho Quase Adulto", estagio_vida=EstagioVida.CRIANCA.value,
                   mae_id="npc_mae")
    mundo = mundo_de(npcs=[mae, filho], locais=[casa(capacidade=5)])
    # Nasceu exatamente `dias_para_adulto` dias atrás, na mesma hora do corte —
    # o próximo tick que cruzar `hora_crescimento` já processa a maioridade.
    agora = datetime(2026, 1, 1, hora_crescimento, 0)
    filho.data_nascimento = (agora - timedelta(days=dias_para_adulto)).isoformat()
    mundo.data_simulada = agora - timedelta(minutes=1)

    loop = GameLoop(mundo, config)
    loop.executar_tick()

    filho_atual = next(n for n in mundo.npcs if n.id == "npc_filho")
    mae_atual = next(n for n in mundo.npcs if n.id == "npc_mae")
    assert filho_atual.estagio_vida == EstagioVida.ADULTO.value
    assert mae_atual.num_dependentes == 0
