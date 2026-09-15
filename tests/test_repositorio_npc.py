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


def test_buscar_ficha_resolve_nomes_de_pais_e_filhos(tmp_path):
    """P03 (docs/16_PLANO_PAINEL_E_IA.md): a ficha resolve mãe/pai/cônjuge (LEFT
    JOIN — cônjuge pode não existir) e filhos numa consulta só, sem varrer a
    tabela inteira em Python."""
    db = _db(tmp_path)
    mae = _npc("mae_1", nome="Mãe Um")
    pai = _npc("pai_1", nome="Pai Um")
    filho = _npc("filho_1", nome="Filho Um", mae_id="mae_1", pai_id="pai_1", estagio_vida=EstagioVida.CRIANCA.value)
    npc = _npc("npc_1", nome="NPC Um", mae_id="mae_1", pai_id="pai_1", conjuge_id="conjuge_inexistente")
    db.npcs.salvar_completo([mae, pai, filho, npc])

    ficha = db.npcs.buscar_ficha("npc_1")

    assert ficha["npc"]["mae_nome"] == "Mãe Um"
    assert ficha["npc"]["pai_nome"] == "Pai Um"
    assert ficha["npc"]["conjuge_nome"] is None  # cônjuge referenciado não existe no banco
    assert ficha["filhos"] == []  # npc_1 não tem filhos cadastrados

    # pai_1/mae_1 têm DOIS filhos cadastrados: filho_1 e o próprio npc_1 (mesmos pais)
    filhos_do_pai = db.npcs.buscar_ficha("pai_1")["filhos"]
    assert {f["id"] for f in filhos_do_pai} == {"filho_1", "npc_1"}


def test_buscar_ficha_de_npc_inexistente_devolve_none(tmp_path):
    db = _db(tmp_path)
    assert db.npcs.buscar_ficha("fantasma") is None


def test_listar_posicoes_respeita_limite_e_blocos(tmp_path):
    """M04 (docs/16_PLANO_PAINEL_E_IA.md): 2.000 locais (> 900, força mais de um
    bloco de `IN (...)`) e 3.000 NPCs vivos espalhados entre eles — `limite=1000`
    nunca devolve mais que 1.000 linhas, mesmo cruzando blocos."""
    from engine.models import Local

    db = _db(tmp_path)
    locais = [Local(id=f"local_{i}", nome=f"Local {i}", tipo="Casa") for i in range(2000)]
    db.locais.salvar_em_lote(locais)

    npcs = [_npc(f"npc_{i}", localizacao_atual_id=f"local_{i % 2000}") for i in range(3000)]
    db.npcs.salvar_completo(npcs)

    local_ids = [l.id for l in locais]
    resultado = db.npcs.listar_posicoes(local_ids, limite=1000)

    assert len(resultado) == 1000


def test_listar_posicoes_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    assert db.npcs.listar_posicoes([], limite=100) == []


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
