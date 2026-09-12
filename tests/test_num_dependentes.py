"""
N04 (docs/PLANO_POPULACAO_E_ESCALA.md): `GameLoop._atualizar_dependentes` só recalcula
`num_dependentes` para as casas cuja composição mudou desde o fim do tick anterior — e
não é um "cache entre ticks" na acepção proibida (Anexo 3, docs/
PLANO_POPULACAO_E_ESCALA.md): é escopo de tick, como `npcs_por_casa` (P03). Escrito
antes de considerar a tarefa terminada, como o plano pede para qualquer coisa "onde um
bug fica escondido por muitos ticks antes de aparecer".

A correção do parto-no-mesmo-tick é validada em `tests/test_persistencia.py` (precisa
de SQLite de verdade: `processar_parto` recarrega `mundo.npcs` do banco, e o dublê
`BancoFalso` usado aqui não guarda estado nenhum entre um `salvar` e o `carregar_todos`
seguinte)."""
from engine.config_loader import carregar_config_global
from engine.loop import GameLoop
from engine.models import Genero

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
    `carregar_todos()`), todos com `num_dependentes` no default 0. Mesmo sem nenhuma
    mudança de composição de verdade, a troca de lista tem que forçar um recálculo —
    senão o valor fica preso em 0 pra sempre."""
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
    assert mae_recarregada.num_dependentes == 0

    loop.executar_tick()
    assert next(n for n in mundo.npcs if n.id == "npc_mae").num_dependentes == 1
