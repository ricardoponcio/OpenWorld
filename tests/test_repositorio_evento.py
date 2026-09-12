"""
E01 (docs/PLANO_POPULACAO_E_ESCALA.md): `RepositorioEvento.salvar_muitos` — uma
transação pra todos os eventos do tick, não um commit por evento. Precisa de SQLite
de verdade (mesmo padrão de tests/test_repositorio_npc.py).
"""
from engine.database import DatabaseManager
from engine.models import Evento


def _db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)


def _evento(evento_id, **campos):
    base = dict(id=evento_id, timestamp="Dia 1, 08:00", local_id="local_1",
                envolvidos=["npc_1"], tipo_evento="CONVERSA",
                modificador_afinidade=5, resumo_estruturado="Um evento de teste.")
    base.update(campos)
    return Evento(**base)


def test_salvar_muitos_grava_todos_numa_transacao(tmp_path):
    db = _db(tmp_path)
    eventos = [_evento(f"evt_{i}") for i in range(5)]

    db.eventos.salvar_muitos(eventos)

    recentes = db.eventos.listar_recentes(10)
    assert len(recentes) == 5


def test_salvar_muitos_lista_vazia_nao_quebra(tmp_path):
    db = _db(tmp_path)
    db.eventos.salvar_muitos([])
    assert db.eventos.listar_recentes(10) == []


def test_podar_por_idade_remove_so_os_mais_velhos_que_o_corte(tmp_path):
    """E02: 'Dia N' anterior ao corte some; 'Dia N' igual ou depois do corte fica."""
    db = _db(tmp_path)
    db.eventos.salvar_muitos([
        _evento("evt_velho", timestamp="Dia 1, 08:00"),
        _evento("evt_na_borda", timestamp="Dia 10, 08:00"),
        _evento("evt_novo", timestamp="Dia 20, 08:00"),
    ])

    apagadas = db.eventos.podar_por_idade(dia_de_corte=10)

    assert apagadas == 1
    restantes = {r["timestamp"] for r in db.eventos.listar_recentes(10)}
    assert restantes == {"Dia 10, 08:00", "Dia 20, 08:00"}


def test_podar_por_idade_nao_toca_eventos_globais(tmp_path):
    db = _db(tmp_path)
    db.eventos.salvar_muitos([_evento("evt_velho", timestamp="Dia 1, 08:00")])
    db.eventos.salvar_global("evg_1", "Praga", "desc", "clima", "", "{}", duracao=999)

    db.eventos.podar_por_idade(dia_de_corte=100)

    assert db.eventos.listar_recentes(10) == []
    assert len(db.eventos.carregar_globais_ativos()) == 1
