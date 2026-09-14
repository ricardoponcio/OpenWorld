"""
Testes de `JobMarket` (mercado de trabalho) contra SQLite de verdade — precisa do
schema real e dos dados de domínio (profissões/mapeamento categoria->sistema), então
usa `SemeadorDeDominio.aplicar` como `builder/populate.py` faz (mesmo padrão de
tests/test_repositorio_npc.py: arquivo temporário, nunca `:memory:`).

docs/15_PLANO_MUNDO_CRIVEL.md, Bloco V (V02/V03): antes desta tarefa, 87,4% das vagas
do mundo medido eram residências (`buscar_vagas_disponiveis` filtrava por
`tipo != 'Casa'`, não por categoria empregadora), e todo contratado sem profissão
mapeada virava "Desempregado" mesmo tendo sido contratado.
"""
from engine.database import DatabaseManager
from engine.repositorios.seed import SemeadorDeDominio
from engine.mechanics.market import JobMarket
from engine.models import Local, NPC, CategoriaLocal, EstagioVida, ProfissaoID
from config import get_config


def _db(tmp_path):
    db = DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)
    SemeadorDeDominio.aplicar(db)
    return db


def _local(local_id, cidade_id, categoria, capacidade=5, status=1):
    return Local(id=local_id, nome=local_id, tipo="Outro", cidade_id=cidade_id,
                 categoria=categoria, capacidade=capacidade, status=status)


def _candidato(npc_id, cidade_id, casa_id="casa_1"):
    return NPC(id=npc_id, nome=npc_id, profissao="Aldeão", profissao_id=ProfissaoID.OCIOSO.value,
               local_trabalho_id="", localizacao_atual_id=casa_id, casa_id=casa_id,
               cidade_id=cidade_id, estagio_vida=EstagioVida.ADULTO.value)


def test_vaga_nunca_e_residencia_nem_outra_cidade(tmp_path):
    db = _db(tmp_path)
    db.locais.salvar_em_lote([
        _local("casa_1", 1, CategoriaLocal.RESIDENCIA.value),
        _local("forja_1", 1, CategoriaLocal.FORJA.value),
        _local("forja_2", 2, CategoriaLocal.FORJA.value),
    ])
    db.npcs.salvar_completo([_candidato("npc_1", cidade_id=1)])

    JobMarket(db, get_config()).processar_contratacoes()

    contratado = db.npcs.carregar_todos()[0]
    assert contratado.local_trabalho_id == "forja_1"


def test_contratado_nunca_fica_desempregado(tmp_path):
    """V03: contratar e chamar de 'Desempregado' é pior que não contratar — o
    fallback silencioso `prof_por_cat.get(cat, (OCIOSO, 'Desempregado'))` foi
    removido; toda vaga oferecida já tem profissão mapeada de verdade."""
    db = _db(tmp_path)
    db.locais.salvar_em_lote([_local("forja_1", 1, CategoriaLocal.FORJA.value)])
    db.npcs.salvar_completo([_candidato("npc_1", cidade_id=1)])

    JobMarket(db, get_config()).processar_contratacoes()

    contratado = db.npcs.carregar_todos()[0]
    assert contratado.local_trabalho_id != ""
    assert contratado.profissao_id != ProfissaoID.OCIOSO.value
    assert contratado.profissao != "Desempregado"
