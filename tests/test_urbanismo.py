"""
Testes de `GerenciadorUrbanismo` — docs/12_PLANO_CIDADE_VIVA.md O02.
"""
from engine.mechanics.urbanismo import GerenciadorUrbanismo, tipo_local_de_categoria
from engine.models import TipoLocal, CategoriaLocal
from config import get_config

from tests.mundo_sintetico import adulto, casa, mundo_de


def test_todo_local_tem_tipo_do_enum():
    """V01 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco V): `tipo_local_por_categoria` cobre
    TODAS as `CategoriaLocal`, e cada valor está em `TipoLocal` — sem isto, `tipo`
    virava cópia exata de `tipo_local` em 26.748 de 26.748 locais medidos."""
    config = get_config()
    tipos_validos = {t.value for t in TipoLocal}
    for cat in CategoriaLocal:
        tipo = tipo_local_de_categoria(cat.value, config)
        assert tipo in tipos_validos, f"{cat.value} -> {tipo!r} não está em TipoLocal"


def _config_urbanismo(**overrides):
    base = {
        "habitantes_por_estabelecimento": {"taverna": 2},
        "custo_estabelecimento_pc": 100,
        "nome_padrao_por_categoria": {"taverna": "Taverna"},
        "capacidade_padrao_estabelecimento": 15,
        "salario_padrao_estabelecimento": 95,
        # X01: limiares de saturação — 0 nos testes de O02 (que não semeiam nenhuma
        # cidade em `mundo.cidades`) pra `avaliar_expansao` nunca satisfazer a condição
        # (livres < 0 é sempre falso) e cair fora antes de tocar `_aplicar_arrabalde`.
        "lotes_livres_minimo": 0,
        "fracao_livre_minima": 0.0,
        "arrabalde_comprimento_m": 180,
        "arrabalde_comprimento_max_m": 520,
    }
    base.update(overrides)
    return {
        "urbanismo": base,
        # V01 (docs/15_PLANO_MUNDO_CRIVEL.md): `abrir_obra` deriva `tipo` daqui.
        "geracao_urbana": {"tipo_local_por_categoria": {
            "residencia": "Casa", "forja": "Oficina", "mercado": "Loja",
            "taverna": "Social", "publico": "Social", "quartel": "Defesa",
            "universidade": "Magia", "fazenda": "Campo", "generic": "Outro",
        }},
    }


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
