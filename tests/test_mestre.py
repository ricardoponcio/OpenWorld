"""
Testes das ações de mundo do Modo Mestre — docs/10_PLANO_REFATORACAO.md (R-F03) e
docs/14_PLANO_AVANCO_E_CALIBRAGEM.md (Bloco F).

O que estes testes protegem:
- (a) um comando que não existe no enum é descartado em vez de cair num ramo errado;
- (b) todo comando registrado responde ao contrato;
- (c) o marcador NOVO_LOCAL continua ligando CRIAR_LOCAL a REATRIBUIR_NPC na mesma
  lista de ações;
- (d) F01: `MestreManager.aplicar_acoes` (processo do Flask) ENFILEIRA, nunca aplica
  na hora — só `drenar_e_aplicar` (processo da simulação, com o `EstadoDoMundo` vivo)
  aplica de verdade;
- (e) F03: toda ação que muda o que um NPC quer chama `mundo.acordar`;
- (f) F02: CRIAR_LOCAL nasce sem dono e já pronto, via `abrir_obra` de verdade.

Usa o mundo sintético compartilhado (tests/mundo_sintetico.py) — o mesmo `BancoFalso`
que os outros testes de mecânica usam, não mais dublês inventados só pra este arquivo.
"""
import pytest

from engine.config_loader import carregar_config_global
from engine.models import ComandoMestre, HumorNPC, MetaChave, TipoLocal
from engine.mechanics.mestre import MestreManager, ACOES, POR_COMANDO
from engine.mechanics.mestre.acoes import AcaoDeMundo, AcaoProposta
from engine.mechanics.mestre.acoes.reatribuir_npc import MARCADOR_NOVO_LOCAL
from engine.mechanics.urbanismo import GerenciadorUrbanismo

from tests.mundo_sintetico import adulto, casa, mundo_de


@pytest.fixture(scope="module")
def config():
    return carregar_config_global()


# ----------------------------------------------------------------------
# Contrato do registro
# ----------------------------------------------------------------------

def test_todo_comando_do_enum_tem_uma_acao_registrada():
    assert set(POR_COMANDO) == set(ComandoMestre)


def test_toda_acao_registrada_responde_a_interface():
    for acao in ACOES:
        assert isinstance(acao, AcaoDeMundo)
        assert isinstance(acao.comando, ComandoMestre)
        assert callable(acao.aplicar)


# ----------------------------------------------------------------------
# Validação do payload da IA
# ----------------------------------------------------------------------

def test_comando_inventado_pela_ia_e_descartado():
    assert AcaoProposta.de_payload({"comando": "INVOCAR_DRAGAO"}) is None
    assert AcaoProposta.de_payload({"comando": None}) is None


def test_payload_sem_bloco_dados_usa_a_propria_acao():
    proposta = AcaoProposta.de_payload({"comando": "DESTRUIR_LOCAL", "id": "loc_7"})
    assert proposta.comando == ComandoMestre.DESTRUIR_LOCAL
    assert proposta.alvo_id == "loc_7"


# ----------------------------------------------------------------------
# F01: aplicar_acoes ENFILEIRA, nunca aplica na hora
# ----------------------------------------------------------------------

def test_aplicar_acoes_enfileira_em_vez_de_aplicar_na_hora(config):
    """O processo do Flask não tem o EstadoDoMundo vivo — aplicar_acoes só pode
    enfileirar. Nenhum NPC/Local é tocado nesta chamada."""
    npc = adulto("npc_1", "Alguém", saude=50.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])

    resultados = MestreManager(mundo.db, config).aplicar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_1", "dados": {"saude": -10}},
    ])

    assert len(mundo.db.mestre.enfileiradas) == 1
    assert npc.saude == 50.0, "nada deveria ter sido aplicado ainda"
    assert len(resultados) == 1
    assert "enviad" in resultados[0].lower() or "📨" in resultados[0]


def test_acoes_desconhecidas_sao_filtradas_antes_de_enfileirar(config):
    mundo = mundo_de(npcs=[adulto("npc_1", "Alguém")], locais=[casa()])
    MestreManager(mundo.db, config).aplicar_acoes([
        {"comando": "FAZER_CHOVER_SAPOS"},
        {"comando": "AFETAR_NPC", "id": "npc_1", "dados": {"saude": -5}},
    ])
    assert len(mundo.db.mestre.enfileiradas) == 1
    assert mundo.db.mestre.enfileiradas[0]["comando"] == "AFETAR_NPC"


def test_aplicar_acoes_sem_nenhuma_reconhecida_nao_enfileira_nada(config):
    mundo = mundo_de(npcs=[], locais=[])
    resultados = MestreManager(mundo.db, config).aplicar_acoes([{"comando": "FAZER_CHOVER_SAPOS"}])
    assert mundo.db.mestre.enfileiradas == []
    assert len(resultados) == 1  # aviso de "nenhuma ação reconhecida"


# ----------------------------------------------------------------------
# F01/F03: drenar_e_aplicar — o lado da simulação, com o mundo vivo
# ----------------------------------------------------------------------

def test_drenar_e_aplicar_esta_vazio_sem_fila(config):
    mundo = mundo_de(npcs=[], locais=[])
    assert MestreManager(mundo.db, config).drenar_e_aplicar(mundo) == []


def test_afetar_npc_muda_saude_humor_e_acorda(config):
    from datetime import timedelta
    npc = adulto("npc_1", "Alguém", saude=50.0, humor=HumorNPC.NEUTRO.value)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    # Agenda um salto grande pro futuro pra provar que acordar() FURA esse salto —
    # sem isto, o NPC já estaria "em dia" por estar em npcs_sem_agenda (default).
    mundo.agendar_decisao(npc, mundo.data_simulada + timedelta(hours=5))

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_1", "dados": {"saude": -10, "humor": HumorNPC.PANICO.value}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert npc.saude == 40.0
    assert npc.humor == HumorNPC.PANICO.value
    assert npc.proximo_instante_decisao == mundo.data_simulada, "F03: precisa acordar"
    assert len(resultados) == 1
    assert npc in mundo.db.npcs.salvos


def test_afetar_npc_inexistente_nao_quebra_e_avisa(config):
    mundo = mundo_de(npcs=[], locais=[])
    mundo.db.mestre.enfileirar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_fantasma", "dados": {"saude": -10}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)
    assert len(resultados) == 1
    assert "não encontrado" in resultados[0]


def test_humor_invalido_da_ia_vira_neutro(config):
    npc = adulto("npc_1", "Alguém", saude=50.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    mundo.db.mestre.enfileirar_acoes([
        {"comando": "AFETAR_NPC", "id": "npc_1", "dados": {"saude": -10, "humor": "Eufórico"}},
    ])
    MestreManager(mundo.db, config).drenar_e_aplicar(mundo)
    assert npc.humor == HumorNPC.NEUTRO.value


def test_reatribuir_npc_muda_trabalho_e_casa_reindexando_e_acorda(config):
    npc = adulto("npc_1", "Alguém", casa_id="casa_1", localizacao_atual_id="casa_1")
    casa_nova = casa("casa_2")
    mundo = mundo_de(npcs=[npc], locais=[casa(), casa_nova, casa("loc_trabalho", tipo=TipoLocal.LOJA.value)])

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": "loc_trabalho", "casa_id": "casa_2"}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert npc.local_trabalho_id == "loc_trabalho"
    assert npc.casa_id == "casa_2"
    assert npc.id in {n.id for n in mundo.npcs_por_casa.get("casa_2", [])}
    assert npc.id not in {n.id for n in mundo.npcs_por_casa.get("casa_1", [])}
    assert npc.proximo_instante_decisao == mundo.data_simulada
    assert len(resultados) == 2


def test_reatribuicao_para_local_inexistente_e_ignorada(config):
    npc = adulto("npc_1", "Alguém", casa_id="casa_1")
    mundo = mundo_de(npcs=[npc], locais=[casa()])

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": "loc_fantasma"}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert npc.local_trabalho_id == ""
    assert resultados == []


def test_destruir_local_desativa_e_acorda_moradores_trabalhadores_e_presentes(config):
    """F03: quem morava, trabalhava OU só estava lá reavalia agora."""
    morador = adulto("npc_morador", "Morador", casa_id="loc_alvo", localizacao_atual_id="casa_2")
    trabalhador = adulto("npc_trab", "Trabalhador", local_trabalho_id="loc_alvo",
                          casa_id="casa_2", localizacao_atual_id="casa_2")
    visitante = adulto("npc_visita", "Visitante", localizacao_atual_id="loc_alvo",
                        casa_id="casa_2")
    alvo = casa("loc_alvo", status=1, integridade=100)
    mundo = mundo_de(npcs=[morador, trabalhador, visitante],
                      locais=[alvo, casa("casa_2")])

    mundo.db.mestre.enfileirar_acoes([{"comando": "DESTRUIR_LOCAL", "id": "loc_alvo"}])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert alvo.status == 0
    assert alvo.integridade == 0
    for npc in (morador, trabalhador, visitante):
        assert npc.proximo_instante_decisao == mundo.data_simulada, f"{npc.id} devia ter acordado"
    assert len(resultados) == 1


def test_destruir_local_inexistente_nao_quebra(config):
    mundo = mundo_de(npcs=[], locais=[])
    mundo.db.mestre.enfileirar_acoes([{"comando": "DESTRUIR_LOCAL", "id": "loc_fantasma"}])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)
    assert "não encontrado" in resultados[0]


# ----------------------------------------------------------------------
# F02: CRIAR_LOCAL chama abrir_obra de verdade — sem dono, já pronto
# ----------------------------------------------------------------------

def test_criar_local_reserva_lote_real_nasce_sem_dono_e_pronto(config):
    mundo = mundo_de(npcs=[], locais=[], cidades=[])
    mundo.db.meta.salvar(MetaChave.CIDADE_SIMULADA, "1")
    mundo.db.lotes.adicionar("lote_1", cidade_id=1, x=10.0, y=20.0)

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "CRIAR_LOCAL",
         "dados": {"nome": "Quartel do Norte", "tipo": "Trabalho", "categoria": "quartel"}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert "lote_1" in mundo.locais
    obra = mundo.locais["lote_1"]
    assert obra.nome == "Quartel do Norte"
    assert obra.dono_npc_id == "", "F02: edifício do Mestre não tem dono pessoal"
    assert obra.status == 1 and obra.integridade == 100, "F02: nasce pronto, não em obra"
    assert mundo.db.lotes.lotes["lote_1"].estado == "ocupado"
    assert len(resultados) == 1


def test_criar_local_sem_cidade_simulada_nao_cria_nada(config):
    mundo = mundo_de(npcs=[], locais=[])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1)

    mundo.db.mestre.enfileirar_acoes([{"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel"}}])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert mundo.locais == {}
    assert resultados == []


def test_criar_local_sem_lote_livre_dispara_avaliar_expansao(config, monkeypatch):
    """X01: cidade saturada — a mesma avaliação de auto-expansão que a simulação
    usa é chamada, com o mundo vivo (não mais um EstadoDoMundo de trabalho
    descartável — F01 apagou esse desvio)."""
    chamadas = []
    monkeypatch.setattr(GerenciadorUrbanismo, "avaliar_expansao",
                         lambda self, cidade_id: chamadas.append(cidade_id))

    mundo = mundo_de(npcs=[], locais=[])
    mundo.db.meta.salvar(MetaChave.CIDADE_SIMULADA, "1")
    # Nenhum lote livre semeado — reservar_livre devolve None de cara.

    mundo.db.mestre.enfileirar_acoes([{"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel"}}])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert chamadas == [1]
    assert mundo.locais == {}
    assert len(resultados) == 1  # aviso de "sem lote mesmo após avaliar expansão"


def test_novo_local_liga_a_criacao_a_reatribuicao(config):
    npc = adulto("npc_1", "Alguém")
    mundo = mundo_de(npcs=[npc], locais=[])
    mundo.db.meta.salvar(MetaChave.CIDADE_SIMULADA, "1")
    mundo.db.lotes.adicionar("lote_1", cidade_id=1, x=10.0, y=20.0)

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "CRIAR_LOCAL", "dados": {"nome": "Quartel do Norte", "tipo": "Trabalho",
                                             "categoria": "quartel"}},
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": MARCADOR_NOVO_LOCAL}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert npc.local_trabalho_id == "lote_1"  # M02: o id do Local É o id do lote
    assert len(resultados) == 2


def test_marcador_sem_criacao_antes_nao_reatribui_nada(config):
    npc = adulto("npc_1", "Alguém")
    mundo = mundo_de(npcs=[npc], locais=[])

    mundo.db.mestre.enfileirar_acoes([
        {"comando": "REATRIBUIR_NPC", "id": "npc_1",
         "dados": {"local_trabalho_id": MARCADOR_NOVO_LOCAL}},
    ])
    resultados = MestreManager(mundo.db, config).drenar_e_aplicar(mundo)

    assert npc.local_trabalho_id == ""
    assert resultados == []
