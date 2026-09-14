"""
A03 (docs/13_PLANO_POPULACAO_E_ESCALA.md): `EstadoDoMundo.acordar`/`acordar_cidade` — a
única porta pra "algo de fora da decisão do próprio NPC mudou o que ele quer, reavalie
agora", furando qualquer salto grande que a agenda (A02) tivesse calculado. E a rede de
segurança: mesmo sem NENHUM `acordar`, um NPC esquecido volta a decidir dentro do teto
de segurança, nunca fica congelado pra sempre.
"""
from datetime import datetime, timedelta

from engine.config_loader import carregar_config_global, cfg_get
from engine.mechanics.decay import InfrastructureManager
from engine.mechanics.events import GlobalEventManager
from engine.mechanics.marriage import NPCMarriageManager
from engine.models import Acao, EstadoCivil, Genero, TipoLocal
from tests.mundo_sintetico import BancoFalso, adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def test_acordar_poe_proximo_instante_em_agora():
    npc = adulto("npc_1", "Dorminhoco")
    npc.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)  # bem no futuro
    mundo = mundo_de(npcs=[npc])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)

    mundo.acordar(npc)

    assert npc.proximo_instante_decisao == mundo.data_simulada


def test_acordar_cidade_so_acorda_vivos_da_propria_cidade():
    from engine.models import Cidade
    c1 = Cidade(id=1, continente_uuid="c", nome="Vila 1", tamanho="pequeno", tipo="residencial", x_global=0, y_global=0)
    c2 = Cidade(id=2, continente_uuid="c", nome="Vila 2", tamanho="pequeno", tipo="residencial", x_global=0, y_global=0)
    n1 = adulto("npc_1", "Da Vila 1", cidade_id=1)
    n2 = adulto("npc_2", "Da Vila 2", cidade_id=2)
    morto = adulto("npc_3", "Morto da Vila 1", cidade_id=1, saude=0, estagio_vida="morto")
    for n in (n1, n2, morto):
        n.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    mundo = mundo_de(npcs=[n1, n2, morto], cidades=[c1, c2])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)

    mundo.acordar_cidade(1)

    assert n1.proximo_instante_decisao == mundo.data_simulada
    assert n2.proximo_instante_decisao == datetime(2026, 1, 2, 0, 0)  # cidade errada
    assert morto.proximo_instante_decisao == datetime(2026, 1, 2, 0, 0)  # morto, não acorda


def test_fechamento_de_local_acorda_os_trabalhadores(monkeypatch):
    config = _config()
    forja = casa("loc_forja", nome="Forja", tipo=TipoLocal.LOJA.value, integridade=20)
    ferreiro = adulto("npc_1", "Ferreiro", local_trabalho_id="loc_forja")
    ferreiro.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    mundo = mundo_de(npcs=[ferreiro], locais=[forja])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)

    # Desgaste sozinho (0,2/dia) não derruba de 20 pra <=10 (ruína); fica em "crítico"
    # (10 < integridade <= 25) e dispara _fechar_local, não _colapsar_para_ruina.
    InfrastructureManager(mundo, config).processar_desgaste()

    assert ferreiro.local_trabalho_id is None
    assert ferreiro.proximo_instante_decisao == mundo.data_simulada


def test_colapso_para_ruina_acorda_os_trabalhadores():
    config = _config()
    casa_caindo = casa("loc_1", nome="Casa", tipo=TipoLocal.LOJA.value, integridade=1)
    trabalhador = adulto("npc_1", "Trabalhador", local_trabalho_id="loc_1")
    trabalhador.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    mundo = mundo_de(npcs=[trabalhador], locais=[casa_caindo])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)
    mundo.db.lotes.definir_estado("loc_1", "ocupado")

    InfrastructureManager(mundo, config).processar_desgaste()

    assert trabalhador.local_trabalho_id is None
    assert trabalhador.proximo_instante_decisao == mundo.data_simulada


def test_casamento_acorda_os_dois_conjuges():
    config = _config()
    n1 = adulto("npc_1", "Noivo", genero=Genero.MASCULINO.value, casa_id="casa_1")
    n2 = adulto("npc_2", "Noiva", genero=Genero.FEMININO.value, casa_id="casa_1")
    n1.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    n2.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    mundo = mundo_de(npcs=[n1, n2], locais=[casa(capacidade=5)])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)

    NPCMarriageManager(mundo, config).realizar_casamento(n1, n2, "casa_1")

    assert n1.proximo_instante_decisao == mundo.data_simulada
    assert n2.proximo_instante_decisao == mundo.data_simulada


def test_evento_global_novo_acorda_todo_mundo_mas_so_uma_vez():
    n1 = adulto("npc_1", "Cidadao")
    n1.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    mundo = mundo_de(npcs=[n1])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)
    mundo.db.eventos.carregar_globais_ativos = lambda: [
        {"id": "ev_1", "ticks_restantes": 10}]
    mundo.db.eventos.atualizar_ticks_restantes = lambda eventos: None

    gerenciador = GlobalEventManager(mundo)
    gerenciador.atualizar_eventos_globais()
    assert n1.proximo_instante_decisao == mundo.data_simulada

    # Simula o próximo tick: o NPC já foi processado e agendado de novo, longe.
    n1.proximo_instante_decisao = datetime(2026, 1, 2, 0, 0)
    gerenciador.atualizar_eventos_globais()  # MESMO evento, já conhecido
    assert n1.proximo_instante_decisao == datetime(2026, 1, 2, 0, 0)  # não reacordou


def test_rede_de_seguranca_sem_nenhum_acordar_o_npc_volta_a_decidir():
    """Resistência (A03): mesmo removendo de propósito qualquer `acordar`, o NPC
    tem que voltar a decidir dentro do teto de segurança configurado — nunca fica
    congelado pra sempre."""
    from engine.loop import GameLoop
    config = _config()
    teto = cfg_get(config, "simulacao_intervalo_maximo_decisao_min")

    npc = adulto("npc_1", "Isolado", acao_atual=Acao.OCIOSO, energia=100.0, fome=0.0)
    mundo = mundo_de(npcs=[npc], locais=[casa()])
    mundo.data_simulada = datetime(2026, 1, 1, 10, 0)
    loop = GameLoop(mundo, config)

    loop.executar_tick()
    agendado_para = mundo.npcs[0].proximo_instante_decisao
    assert agendado_para <= mundo.data_simulada + timedelta(minutes=teto)

    ticks_ate_reavaliar = int((agendado_para - mundo.data_simulada).total_seconds() // 60)
    for _ in range(ticks_ate_reavaliar):
        loop.executar_tick()

    assert loop.decisoes_avaliadas_no_ultimo_tick >= 1
