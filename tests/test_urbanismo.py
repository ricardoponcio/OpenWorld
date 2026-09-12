"""
Testes de `GerenciadorUrbanismo` — docs/PLANO_CIDADE_VIVA.md O02.
"""
from engine.mechanics.urbanismo import GerenciadorUrbanismo

from tests.mundo_sintetico import adulto, casa, mundo_de


def _config_urbanismo(**overrides):
    base = {
        "habitantes_por_estabelecimento": {"taverna": 2},
        "custo_estabelecimento_pc": 100,
        "nome_padrao_por_categoria": {"taverna": "Taverna"},
        "capacidade_padrao_estabelecimento": 15,
        "salario_padrao_estabelecimento": 95,
    }
    base.update(overrides)
    return {"urbanismo": base}


def test_abre_estabelecimento_quando_ha_deficit_e_dinheiro():
    rico = adulto("npc_1", "Rico", dinheiro_total_pc=500.0, cidade_id=1, casa_id="casa_1")
    pobre = adulto("npc_2", "Pobre", dinheiro_total_pc=10.0, cidade_id=1, casa_id="casa_1")
    mundo = mundo_de(npcs=[rico, pobre], locais=[casa()])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1, x=1.0, y=1.0, bairro="Centro")

    GerenciadorUrbanismo(mundo, _config_urbanismo()).processar_urbanismo()

    novos = [l for l in mundo.locais.values() if l.categoria == "taverna"]
    assert len(novos) == 1
    assert novos[0].id == "lote_1"
    assert novos[0].dono_npc_id == "npc_1"  # o mais rico, não o pobre
    assert novos[0].status == 0  # nasce como obra
    assert rico.dinheiro_total_pc == 400.0  # 500 - custo (100)
    assert mundo.db.lotes.buscar_por_id("lote_1").estado == "obra"


def test_nao_abre_sem_ninguem_com_dinheiro_suficiente():
    pobre1 = adulto("npc_1", "Pobre1", dinheiro_total_pc=10.0, cidade_id=1)
    pobre2 = adulto("npc_2", "Pobre2", dinheiro_total_pc=20.0, cidade_id=1)
    mundo = mundo_de(npcs=[pobre1, pobre2], locais=[casa()])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1)

    GerenciadorUrbanismo(mundo, _config_urbanismo()).processar_urbanismo()

    assert [l for l in mundo.locais.values() if l.categoria == "taverna"] == []
    assert mundo.db.lotes.buscar_por_id("lote_1").estado == "livre"


def test_nao_abre_sem_deficit():
    """Sem NPC nenhum na cidade, não há demanda — nada é construído."""
    mundo = mundo_de(npcs=[], locais=[casa()])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1)

    GerenciadorUrbanismo(mundo, _config_urbanismo()).processar_urbanismo()

    assert mundo.db.lotes.buscar_por_id("lote_1").estado == "livre"


def test_no_maximo_um_estabelecimento_por_cidade_por_chamada():
    rico = adulto("npc_1", "Rico", dinheiro_total_pc=5000.0, cidade_id=1)
    mundo = mundo_de(npcs=[rico], locais=[casa()])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1)
    mundo.db.lotes.adicionar("lote_2", cidade_id=1)

    cfg = _config_urbanismo(habitantes_por_estabelecimento={"taverna": 1})
    GerenciadorUrbanismo(mundo, cfg).processar_urbanismo()

    novos = [l for l in mundo.locais.values() if l.categoria == "taverna"]
    assert len(novos) == 1
