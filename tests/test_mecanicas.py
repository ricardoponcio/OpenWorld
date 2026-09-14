"""
Testes de injeção dos gerenciadores de mecânica — docs/10_PLANO_REFATORACAO.md, R-F01
e docs/11_ARQUITETURA.md, Seção 7 ("Classes: estático, instância ou função") e Seção 13
("O teste que a injeção de dependência habilita").

Cada gerenciador de `engine/mechanics/` recebe um `EstadoDoMundo` e a config, nunca a
`SimulationEngine`. O invariante que estes testes protegem é justamente esse: se algum
gerenciador voltar a depender da engine (ou abrir um banco por conta própria), nenhum
destes testes consegue ser construído. O banco é um dublê em memória que só registra o
que foi salvo — não há arquivo, schema, nem pool de conexões em lugar nenhum. Os dublês
e as fábricas de mundo moram em tests/mundo_sintetico.py.
"""
import copy

import pytest

from engine.config_loader import carregar_config_global, cfg_get
from engine.models import (
    Cidade, NPC, Acao, EstagioVida, Genero, EstadoCivil, HumorNPC,
    TipoLocal, CategoriaLocal, VinculoSocial,
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


def test_humor_mesma_taxa_em_1_e_240_minutos(config):
    """X01 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 17): a agenda avalia um NPC
    ~20-30 vezes por dia em vez de 1.440 — `minutos` pode ser 1 ou 240. Antes desta
    correção, `min(minutos, distancia)` capava as tentativas de transição em
    ~4 (o tamanho da escala), então 240 chamadas de 1 minuto tinham MUITO mais
    chance de transição total que 1 chamada de 240 minutos de uma vez (P=1,000 vs
    P=0,352 medido no mundo real, §armadilha 17 do documento). As duas devem
    produzir, estatisticamente, a MESMA taxa de "saiu do humor inicial"."""
    amostras = 300

    def _rodar(passos_minutos):
        saiu_do_neutro = 0
        for i in range(amostras):
            npc = adulto(f"npc_{i}", "Sofrido", energia=0.0, fome=100.0, social=0.0,
                        humor=HumorNPC.NEUTRO.value)
            gerente = NPCMoodManager(config)
            for minutos in passos_minutos:
                gerente.processar_humor(npc, minutos=minutos)
            if npc.humor != HumorNPC.NEUTRO.value:
                saiu_do_neutro += 1
        return saiu_do_neutro / amostras

    taxa_1_min = _rodar([1] * 240)      # 240 chamadas de 1 minuto (regime antigo)
    taxa_240_min = _rodar([240])        # 1 chamada de 240 minutos (regime da agenda)

    assert abs(taxa_1_min - taxa_240_min) < 0.12


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


def test_colapso_para_ruina_libera_o_lote(config):
    """T04 (docs/12_PLANO_CIDADE_VIVA.md): quando um Local entra em colapso, o LOTE
    (mesmo id, armadilha 3) volta a 'livre' — pronto pra receber obra nova."""
    casa_caindo = casa("loc_1", nome="Casa", integridade=1)
    mundo = mundo_de(locais=[casa_caindo])
    mundo.db.lotes.definir_estado("loc_1", "ocupado")

    InfrastructureManager(mundo, config).processar_desgaste()

    assert casa_caindo.tipo == TipoLocal.RUINA.value
    assert mundo.db.lotes.estados["loc_1"] == "livre"


def test_liberar_lote_nao_atropela_reserva_nova(config):
    """T04: se o lote já não está mais 'ocupado' quando o colapso roda (alguém já
    reservou de novo, ou já foi liberado por outro caminho), `liberar` não atropela."""
    casa_caindo = casa("loc_1", nome="Casa", integridade=1)
    mundo = mundo_de(locais=[casa_caindo])
    mundo.db.lotes.definir_estado("loc_1", "obra")  # já reservado por outro casal

    InfrastructureManager(mundo, config).processar_desgaste()

    assert mundo.db.lotes.estados["loc_1"] == "obra"


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


def test_obra_reserva_um_lote_real(config):
    """O01 (docs/12_PLANO_CIDADE_VIVA.md): a obra nasce no lote livre mais próximo da
    casa atual do casal — não mais numa coordenada sorteada em terra firme. O id do
    Local É o id do lote (armadilha 3), e o lote passa a 'obra'."""
    solteiro = adulto("npc_1", "Kai Solitário")
    cidade = Cidade(1, "uuid", "Vila", "pequena", "vila", 2048, 1024)
    mundo = mundo_de(npcs=[solteiro], locais=[casa()], cidades=[cidade])
    mundo.db.lotes.adicionar("lote_1", cidade_id=1, x=10.0, y=20.0, bairro="Centro")

    assert NPCHousingManager(mundo, config).iniciar_obra_para_casal(solteiro) is True

    obras = [l for l in mundo.locais.values() if l.status == 0]
    assert len(obras) == 1
    assert obras[0].id == "lote_1"
    assert obras[0].dono_npc_id == "npc_1"
    assert obras[0].coordenadas == [10.0, 20.0]
    assert obras[0].bairro == "Centro"
    assert obras[0] in mundo.db.locais.salvos
    assert mundo.db.lotes.buscar_por_id("lote_1").estado == "obra"


def test_obra_sem_lote_livre_nao_constroi_e_nao_quebra(config):
    """O01: sem lote livre na cidade, `iniciar_obra_para_casal` devolve False (não
    levanta exceção — estado normal de cidade saturada, 11_ARQUITETURA.md P5)."""
    solteiro = adulto("npc_1", "Kai Solitário")
    mundo = mundo_de(npcs=[solteiro], locais=[casa()])

    assert NPCHousingManager(mundo, config).iniciar_obra_para_casal(solteiro) is False
    assert [l for l in mundo.locais.values() if l.status == 0] == []


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


def test_casamento_leva_os_filhos(config):
    """G04 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco G): sem isto, o casal se mudava e o
    dependente ficava sozinho na casa antiga, virando o próprio pagador da
    refeição com 0 PC (§5.2 do documento, 10 casos num mundo real de 25 dias)."""
    noivo = adulto("npc_1", "Rolf Noivo", casa_id="casa_1")
    noiva = adulto("npc_2", "Ilse Noiva", casa_id="casa_2", genero=Genero.FEMININO.value)
    bebe = NPC(id="npc_3", nome="Bebê de Ilse", profissao="dependente",
               local_trabalho_id="", localizacao_atual_id="casa_2", casa_id="casa_2",
               cidade_id=1, estagio_vida=EstagioVida.BEBE.value, mae_id="npc_2")
    mundo = mundo_de(npcs=[noivo, noiva, bebe],
                     locais=[casa("casa_1", capacidade=4), casa("casa_2", capacidade=4)])

    NPCMarriageManager(mundo, config).realizar_casamento(noivo, noiva, "casa_1")

    assert bebe.casa_id == "casa_1"
    assert bebe.localizacao_atual_id == "casa_1"


def test_coabitacao_so_roda_na_cadencia_diaria_nao_a_cada_tick(config, monkeypatch):
    """H02 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): `processar_coabitacao` deixou de ser
    chamada de dentro de `NPCSocialManager.processar_interacoes` (a cada tick) e
    passou a ser despachada por `GameLoop._rotinas_diarias`, uma vez por dia
    simulado, na hora de `casamento_hora`. Prova as duas metades: NENHUM casamento
    acontece fora dessa hora (mesmo rodando vários ticks com afinidade e chance
    máximas), e o casamento acontece exatamente quando o relógio cruza essa hora."""
    from datetime import datetime
    from engine.loop import GameLoop

    monkeypatch.setattr("engine.mechanics.marriage.random.random", lambda: 0.0)

    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    hora_casamento = cfg_get(cfg_bio, "casamento_hora")

    n1 = adulto("npc_1", "Pretendente", genero=Genero.MASCULINO.value, casa_id="casa_1")
    n2 = adulto("npc_2", "Pretendida", genero=Genero.FEMININO.value, casa_id="casa_2")
    afinidade = cfg_get(cfg_bio, "concepcao_afinidade_minima") + 10
    n1.relacionamentos[n2.id] = afinidade
    n2.relacionamentos[n1.id] = afinidade
    mundo = mundo_de(npcs=[n1, n2], locais=[casa("casa_1"), casa("casa_2")])
    # Começa DUAS horas antes da cadência de casamento, minuto 59 — o próximo tick
    # cruza pro minuto 0 de uma hora que ainda não é `casamento_hora`.
    mundo.data_simulada = datetime(2026, 1, 1, (hora_casamento - 2) % 24, 59)
    loop = GameLoop(mundo, config)

    loop.executar_tick()  # cruza pro minuto 0 da hora ANTERIOR a casamento_hora
    assert not any(n.conjuge_id for n in mundo.npcs), (
        "casamento não devia acontecer fora da hora configurada")

    for _ in range(60):  # avança até cruzar exatamente hora_casamento, minuto 0
        loop.executar_tick()
        if mundo.data_simulada.hour == hora_casamento and mundo.data_simulada.minute == 0:
            break

    casados = [n for n in mundo.npcs if n.conjuge_id]
    assert len(casados) == 2, "casamento devia acontecer na cadência diária configurada"


# ----------------------------------------------------------------------
# NPCSocialManager
# ----------------------------------------------------------------------

class CasamentoDuble:
    """Deixa a interação social medir só a afinidade, sem romance surpresa no meio.
    H02 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): `processar_coabitacao` não é mais
    chamada por `NPCSocialManager` (ganhou cadência diária própria), então este
    dublê não precisa mais simulá-la."""

    def verificar_elegibilidade_casamento(self, n1, n2, afinidade):
        return False


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
    # M02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco M): o relacionamento é SEMPRE gravado
    # (linhas acima), mas o EVENTO só quando o vínculo muda de FAIXA — afinidade
    # 0 -> pequena ainda é "Conhecido" nos dois lados, então nenhum evento nasce
    # aqui (era 99,1% "tiveram uma conversa" no log medido do mundo real).
    assert len(mundo.db.eventos.salvos) == 0


def test_vinculo_inimigo_e_alcancavel(config):
    """Protege a correção do R-B01: com a ordem antiga dos limiares, INIMIGO era
    inalcançável porque RIVAL (-20) era testado antes de INIMIGO (-50)."""
    assert NPCSocialManager._classificar_vinculo(
        -1000, cfg_get(config, "biologia_e_sociedade")) == VinculoSocial.INIMIGO


def test_romance_surpresa_para_casa_nova_nao_quebra_a_iteracao(config):
    """C01 (docs/16_PLANO_PAINEL_E_IA.md, Armadilha 20): `processar_interacoes` itera
    `mundo.npcs_por_localizacao` — um índice VIVO. Um romance surpresa que termine em
    `realizar_casamento` chama `mundo.mover_npc`, que faz `setdefault(casa_nova, [])`
    no mesmo dicionário: se `casa_nova` nunca teve morador, o dicionário cresce no
    meio do laço e o Python levanta `RuntimeError: dictionary changed size during
    iteration`. Reproduzido: 2 crashes em 240 ticks numa run real (Seção 2.4)."""
    cfg = copy.deepcopy(config)
    cfg_bio = cfg_get(cfg, "biologia_e_sociedade")
    cfg_bio["interacao_chance"] = 1.0
    cfg_bio["casamento_chance_romance_fisico"] = 1.0

    n1 = adulto("npc_1", "Pretendente", genero=Genero.MASCULINO.value,
                localizacao_atual_id="t1", casa_id="c1")
    n2 = adulto("npc_2", "Pretendida", genero=Genero.FEMININO.value,
                localizacao_atual_id="t1", casa_id="c2")
    # Afinidade inicial bem acima do limiar de concepção (usado pela elegibilidade
    # de casamento) — sobra folga mesmo depois do `mod` aleatório da interação.
    afinidade_alta = cfg_get(cfg_bio, "concepcao_afinidade_minima") + 500
    n1.relacionamentos[n2.id] = afinidade_alta
    n2.relacionamentos[n1.id] = afinidade_alta

    taverna = casa("t1", nome="Taverna", tipo=TipoLocal.SOCIAL.value)
    # Nenhum NPC tem `localizacao_atual_id == "c1"` — é isso que faz "c1" ser uma
    # chave NOVA em `npcs_por_localizacao` quando o casamento move alguém pra lá.
    mundo = mundo_de(npcs=[n1, n2], locais=[taverna, casa("c1"), casa("c2")])

    NPCSocialManager(mundo, cfg).processar_interacoes()  # não deve levantar RuntimeError

    assert n1.casa_id == n2.casa_id == "c1"


# ----------------------------------------------------------------------
# NPCSocialManager.processar_poda_de_relacionamentos (H05, docs/
# 14_PLANO_AVANCO_E_CALIBRAGEM.md)
# ----------------------------------------------------------------------

def test_poda_nunca_descarta_familia(config):
    """H05: cônjuge, pai/mãe e filho sobrevivem à poda e ao decaimento mesmo com
    afinidade baixa e mesmo estourando o teto — "uma pessoa esquece um conhecido de
    taverna, não a própria irmã"."""
    npc = adulto("npc_1", "Alguém", conjuge_id="npc_conjuge",
                 mae_id="npc_mae", pai_id="npc_pai")
    conjuge = adulto("npc_conjuge", "Cônjuge")
    mae = adulto("npc_mae", "Mãe")
    pai = adulto("npc_pai", "Pai")
    filho = adulto("npc_filho", "Filho", mae_id="npc_1")

    npc.relacionamentos = {
        "npc_conjuge": 1, "npc_mae": 1, "npc_pai": 1, "npc_filho": 1,
    }
    # Estoura bem o teto com desconhecidos fracos, pra forçar a poda a agir.
    teto = cfg_get(cfg_get(config, "simulacao"), "relacionamentos_max_por_npc")
    for i in range(teto + 20):
        npc.relacionamentos[f"npc_desconhecido_{i}"] = 1

    mundo = mundo_de(npcs=[npc, conjuge, mae, pai, filho], locais=[casa()])
    social = NPCSocialManager(mundo, config)

    for _ in range(5):  # vários dias de decaimento
        social.processar_poda_de_relacionamentos()

    for protegido in ("npc_conjuge", "npc_mae", "npc_pai", "npc_filho"):
        assert protegido in npc.relacionamentos, f"{protegido} não devia ter sido descartado"
    assert len(npc.relacionamentos) <= teto


def test_decaimento_anda_em_direcao_a_zero_e_remove_ao_chegar(config):
    """H05: afinidade fraca e não protegida decai até sumir — nunca cruza pro lado
    oposto (não vira negativa por decair demais numa passada)."""
    cfg_sim = cfg_get(config, "simulacao")
    decaimento = cfg_get(cfg_sim, "relacionamentos_decaimento_por_dia")

    npc = adulto("npc_1", "Alguém")
    npc.relacionamentos = {"npc_conhecido": decaimento * 3}
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    social = NPCSocialManager(mundo, config)

    for _ in range(2):
        social.processar_poda_de_relacionamentos()
        assert npc.relacionamentos["npc_conhecido"] >= 0

    for _ in range(5):
        social.processar_poda_de_relacionamentos()

    assert "npc_conhecido" not in npc.relacionamentos


def test_vinculo_forte_nao_decai_nem_e_podado(config):
    """H05: um amigo de verdade (afinidade >= vinculo_limiar_amigo) não decai e
    sobrevive à poda mesmo sem ser família."""
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    limiar_forte = cfg_get(cfg_bio, "vinculo_limiar_amigo")
    teto = cfg_get(cfg_get(config, "simulacao"), "relacionamentos_max_por_npc")

    npc = adulto("npc_1", "Alguém")
    npc.relacionamentos = {"npc_amigo": limiar_forte}
    for i in range(teto + 5):
        npc.relacionamentos[f"npc_desconhecido_{i}"] = 1
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    social = NPCSocialManager(mundo, config)

    social.processar_poda_de_relacionamentos()

    assert npc.relacionamentos["npc_amigo"] == limiar_forte


def test_teto_descarta_os_mais_fracos_primeiro(config):
    """H05: estourando o teto, quem tem menos afinidade acumulada é descartado
    antes de quem tem mais (entre os não protegidos)."""
    teto = cfg_get(cfg_get(config, "simulacao"), "relacionamentos_max_por_npc")
    npc = adulto("npc_1", "Alguém")
    npc.relacionamentos = {f"npc_{i}": i + 1 for i in range(teto + 10)}
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    social = NPCSocialManager(mundo, config)

    social.processar_poda_de_relacionamentos()

    assert len(npc.relacionamentos) <= teto
    assert "npc_0" not in npc.relacionamentos, "o mais fraco tinha que ter sido descartado primeiro"


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


def test_concepcao_recusa_parentes(config, monkeypatch):
    """G02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco G): mãe e filho adulto na mesma casa
    têm afinidade 100 automática (`parto_afinidade_inicial_pais`) — sem checar
    parentesco, isso engravidava em 6 de 200 noites testadas (§5.2 do documento;
    2 casos num mundo real de 25 dias). `processar_concepcao` agora usa
    `NPCUtils.pode_conceber`, que inclui `sao_parentes`."""
    monkeypatch.setattr("engine.mechanics.reproduction.random.random", lambda: 0.0)
    mae = adulto("npc_mae", "Mãe", genero=Genero.FEMININO.value,
                 relacionamentos={"npc_filho": 1000})
    filho = adulto("npc_filho", "Filho Adulto", mae_id="npc_mae",
                   relacionamentos={"npc_mae": 1000})
    mundo = mundo_de(npcs=[mae, filho], locais=[casa(capacidade=4)])

    NPCReproductionManager(mundo, config).processar_concepcao()

    assert mae.gravidez_ticks == 0


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


def test_socializar_cobra_uma_vez_por_visita(config):
    """N01 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco N): `custo_pc` era cobrado por
    MINUTO — 136,9 PC/dia, a maior despesa de TODA classe (71% da renda do
    trabalhador, 3,4x a pensão do idoso, §5.1 do documento). Agora só na chegada;
    ficar no mesmo local social não cobra de novo. Usa o `NPCMovementManager`
    REAL (não o dublê) — é `mover_para_social` ficando no mesmo lugar (N01) que
    faz `chegou_agora` virar `False` na segunda chamada."""
    frequentador = adulto("npc_1", "Bram Frequentador", dinheiro_total_pc=100.0,
                          acao_atual=Acao.SOCIALIZAR, num_dependentes=0)
    taverna = casa("loc_taverna", nome="Taverna", tipo=TipoLocal.SOCIAL.value,
                   categoria=CategoriaLocal.TAVERNA.value, capacidade=10)
    mundo = mundo_de(npcs=[frequentador], locais=[casa(), taverna])

    acoes = NPCActionManager(mundo, config)
    acoes.executar_acao(frequentador)
    assert frequentador.localizacao_atual_id == "loc_taverna"
    saldo_apos_chegada = frequentador.dinheiro_total_pc
    assert saldo_apos_chegada < 100.0  # cobrou na chegada

    acoes.executar_acao(frequentador)  # continua no mesmo local social
    assert frequentador.localizacao_atual_id == "loc_taverna"
    assert frequentador.dinheiro_total_pc == saldo_apos_chegada  # não cobrou de novo


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


def test_mover_para_social_nunca_atravessa_cidade(config):
    """P04 (docs/12_PLANO_CIDADE_VIVA.md): dois NPCs em cidades diferentes, cada uma com
    seu próprio local social — mover_para_social nunca coloca um NPC num local de
    cidade_id diferente do dele."""
    social_1 = casa("social_1", nome="Taverna 1", tipo=TipoLocal.SOCIAL.value, cidade_id=1)
    social_2 = casa("social_2", nome="Taverna 2", tipo=TipoLocal.SOCIAL.value, cidade_id=2)
    n1 = adulto("n1", "Da Cidade 1", cidade_id=1, casa_id="casa_1", num_dependentes=0)
    n2 = adulto("n2", "Da Cidade 2", cidade_id=2, casa_id="casa_1", num_dependentes=0)
    mundo = mundo_de(npcs=[n1, n2], locais=[casa(), social_1, social_2])

    movimento = NPCMovementManager(mundo, config)
    for _ in range(20):  # a escolha é aleatória — repete pra não passar por sorte
        movimento.mover_para_social(n1)
        movimento.mover_para_social(n2)
        assert n1.localizacao_atual_id in ("casa_1", "social_1")
        assert n2.localizacao_atual_id in ("casa_1", "social_2")


def test_fallback_de_mover_para_nao_muda_npc_de_cidade(config):
    """P04: a casa do NPC não existe mais (ou nunca existiu) — a rede de segurança só
    pode escolher uma casa da PRÓPRIA cidade dele, nunca de outra."""
    andarilho = adulto("npc_1", "Sem Casa", cidade_id=1, casa_id="casa_fantasma",
                        localizacao_atual_id="casa_fantasma")
    casa_outra_cidade = casa("casa_2", nome="Casa Cidade 2", cidade_id=2)
    mundo = mundo_de(npcs=[andarilho], locais=[casa_outra_cidade])

    NPCMovementManager(mundo, config).mover_para(andarilho, "casa_fantasma")

    # Nenhuma casa na cidade 1 — o NPC fica onde estava, não migra pra cidade 2.
    assert andarilho.localizacao_atual_id == "casa_fantasma"
