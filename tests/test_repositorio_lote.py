"""
Testes de `RepositorioLote` — docs/PLANO_CIDADE_VIVA.md T01.

Diferente de test_mecanicas.py (que usa um dublê de banco em memória), este arquivo
precisa de SQL de verdade: `reservar_livre` é uma sentença condicional pensada
especificamente pra correção sob concorrência, e isso só se prova contra um SQLite
real — um dublê nunca reproduziria uma condição de corrida de leitura-depois-escrita.
Usa um arquivo temporário (`tmp_path`), nunca `:memory:` — o pool de conexões de
`DatabaseManager` abre várias conexões, e cada conexão `:memory:` é seu próprio banco
isolado, não um banco compartilhado.
"""
from engine.database import DatabaseManager
from engine.models import Lote, LoteEstado


def _db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)


def _lote(lote_id, cidade_id=1, estado=LoteEstado.LIVRE.value):
    return Lote(id=lote_id, cidade_id=cidade_id, quarteirao_id="1_0", bairro="Centro",
                banda=1, classe_frente="principal", area_m2=180.0, x=0.0, y=0.0, estado=estado)


def test_reservar_livre_nao_entrega_o_mesmo_lote_duas_vezes(tmp_path):
    """T01 — o invariante central: duas chamadas de reservar_livre na mesma cidade com
    um único lote livre devolvem um id e None, nunca o mesmo id duas vezes."""
    db = _db(tmp_path)
    db.lotes.salvar_em_lote([_lote("cidade_1_0_l00")])

    primeiro = db.lotes.reservar_livre(cidade_id=1, npc_id="npc_a")
    segundo = db.lotes.reservar_livre(cidade_id=1, npc_id="npc_b")

    assert primeiro == "cidade_1_0_l00"
    assert segundo is None


def test_reservar_livre_prioriza_mais_proximo(tmp_path):
    db = _db(tmp_path)
    longe = _lote("longe"); longe.x, longe.y = 100.0, 0.0
    perto = _lote("perto"); perto.x, perto.y = 1.0, 0.0
    db.lotes.salvar_em_lote([longe, perto])

    escolhido = db.lotes.reservar_livre(cidade_id=1, npc_id="npc_a", perto_de=(0.0, 0.0))

    assert escolhido == "perto"


def test_contar_por_estado(tmp_path):
    db = _db(tmp_path)
    db.lotes.salvar_em_lote([
        _lote("l1", estado=LoteEstado.LIVRE.value),
        _lote("l2", estado=LoteEstado.LIVRE.value),
        _lote("l3", estado=LoteEstado.OCUPADO.value),
    ])

    contagem = db.lotes.contar_por_estado(cidade_id=1)

    assert contagem == {"livre": 2, "ocupado": 1}


def test_concluir_e_liberar(tmp_path):
    db = _db(tmp_path)
    db.lotes.salvar_em_lote([_lote("l1")])

    db.lotes.reservar_livre(cidade_id=1, npc_id="npc_a")
    db.lotes.concluir("l1", local_id="l1")
    assert db.lotes.contar_por_estado(1) == {"ocupado": 1}

    db.lotes.liberar("l1")
    assert db.lotes.contar_por_estado(1) == {"livre": 1}


def test_liberar_nao_atropela_lote_ja_reocupado(tmp_path):
    """T04: se alguém já reservou o lote de novo, `liberar` não pode voltar a marcá-lo
    livre por baixo do pé — só libera quando o estado ainda é 'ocupado'."""
    db = _db(tmp_path)
    db.lotes.salvar_em_lote([_lote("l1")])
    db.lotes.reservar_livre(cidade_id=1, npc_id="npc_a")
    db.lotes.concluir("l1", local_id="l1")
    db.lotes.liberar("l1")
    db.lotes.reservar_livre(cidade_id=1, npc_id="npc_b")  # alguém pegou de novo (estado='obra')

    db.lotes.liberar("l1")  # chamada tardia/duplicada de decay.py — não deve atropelar

    assert db.lotes.contar_por_estado(1) == {"obra": 1}
