"""
A02 (docs/PLANO_POPULACAO_E_ESCALA.md): testes de `engine/mechanics/agenda.py` — o
cálculo puro de "quando este NPC precisa ser reavaliado de novo". Compara sempre contra
os limiares reais de `config.json` (carregado de verdade, não um dublê) porque a
propriedade que importa — nunca pular por cima de um limiar — depende dos valores
reais configurados, não de números inventados.
"""
from datetime import datetime, timedelta

from engine.config_loader import carregar_config_global, cfg_get
from engine.loop import GameLoop
from engine.mechanics import agenda
from engine.models import Acao, Cidade, EstagioVida, Genero

from tests.mundo_sintetico import adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def test_npc_nunca_avaliado_esta_sempre_em_dia():
    npc = adulto("npc_1", "Novo")
    assert agenda.npc_esta_em_dia(npc, datetime(2026, 1, 1, 10, 0), {"inaniacao_fome_limiar": 90})


def test_npc_em_inaniacao_esta_sempre_em_dia_mesmo_agendado_pro_futuro():
    npc = adulto("npc_1", "Faminto", fome=95.0)
    npc.proximo_instante_decisao = datetime(2026, 1, 1, 20, 0)  # bem no futuro
    agora = datetime(2026, 1, 1, 10, 0)
    assert agenda.npc_esta_em_dia(npc, agora, {"inaniacao_fome_limiar": 90})


def test_npc_agendado_pro_futuro_nao_esta_em_dia():
    npc = adulto("npc_1", "Dorminhoco", fome=10.0)
    npc.proximo_instante_decisao = datetime(2026, 1, 1, 20, 0)
    agora = datetime(2026, 1, 1, 10, 0)
    assert not agenda.npc_esta_em_dia(npc, agora, {"inaniacao_fome_limiar": 90})


def test_acao_nao_loteavel_agenda_so_um_minuto():
    config = _config()
    npc = adulto("npc_1", "Comendo", acao_atual=Acao.COMER)
    agora = datetime(2026, 1, 1, 10, 0)
    proximo = agenda.calcular_proximo_instante(npc, agora, config)
    assert proximo == agora + timedelta(minutes=1)


def test_dormir_agenda_um_salto_grande_quando_tudo_esta_bem():
    """Cenário central de A00b: uma noite de sono inteira, energia e fome longe de
    qualquer limiar — o salto tem que ser grande (perto do teto), não de 1 minuto."""
    config = _config()
    npc = adulto("npc_1", "Dorminhoco", acao_atual=Acao.DORMIR, energia=50.0, fome=10.0)
    agora = datetime(2026, 1, 1, 23, 0)  # dentro do sono obrigatório (22h-6h)
    proximo = agenda.calcular_proximo_instante(npc, agora, config)

    teto = cfg_get(config, "simulacao_intervalo_maximo_decisao_min")
    minutos_agendados = (proximo - agora).total_seconds() / 60
    assert minutos_agendados > 60, "um NPC dormindo tranquilo não devia ser reavaliado em menos de uma hora"
    assert minutos_agendados <= teto


def test_dormir_nao_ultrapassa_o_limiar_de_fome_dormindo():
    """O cruzamento tem que parar ANTES (ou exatamente n)o limiar, nunca depois —
    é a garantia central da armadilha 11."""
    config = _config()
    cfg_dec = cfg_get(config, "ia_decisao")
    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    gatilho = cfg_get(cfg_dec, "gatilho_fome_dormindo")

    npc = adulto("npc_1", "Quase com fome", acao_atual=Acao.DORMIR,
                 energia=50.0, fome=gatilho - 1.0)
    agora = datetime(2026, 1, 1, 23, 0)
    proximo = agenda.calcular_proximo_instante(npc, agora, config)
    minutos = (proximo - agora).total_seconds() / 60

    meta = cfg_get(config, "metabolismo")
    taxa_pior_caso = cfg_get(meta, "fome_base_ganho_max") * cfg_get(meta, "multiplicador_fome_dormindo")
    fome_projetada = npc.fome + taxa_pior_caso * minutos
    assert fome_projetada <= gatilho + 1e-9


def test_energia_desmaio_nao_e_ultrapassada_trabalhando():
    config = _config()
    cfg_dec = cfg_get(config, "ia_decisao")
    limiar = cfg_get(cfg_dec, "energia_limiar_desmaio")

    npc = adulto("npc_1", "Cansado", acao_atual=Acao.TRABALHAR,
                 energia=limiar + 1.0, fome=10.0)
    agora = datetime(2026, 1, 1, 10, 0)
    proximo = agenda.calcular_proximo_instante(npc, agora, config)
    minutos = (proximo - agora).total_seconds() / 60

    meta = cfg_get(config, "metabolismo")
    cfg_trabalhar = cfg_get(cfg_get(config, "acoes"), "trabalhar")
    taxa = cfg_get(meta, "energia_base_perda") + cfg_get(cfg_trabalhar, "energia_perda")
    energia_projetada = npc.energia - taxa * minutos
    assert energia_projetada >= limiar - 1e-9


def test_baldes_somam_a_populacao():
    """H01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): o invariante que sustenta o bloco
    inteiro — todo NPC vivo está em EXATAMENTE um lugar da agenda (balde de minuto,
    conjunto de consequência, ou "sem agenda ainda"). Roda parto (esposa grávida),
    morte (solteiro com saúde baixa) e o metabolismo normal por 100 ticks, e confere
    o invariante depois de CADA tick — não só no fim — porque uma violação
    transitória (um NPC duplicado por um tick só) é exatamente o tipo de bug que só
    aparece assim."""
    cidade = Cidade(id=1, continente_uuid="c", nome="Vila Teste", tamanho="pequeno",
                     tipo="residencial", x_global=0, y_global=0)
    casa_a = casa("casa_a", capacidade=5)
    casa_b = casa("casa_b", capacidade=5)

    marido = adulto("npc_marido", "Marido", genero=Genero.MASCULINO.value, casa_id="casa_a",
                     localizacao_atual_id="casa_a", cidade_id=1)
    esposa = adulto("npc_esposa", "Esposa", genero=Genero.FEMININO.value, casa_id="casa_a",
                     localizacao_atual_id="casa_a", cidade_id=1, gravidez_ticks=1)
    filho = adulto("npc_filho", "Filho", estagio_vida=EstagioVida.CRIANCA.value,
                   casa_id="casa_a", localizacao_atual_id="casa_a", cidade_id=1,
                   mae_id="npc_esposa")
    solteiro = adulto("npc_solteiro", "Solteiro", genero=Genero.MASCULINO.value,
                      casa_id="casa_b", localizacao_atual_id="casa_b", cidade_id=1,
                      saude=1)

    mundo = mundo_de(npcs=[marido, esposa, filho, solteiro], locais=[casa_a, casa_b], cidades=[cidade])
    loop = GameLoop(mundo, _config())

    for i in range(100):
        loop.executar_tick()
        vivos = sum(1 for n in mundo.npcs if n.esta_vivo())
        na_agenda = (sum(len(b) for b in mundo.baldes_decisao.values())
                     + len(mundo.npcs_em_consequencia)
                     + len(mundo.npcs_sem_agenda))
        assert na_agenda == vivos, f"tick {i + 1}: {na_agenda} na agenda contra {vivos} vivos"
