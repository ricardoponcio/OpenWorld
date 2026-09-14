"""
Testes de `IndiceDeLocais` — docs/12_PLANO_CIDADE_VIVA.md P01/P02.
"""
from engine.indice_locais import IndiceDeLocais
from engine.models import Local, TipoLocal, CategoriaLocal

from tests.mundo_sintetico import casa, mundo_de


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


def test_registrar_local_e_desativar_local_via_estado_do_mundo():
    """P02 — o único caminho de escrita de Local: registrar_local cria/reindexa,
    desativar_local persiste e tira dos índices de "disponível agora"."""
    mundo = mundo_de()
    social = casa("social_1", nome="Taverna Nova", tipo=TipoLocal.SOCIAL.value, cidade_id=1)

    mundo.registrar_local(social)
    assert social.id in mundo.locais
    assert mundo.indice.sociais(1) == ["social_1"]
    assert social in mundo.db.locais.salvos

    social.status = 0
    mundo.desativar_local(social.id)
    assert mundo.indice.sociais(1) == []
    assert social.id in mundo.locais  # continua acessível por id, só sai do índice


def test_registrar_local_reindexa_obra_concluida():
    """P02: quando uma obra conclui (status 0 -> 1), registrar_local de novo tem que
    tirar o local de obra_por_dono (senão o dono parece ter obra em andamento pra
    sempre) e passar a indexar como residência ativa."""
    mundo = mundo_de()
    obra = casa("obra_1", nome="Obra", tipo=TipoLocal.CASA.value, status=0,
                categoria=CategoriaLocal.RESIDENCIA.value, dono_npc_id="npc_1", cidade_id=1)
    mundo.registrar_local(obra)
    assert mundo.indice.obra_por_dono["npc_1"] == "obra_1"
    assert mundo.indice.residencias_ativas(1) == []

    obra.status = 1
    mundo.registrar_local(obra)

    assert "npc_1" not in mundo.indice.obra_por_dono
    assert mundo.indice.residencias_ativas(1) == ["obra_1"]
