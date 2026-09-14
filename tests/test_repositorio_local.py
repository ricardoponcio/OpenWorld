"""
M01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): `RepositorioLocal.criar`/`desativar`
incrementam `MetaChave.LOCAIS_VERSAO` na MESMA transação da escrita do local — é o
contador que `run_simulation.py` usa pra saber que precisa chamar
`SimulationEngine.recarregar_locais()`, sem recarregar 24 mil locais todo tick.
Precisa de SQLite de verdade (mesmo padrão de tests/test_repositorio_npc.py).
"""
from engine.core import SimulationEngine
from engine.database import DatabaseManager
from engine.models import MetaChave


def _db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)


def test_criar_incrementa_locais_versao(tmp_path):
    db = _db(tmp_path)
    assert db.meta.carregar(MetaChave.LOCAIS_VERSAO) is None

    db.locais.criar(id="loc_1", nome="Forja", tipo="Loja", cidade_id=1,
                     categoria="forja", descricao="", coordenadas=[0.0, 0.0])

    assert db.meta.carregar(MetaChave.LOCAIS_VERSAO) == "1"


def test_criar_duas_vezes_incrementa_duas_vezes(tmp_path):
    db = _db(tmp_path)
    db.locais.criar(id="loc_1", nome="Forja", tipo="Loja", cidade_id=1,
                     categoria="forja", descricao="", coordenadas=[0.0, 0.0])
    db.locais.criar(id="loc_2", nome="Taverna", tipo="Social", cidade_id=1,
                     categoria="taverna", descricao="", coordenadas=[1.0, 1.0])

    assert db.meta.carregar(MetaChave.LOCAIS_VERSAO) == "2"


def test_desativar_tambem_incrementa_a_versao(tmp_path):
    db = _db(tmp_path)
    db.locais.criar(id="loc_1", nome="Forja", tipo="Loja", cidade_id=1,
                     categoria="forja", descricao="", coordenadas=[0.0, 0.0])
    versao_apos_criar = db.meta.carregar(MetaChave.LOCAIS_VERSAO)

    db.locais.desativar("loc_1")

    assert db.meta.carregar(MetaChave.LOCAIS_VERSAO) == str(int(versao_apos_criar) + 1)


def test_recarregar_locais_percebe_local_criado_por_fora(tmp_path):
    """M01: simula o Modo Mestre (outro processo, mesmo banco) criando um local
    enquanto o processo da simulação já está de pé — `recarregar_locais()` tem que
    trazer o local novo pra `mundo.locais` E pro `mundo.indice`."""
    db_path = str(tmp_path / "teste.db")
    engine = SimulationEngine(db_path=db_path)
    assert "loc_mestre_1" not in engine.mundo.locais

    # "De fora": outra conexão com o MESMO arquivo, como o Modo Mestre faria.
    db_do_mestre = DatabaseManager(db_path=db_path, pool_size=2)
    db_do_mestre.locais.criar(id="loc_mestre_1", nome="Quartel do Mestre", tipo="Trabalho",
                               cidade_id=1, categoria="quartel", descricao="",
                               coordenadas=[10.0, 10.0], capacidade=8)

    engine.recarregar_locais()

    assert "loc_mestre_1" in engine.mundo.locais
    assert engine.mundo.locais["loc_mestre_1"].nome == "Quartel do Mestre"
