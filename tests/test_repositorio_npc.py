"""
Testes de `RepositorioNPC.salvar_muitos` — docs/PLANO_CIDADE_VIVA.md P05.

Como em tests/test_repositorio_lote.py, precisa de SQLite de verdade (arquivo
temporário, nunca `:memory:` — o pool de conexões abre várias, cada `:memory:` seria um
banco isolado) pra provar que o `executemany` grava e lê de volta corretamente.
"""
from engine.database import DatabaseManager
from engine.models import NPC, EstagioVida


def _db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)


def _npc(npc_id, **campos):
    base = dict(id=npc_id, nome=f"NPC {npc_id}", profissao="Ferreiro",
                local_trabalho_id="", localizacao_atual_id="casa_1", casa_id="casa_1",
                cidade_id=1, estagio_vida=EstagioVida.ADULTO.value)
    base.update(campos)
    return NPC(**base)


def test_salvar_muitos_grava_todos_numa_transacao(tmp_path):
    db = _db(tmp_path)
    npcs = [_npc(f"npc_{i}") for i in range(5)]

    db.npcs.salvar_muitos(npcs)

    carregados = db.npcs.carregar_todos()
    assert {n.id for n in carregados} == {f"npc_{i}" for i in range(5)}


def test_salvar_muitos_atualiza_registros_existentes(tmp_path):
    db = _db(tmp_path)
    npc = _npc("npc_1", energia=100.0)
    db.npcs.salvar_muitos([npc])

    npc.energia = 42.0
    db.npcs.salvar_muitos([npc])

    recarregado = db.npcs.carregar_todos()[0]
    assert recarregado.energia == 42.0


def test_salvar_muitos_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    db.npcs.salvar_muitos([])  # não deve levantar exceção nem tocar o banco
    assert db.npcs.carregar_todos() == []
