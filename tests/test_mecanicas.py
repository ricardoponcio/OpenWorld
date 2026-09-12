"""
Testes de injeção dos gerenciadores de mecânica — docs/PLANO_REFATORACAO.md, R-F01
e docs/ARQUITETURA.md, Seção 7 ("Classes: estático, instância ou função") e Seção 13
("O teste que a injeção de dependência habilita").

Cada gerenciador de `engine/mechanics/` recebe um `EstadoDoMundo` e a config, nunca a
`SimulationEngine`. O invariante que estes testes protegem é justamente esse: se algum
gerenciador voltar a depender da engine (ou abrir um banco por conta própria), nenhum
destes testes consegue ser construído. O banco é um dublê em memória que só registra o
que foi salvo — não há arquivo, schema, nem pool de conexões em lugar nenhum. Os dublês
e as fábricas de mundo moram em tests/mundo_sintetico.py.
"""
import pytest

from engine.config_loader import carregar_config_global, cfg_get
from engine.models import (
    Cidade, Acao, EstagioVida, Genero, EstadoCivil, HumorNPC,
    TipoLocal, VinculoSocial,
)
from engine.mechanics.kingdom import KingdomManager
from engine.mechanics.mood import NPCMoodManager
from engine.mechanics.decay import InfrastructureManager
from engine.mechanics.housing import NPCHousingManager
from engine.mechanics.marriage import NPCMarriageManager
from engine.mechanics.social import NPCSocialManager
from engine.mechanics.lifecycle import NPCLifecycleManager
from engine.mechanics.finance import NPCLegacyManager
from engine.mechanics.reproduction import NPCReproductionManager
from engine.mechanics.actions import NPCActionManager
from engine.mechanics.movement import NPCMovementManager

from tests.mundo_sintetico import MovimentoDuble, adulto, casa, mundo_de


@pytest.fixture(scope="module")
def config():
    return carregar_config_global()


# ----------------------------------------------------------------------
# KingdomManager
# ----------------------------------------------------------------------

def test_pensao_do_reino_vai_so_para_idosos(config):
    jovem = adulto("npc_1", "Bran Jovem", dinheiro_total_pc=0.0)
    velho = adulto("npc_2", "Olda Anciã", dinheiro_total_pc=0.0,
                   estagio_vida=EstagioVida.IDOSO.value)
    mundo = mundo_de(npcs=[jovem, velho])

    KingdomManager(mundo, config).processar_pagamentos_reino()

    assert jovem.dinheiro_total_pc == 0.0
    assert velho.dinheiro_total_pc > 0.0


def test_sopao_nao_atende_adulto_com_dinheiro(config):
    rico = adulto("npc_1", "Rico Fartura", dinheiro_total_pc=500.0, fome=95.0)
    mundo = mundo_de(npcs=[rico])

    atendido = KingdomManager(mundo, config).fornecer_sopao(rico, 10.0, 5.0)

    assert atendido is False
    assert rico.fome == 95.0


# ----------------------------------------------------------------------
# NPCMoodManager — único gerenciador que não precisa do mundo
# ----------------------------------------------------------------------

def test_humor_caminha_um_passo_por_vez_na_escala(config, monkeypatch):
    # Necessidades no chão: o alvo é o pior humor da escala, mas a transição é gradual.
    sofrido = adulto("npc_1", "Tris Tebaixo", energia=0.0, fome=100.0, social=0.0,
                     humor=HumorNPC.NEUTRO.value)
    monkeypatch.setattr("engine.mechanics.mood.random.random", lambda: 0.0)

    NPCMoodManager(config).processar_humor(sofrido)

    escala = [h.value for h in HumorNPC.escala_normal()]
    assert sofrido.humor != HumorNPC.NEUTRO.value
    assert abs(escala.index(sofrido.humor) - escala.index(HumorNPC.NEUTRO.value)) == 1


# ----------------------------------------------------------------------
# InfrastructureManager
# ----------------------------------------------------------------------

def test_desgaste_reduz_integridade_e_persiste(config):
    forja = casa("loc_forja", nome="Forja", tipo=TipoLocal.LOJA.value, integridade=80)
    mundo = mundo_de(locais=[forja])

    InfrastructureManager(mundo, config).processar_desgaste()

    assert forja.integridade < 80
    assert forja in mundo.db.locais.salvos


def test_ruina_e_obra_nao_decaem(config):
    ruina = casa("loc_ruina", nome="Ruínas", tipo=TipoLocal.RUINA.value, integridade=0)
    obra = casa("loc_obra", nome="Obra", integridade=40, status=0)
    mundo = mundo_de(locais=[ruina, obra])

    InfrastructureManager(mundo, config).processar_desgaste()

    assert obra.integridade == 40
    assert mundo.db.locais.salvos == []


# ----------------------------------------------------------------------
# NPCHousingManager — o exemplo do próprio plano (R-F01)
# ----------------------------------------------------------------------

def test_obra_nao_duplica_para_casal_que_ja_constroi(config):
    marido = adulto("npc_1", "Ulf Pedreiro", conjuge_id="npc_2",
                    estado_civil=EstadoCivil.CASADO.value)
    esposa = adulto("npc_2", "Ama Pedreiro", conjuge_id="npc_1",
                    estado_civil=EstadoCivil.CASADO.value, genero=Genero.FEMININO.value)
    obra_em_curso = casa("casa_obra_1", nome="Obra de Pedreiro", status=0,
                         integridade=0, dono_npc_id="npc_1")
    mundo = mundo_de(npcs=[marido, esposa], locais=[casa(), obra_em_curso],
                     cidades=[Cidade(1, "uuid", "Vila", "pequena", "vila", 100, 100)])

    iniciou = NPCHousingManager(mundo, config).iniciar_obra_para_casal(marido, esposa)

    assert iniciou is False
    assert len([l for l in mundo.locais.values() if l.status == 0]) == 1


def test_obra_nasce_na_coordenada_da_cidade_do_npc(config):
    solteiro = adulto("npc_1", "Kai Solitário")
    cidade = Cidade(1, "uuid", "Vila", "pequena", "vila", 2048, 1024)
    mundo = mundo_de(npcs=[solteiro], locais=[casa()], cidades=[cidade])

    assert NPCHousingManager(mundo, config).iniciar_obra_para_casal(solteiro) is True

    obras = [l for l in mundo.locais.values() if l.status == 0]
    assert len(obras) == 1
    assert obras[0].dono_npc_id == "npc_1"
    assert obras[0] in mundo.db.locais.salvos


# ----------------------------------------------------------------------
# NPCMarriageManager
# ----------------------------------------------------------------------

def test_irmaos_nunca_sao_elegiveis_ao_casamento(config):
    irmao = adulto("npc_1", "Edd Irmão", mae_id="npc_mae", casa_id="casa_1")
    irma = adulto("npc_2", "Eda Irmã", mae_id="npc_mae", casa_id="casa_2",
                  genero=Genero.FEMININO.value)
    mundo = mundo_de(npcs=[irmao, irma], locais=[casa(), casa("casa_2")])

    elegivel = NPCMarriageManager(mundo, config).verificar_elegibilidade_casamento(
        irmao, irma, afinidade=1000)

    assert elegivel is False


def test_casamento_usa_a_habitacao_injetada_quando_a_casa_esta_cheia(config):
    class HabitacaoDuble:
        def __init__(self):
            self.pedidos = []

        def iniciar_obra_para_casal(self, n1, n2=None):
            self.pedidos.append((n1.id, n2.id if n2 else None))
            return True

    noivo = adulto("npc_1", "Rolf Noivo", casa_id="casa_1")
    noiva = adulto("npc_2", "Ilse Noiva", casa_id="casa_2", genero=Genero.FEMININO.value)
    sogro = adulto("npc_3", "Hal Sogro", casa_id="casa_1")
    lotada = casa("casa_1", capacidade=1)
    mundo = mundo_de(npcs=[noivo, noiva, sogro], locais=[lotada, casa("casa_2", capacidade=1)])

    duble = HabitacaoDuble()
    NPCMarriageManager(mundo, config, habitacao=duble).realizar_casamento(
        noivo, noiva, "casa_1")

    assert duble.pedidos == [("npc_1", "npc_2")]
    assert noivo.conjuge_id == "npc_2" and noiva.conjuge_id == "npc_1"
    assert noivo.estado_civil == EstadoCivil.CASADO.value


# ----------------------------------------------------------------------
# NPCSocialManager
# ----------------------------------------------------------------------

class CasamentoDuble:
    """Deixa a interação social medir só a afinidade, sem romance surpresa no meio."""

    def verificar_elegibilidade_casamento(self, n1, n2, afinidade):
        return False

    def processar_coabitacao(self):
        pass


def test_interacao_social_grava_afinidade_mutua_e_vinculo(config):
    a = adulto("npc_1", "Vik Falante", localizacao_atual_id="loc_praca")
    b = adulto("npc_2", "Mira Ouvinte", localizacao_atual_id="loc_praca",
               genero=Genero.FEMININO.value)
    praca = casa("loc_praca", nome="Praça", tipo=TipoLocal.SOCIAL.value)
    mundo = mundo_de(npcs=[a, b], locais=[praca])

    social = NPCSocialManager(mundo, config, casamento=CasamentoDuble())
    social.processar_interacao_social(a, b, "loc_praca")

    assert a.relacionamentos["npc_2"] == b.relacionamentos["npc_1"]
    assert len(mundo.db.npcs.relacionamentos) == 1
    assert mundo.db.npcs.relacionamentos[0][3] in [v.value for v in VinculoSocial]
    assert len(mundo.db.eventos.salvos) == 1


def test_vinculo_inimigo_e_alcancavel(config):
    """Protege a correção do R-B01: com a ordem antiga dos limiares, INIMIGO era
    inalcançável porque RIVAL (-20) era testado antes de INIMIGO (-50)."""
    assert NPCSocialManager._classificar_vinculo(
        -1000, cfg_get(config, "biologia_e_sociedade")) == VinculoSocial.INIMIGO


# ----------------------------------------------------------------------
# NPCLifecycleManager e NPCLegacyManager
# ----------------------------------------------------------------------

def test_morte_desvincula_o_npc_e_delega_a_heranca(config):
    class HerancaDuble:
        def __init__(self):
            self.chamadas = []

        def processar_heranca(self, npc, timestamp_rpg):
            self.chamadas.append(npc.id)

    falecido = adulto("npc_1", "Gorm Finado", saude=0, local_trabalho_id="loc_forja",
                      estagio_vida=EstagioVida.IDOSO.value,
                      data_nascimento="2025-01-01T00:00:00")
    mundo = mundo_de(npcs=[falecido], locais=[casa()])

    duble = HerancaDuble()
    NPCLifecycleManager(mundo, config, heranca=duble).processar_morte(falecido)

    assert duble.chamadas == ["npc_1"]
    assert falecido.estagio_vida == EstagioVida.MORTO.value
    assert falecido.casa_id == "" and falecido.local_trabalho_id == ""
    assert falecido.acao_atual == Acao.OCIOSO


def test_heranca_divide_entre_os_filhos_vivos(config):
    pai = adulto("npc_1", "Bron Pai", dinheiro_total_pc=300.0)
    filho = adulto("npc_2", "Cal Filho", pai_id="npc_1", dinheiro_total_pc=0.0)
    filha = adulto("npc_3", "Dara Filha", pai_id="npc_1", dinheiro_total_pc=0.0,
                   genero=Genero.FEMININO.value)
    mundo = mundo_de(npcs=[pai, filho, filha], locais=[casa()])

    NPCLegacyManager(mundo, config).processar_heranca(pai, "Dia 1, 10:00")

    assert filho.dinheiro_total_pc == 150.0
    assert filha.dinheiro_total_pc == 150.0
    assert pai.dinheiro_total_pc == 0


# ----------------------------------------------------------------------
# NPCReproductionManager
# ----------------------------------------------------------------------

def test_concepcao_engravida_a_mulher_do_casal_afim(config, monkeypatch):
    monkeypatch.setattr("engine.mechanics.reproduction.random.random", lambda: 0.0)
    homem = adulto("npc_1", "Tor Marido", relacionamentos={"npc_2": 1000})
    mulher = adulto("npc_2", "Sif Esposa", genero=Genero.FEMININO.value,
                    relacionamentos={"npc_1": 1000})
    mundo = mundo_de(npcs=[homem, mulher], locais=[casa(capacidade=4)])

    NPCReproductionManager(mundo, config).processar_concepcao()

    assert mulher.gravidez_ticks > 0
    assert mulher in mundo.db.npcs.salvos


def test_concepcao_ignora_casa_com_um_unico_morador(config, monkeypatch):
    monkeypatch.setattr("engine.mechanics.reproduction.random.random", lambda: 0.0)
    sozinha = adulto("npc_1", "Eira Sozinha", genero=Genero.FEMININO.value)
    mundo = mundo_de(npcs=[sozinha], locais=[casa()])

    NPCReproductionManager(mundo, config).processar_concepcao()

    assert sozinha.gravidez_ticks == 0


# ----------------------------------------------------------------------
# NPCActionManager e NPCMovementManager
# ----------------------------------------------------------------------

def test_trabalhar_paga_salario_e_gasta_energia(config):
    ferreiro = adulto("npc_1", "Dorn Ferreiro", local_trabalho_id="loc_forja",
                      dinheiro_total_pc=0.0, energia=100.0, acao_atual=Acao.TRABALHAR)
    mundo = mundo_de(npcs=[ferreiro],
                     locais=[casa(), casa("loc_forja", tipo=TipoLocal.LOJA.value)])

    movimento = MovimentoDuble()
    NPCActionManager(mundo, config, movimento=movimento).executar_acao(ferreiro)

    assert ferreiro.dinheiro_total_pc > 0.0
    assert ferreiro.energia < 100.0
    assert movimento.destinos == ["trabalho"]


def test_sem_local_de_trabalho_o_npc_fica_ocioso(config):
    desempregado = adulto("npc_1", "Jorn Sem-Ofício", local_trabalho_id="",
                          acao_atual=Acao.TRABALHAR)
    mundo = mundo_de(npcs=[desempregado], locais=[casa()])

    movimento = MovimentoDuble()
    NPCActionManager(mundo, config, movimento=movimento).executar_acao(desempregado)

    assert desempregado.acao_atual == Acao.OCIOSO
    assert movimento.destinos == []


def test_dependente_nunca_sai_de_casa(config):
    crianca = adulto("npc_1", "Pip Criança", estagio_vida=EstagioVida.CRIANCA.value,
                     casa_id="casa_1", localizacao_atual_id="casa_1")
    taverna = casa("loc_taverna", nome="Taverna", tipo=TipoLocal.SOCIAL.value)
    mundo = mundo_de(npcs=[crianca], locais=[casa(), taverna])

    NPCMovementManager(mundo, config).mover_para(crianca, "loc_taverna")

    assert crianca.localizacao_atual_id == "casa_1"


def test_local_inativo_manda_o_npc_de_volta_para_casa(config):
    andarilho = adulto("npc_1", "Vex Andarilho", localizacao_atual_id="loc_taverna")
    fechada = casa("loc_taverna", nome="Taverna Fechada",
                   tipo=TipoLocal.SOCIAL.value, status=0)
    mundo = mundo_de(npcs=[andarilho], locais=[casa(), fechada])

    NPCMovementManager(mundo, config).mover_para(andarilho, "loc_taverna")

    assert andarilho.localizacao_atual_id == "casa_1"
