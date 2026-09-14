"""
Testes de `NPCUtils` — docs/12_PLANO_CIDADE_VIVA.md P03.
"""
from engine.consultas_npc import NPCUtils
from engine.models import EstagioVida

from tests.mundo_sintetico import adulto, casa, mundo_de


def test_contar_dependentes_na_casa_agrupado_bate_com_a_versao_original():
    pai = adulto("pai", "Pai", casa_id="casa_1")
    filho = adulto("filho", "Filho", casa_id="casa_1", pai_id="pai",
                    estagio_vida=EstagioVida.CRIANCA.value)
    npcs = [pai, filho]

    original = NPCUtils.contar_dependentes_na_casa(npcs, pai)
    agrupado = NPCUtils.contar_dependentes_na_casa_agrupado(pai, NPCUtils.agrupar_por_casa(npcs))

    assert original == agrupado == 1


def test_obter_casas_vazias_so_da_cidade_pedida():
    """P03: consulta por cidade (via índice) — não devolve casa vazia de OUTRA cidade,
    e não devolve casa com morador vivo."""
    casa_vazia_cidade_1 = casa("casa_vazia_1", nome="Casa Vazia", cidade_id=1)
    casa_ocupada_cidade_1 = casa("casa_ocupada_1", nome="Casa Ocupada", cidade_id=1)
    casa_vazia_cidade_2 = casa("casa_vazia_2", nome="Casa Vazia Outra Cidade", cidade_id=2)
    morador = adulto("morador", "Morador", casa_id="casa_ocupada_1", cidade_id=1)

    mundo = mundo_de(npcs=[morador],
                     locais=[casa_vazia_cidade_1, casa_ocupada_cidade_1, casa_vazia_cidade_2])

    vazias = NPCUtils.obter_casas_vazias(mundo, cidade_id=1)

    assert [c.id for c in vazias] == ["casa_vazia_1"]
