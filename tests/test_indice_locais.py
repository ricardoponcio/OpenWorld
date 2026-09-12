"""
Testes de `IndiceDeLocais` — docs/PLANO_CIDADE_VIVA.md P01.
"""
from engine.indice_locais import IndiceDeLocais
from engine.models import Local, TipoLocal, CategoriaLocal

from tests.mundo_sintetico import casa


def test_indices_por_cidade_e_papel():
    taverna = casa("taverna_1", nome="Taverna do Porto", tipo=TipoLocal.SOCIAL.value,
                    categoria=CategoriaLocal.TAVERNA.value, cidade_id=1)
    loja = casa("loja_1", nome="Ferraria", tipo=TipoLocal.LOJA.value,
                categoria=CategoriaLocal.FORJA.value, cidade_id=1)
    praca = casa("praca_2", nome="Praça Pública", tipo=TipoLocal.SOCIAL.value,
                 categoria=CategoriaLocal.PUBLICO.value, cidade_id=2)
    residencia_inativa = casa("casa_x", nome="Casa Abandonada", tipo=TipoLocal.CASA.value,
                               categoria=CategoriaLocal.RESIDENCIA.value, cidade_id=1, status=0)

    indice = IndiceDeLocais({l.id: l for l in [taverna, loja, praca, residencia_inativa]})

    assert indice.sociais(1) == ["taverna_1"]
    assert indice.sociais(2) == ["praca_2"]
    assert indice.sociais_publicos(2) == ["praca_2"]
    assert indice.sociais_publicos(1) == []
    assert indice.comida(1) == ["taverna_1"]
    assert set(indice.passeio(1)) == {"taverna_1", "loja_1"}
    assert indice.residencias_ativas(1) == []  # a única residência da cidade 1 está inativa
    assert indice.trabalho_por_categoria(1, CategoriaLocal.FORJA.value) == ["loja_1"]
    assert indice.por_id["taverna_1"] is taverna


def test_registrar_e_remover_atualizam_os_indices():
    indice = IndiceDeLocais({})
    nova = casa("social_novo", nome="Arena Nova", tipo=TipoLocal.SOCIAL.value, cidade_id=5)

    indice.registrar("social_novo", nova)
    assert indice.sociais(5) == ["social_novo"]

    indice.remover("social_novo")
    assert indice.sociais(5) == []


def test_obra_por_dono():
    obra = casa("obra_1", nome="Obra do João", tipo=TipoLocal.CASA.value, status=0,
                dono_npc_id="npc_joao", cidade_id=1)
    indice = IndiceDeLocais({obra.id: obra})

    assert indice.obra_por_dono["npc_joao"] == "obra_1"
