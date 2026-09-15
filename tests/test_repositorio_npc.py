"""
Testes de `RepositorioNPC.salvar_completo`/`salvar_muitos` — docs/12_PLANO_CIDADE_VIVA.md
P05 e docs/13_PLANO_POPULACAO_E_ESCALA.md N02.

Como em tests/test_repositorio_lote.py, precisa de SQLite de verdade (arquivo
temporário, nunca `:memory:` — o pool de conexões abre várias, cada `:memory:` seria um
banco isolado) pra provar que o `executemany` grava e lê de volta corretamente.
"""
from engine.database import DatabaseManager
from engine.models import NPC, EstagioVida
from engine.repositorios.npc import FiltroHabitantes


def _db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)


def _npc(npc_id, **campos):
    base = dict(id=npc_id, nome=f"NPC {npc_id}", profissao="Ferreiro",
                local_trabalho_id="", localizacao_atual_id="casa_1", casa_id="casa_1",
                cidade_id=1, estagio_vida=EstagioVida.ADULTO.value)
    base.update(campos)
    return NPC(**base)


def test_salvar_completo_grava_todos_numa_transacao(tmp_path):
    db = _db(tmp_path)
    npcs = [_npc(f"npc_{i}") for i in range(5)]

    db.npcs.salvar_completo(npcs)

    carregados = db.npcs.carregar_todos()
    assert {n.id for n in carregados} == {f"npc_{i}" for i in range(5)}


def test_salvar_completo_atualiza_registros_existentes(tmp_path):
    db = _db(tmp_path)
    npc = _npc("npc_1", energia=100.0)
    db.npcs.salvar_completo([npc])

    npc.energia = 42.0
    npc.profissao = "Alfaiate"
    db.npcs.salvar_completo([npc])

    recarregado = db.npcs.carregar_todos()[0]
    assert recarregado.energia == 42.0
    assert recarregado.profissao == "Alfaiate"


def test_salvar_completo_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    db.npcs.salvar_completo([])  # não deve levantar exceção nem tocar o banco
    assert db.npcs.carregar_todos() == []


def test_salvar_muitos_atualiza_so_as_colunas_quentes(tmp_path):
    """N02: `salvar_muitos` (a escrita de fim de tick) é um UPDATE estreito — muda
    energia/fome/social/saude/humor/acao_atual/localizacao_atual_id, e NÃO toca em
    colunas frias como `profissao` ou `relacionamentos`."""
    db = _db(tmp_path)
    npc = _npc("npc_1", energia=100.0, profissao="Ferreiro")
    db.npcs.salvar_completo([npc])

    npc.energia = 42.0
    npc.profissao = "Alfaiate"  # coluna fria — não deve ser persistida por salvar_muitos
    db.npcs.salvar_muitos([npc])

    recarregado = db.npcs.carregar_todos()[0]
    assert recarregado.energia == 42.0
    assert recarregado.profissao == "Ferreiro"


def test_dinheiro_e_gravidez_sobrevivem_a_recarga(tmp_path):
    """P02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco P): `dinheiro_total_pc`/
    `gravidez_ticks` mudam a cada minuto simulado (trabalhar/comer/socializar;
    gestação) e ficaram de fora de `_COLUNAS_QUENTES` por engano — o reload de
    `run_simulation.py` (a cada 5h) restaurava os dois pro valor gravado no
    povoamento, apagando um dia de trabalho e travando toda gravidez em 0%
    (§4 do documento)."""
    db = _db(tmp_path)
    npc = _npc("npc_1", dinheiro_total_pc=500.0, gravidez_ticks=0)
    db.npcs.salvar_completo([npc])

    npc.dinheiro_total_pc = 1234.5
    npc.gravidez_ticks = 1500
    db.npcs.salvar_muitos([npc])

    recarregado = db.npcs.carregar_todos()[0]
    assert recarregado.dinheiro_total_pc == 1234.5
    assert recarregado.gravidez_ticks == 1500


def test_salvar_muitos_em_npc_inexistente_nao_cria_linha(tmp_path):
    """A armadilha que N02 documenta: `salvar_muitos` é UPDATE, não INSERT OR REPLACE
    — numa linha que não existe, não faz nada, silenciosamente."""
    db = _db(tmp_path)
    npc = _npc("npc_fantasma")

    db.npcs.salvar_muitos([npc])

    assert db.npcs.carregar_todos() == []


def test_salvar_muitos_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    db.npcs.salvar_muitos([])  # não deve levantar exceção nem tocar o banco
    assert db.npcs.carregar_todos() == []


def test_salvar_relacionamentos_muitos_grava_as_duas_direcoes(tmp_path):
    """E01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): uma transação pra todos os pares de
    relacionamento do tick — cada par grava as DUAS direções, igual a
    `salvar_relacionamento` chamado par a par."""
    db = _db(tmp_path)
    pares = [("npc_1", "npc_2", 10, "conhecido"), ("npc_3", "npc_4", -5, "rival")]

    db.npcs.salvar_relacionamentos_muitos(pares)

    assert [tuple(r) for r in db.npcs.listar_relacionamentos("npc_1")] == [("npc_2", 10, "conhecido")]
    assert [tuple(r) for r in db.npcs.listar_relacionamentos("npc_2")] == [("npc_1", 10, "conhecido")]
    assert [tuple(r) for r in db.npcs.listar_relacionamentos("npc_4")] == [("npc_3", -5, "rival")]


def test_salvar_relacionamentos_muitos_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    db.npcs.salvar_relacionamentos_muitos([])
    assert db.npcs.listar_relacionamentos("npc_1") == []


def test_listar_habitantes_pagina_e_filtra_por_cidade(tmp_path):
    """P02 (docs/16_PLANO_PAINEL_E_IA.md): filtro e paginação feitos no SQL, não
    no JS — 60 NPCs na cidade 1 (nomes 'C1 NPC 00'..'C1 NPC 59', ordenáveis por
    nome) e 60 na cidade 2; página 2 de 50 da cidade 1 devolve só os 10
    restantes, e contar_habitantes bate com o total real da cidade."""
    db = _db(tmp_path)
    npcs = ([_npc(f"c1_{i}", nome=f"C1 NPC {i:02d}", cidade_id=1) for i in range(60)]
            + [_npc(f"c2_{i}", nome=f"C2 NPC {i:02d}", cidade_id=2) for i in range(60)])
    db.npcs.salvar_completo(npcs)

    filtro = FiltroHabitantes(cidade_id=1, pagina=2, por_pagina=50)
    pagina = db.npcs.listar_habitantes(filtro)

    assert db.npcs.contar_habitantes(filtro) == 60
    assert [r["nome"] for r in pagina] == [f"C1 NPC {i:02d}" for i in range(50, 60)]


def test_busca_por_nome_nao_aceita_injecao(tmp_path):
    """Busca monta `nome LIKE ?` com parâmetro — nunca f-string com o texto do
    usuário (ARQUITETURA §15 item 4)."""
    db = _db(tmp_path)
    db.npcs.salvar_completo([_npc("npc_1", nome="Thorne")])

    filtro = FiltroHabitantes(busca_nome="'; DROP TABLE npcs; --")

    assert db.npcs.contar_habitantes(filtro) == 0
    assert db.npcs.listar_habitantes(filtro) == []
    # A tabela continua existindo e com o NPC original intacto.
    assert len(db.npcs.carregar_todos()) == 1
