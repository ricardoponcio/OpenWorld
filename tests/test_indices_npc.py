"""
A04 (docs/PLANO_POPULACAO_E_ESCALA.md): `EstadoDoMundo.npcs_por_casa`/
`npcs_por_localizacao`/`npcs_por_cidade` — índices mantidos incrementalmente por
`mover_npc`/`mudar_casa`/`registrar_npc`/`remover_npc`, no lugar de recalculados do
zero a cada tick (P03/N04). O teste mais importante deste arquivo é o último
(`test_indices_batem_com_reconstrucao_do_zero`, W01): depois de várias rodadas de
tick com nascimento, morte, casamento e movimento, os índices mantidos têm que ficar
BYTE A BYTE iguais a uma reconstrução do zero — é o teste que pega o `mover_npc`/
`mudar_casa`/etc. esquecido que nenhum `grep` encontra (armadilha 12).
"""
from engine.config_loader import carregar_config_global
from engine.consultas_npc import NPCUtils
from engine.loop import GameLoop
from engine.models import Cidade, EstagioVida, Genero
from tests.mundo_sintetico import adulto, casa, mundo_de


def _config():
    return carregar_config_global()


def _reconstruir_do_zero(mundo):
    """A mesma verdade que `_reconstruir_indices_de_npc` calcula, mas via
    `NPCUtils`/varredura direta — usado só pra comparar, nunca no runtime."""
    por_casa = NPCUtils.agrupar_por_casa(mundo.npcs)
    por_localizacao = {}
    por_cidade = {}
    for npc in mundo.npcs:
        if not npc.esta_vivo():
            continue
        if npc.localizacao_atual_id:
            por_localizacao.setdefault(npc.localizacao_atual_id, []).append(npc)
        por_cidade.setdefault(npc.cidade_id, []).append(npc)
    return por_casa, por_localizacao, por_cidade


def _mesmos_ids_por_chave(indice_a: dict, indice_b: dict) -> bool:
    """Compara dois índices por CONJUNTO de ids em cada bucket — a ordem de inserção
    pode diferir sem que isso seja um bug (nenhum consumidor depende de ordem)."""
    chaves = set(indice_a) | set(indice_b)
    for chave in chaves:
        ids_a = {n.id for n in indice_a.get(chave, [])}
        ids_b = {n.id for n in indice_b.get(chave, [])}
        if ids_a != ids_b:
            return False
    return True


def test_mover_npc_atualiza_o_indice_por_localizacao():
    npc = adulto("npc_1", "Andarilho")
    outra_casa = casa("casa_2")
    mundo = mundo_de(npcs=[npc], locais=[casa(), outra_casa])

    mundo.mover_npc(npc, "casa_2")

    assert npc.localizacao_atual_id == "casa_2"
    assert npc.id in {n.id for n in mundo.npcs_por_localizacao.get("casa_2", [])}
    assert "casa_1" not in mundo.npcs_por_localizacao or npc.id not in {
        n.id for n in mundo.npcs_por_localizacao["casa_1"]}


def test_mudar_casa_atualiza_o_indice_por_casa():
    npc = adulto("npc_1", "Mudante", casa_id="casa_1")
    mundo = mundo_de(npcs=[npc], locais=[casa(), casa("casa_2")])

    mundo.mudar_casa(npc, "casa_2")

    assert npc.casa_id == "casa_2"
    assert npc.id in {n.id for n in mundo.npcs_por_casa.get("casa_2", [])}
    assert npc.id not in {n.id for n in mundo.npcs_por_casa.get("casa_1", [])}


def test_registrar_npc_entra_nos_tres_indices():
    mundo = mundo_de(npcs=[], locais=[casa()])
    bebe = adulto("npc_bebe", "Recém-nascido", casa_id="casa_1", localizacao_atual_id="casa_1", cidade_id=1)

    mundo.registrar_npc(bebe)

    assert bebe in mundo.npcs
    assert bebe.id in {n.id for n in mundo.npcs_por_casa.get("casa_1", [])}
    assert bebe.id in {n.id for n in mundo.npcs_por_localizacao.get("casa_1", [])}
    assert bebe.id in {n.id for n in mundo.npcs_por_cidade.get(1, [])}


def test_remover_npc_sai_dos_tres_indices():
    npc = adulto("npc_1", "Falecido", casa_id="casa_1", localizacao_atual_id="casa_1", cidade_id=1)
    mundo = mundo_de(npcs=[npc], locais=[casa()])

    mundo.remover_npc(npc)

    assert npc.id not in {n.id for n in mundo.npcs_por_casa.get("casa_1", [])}
    assert npc.id not in {n.id for n in mundo.npcs_por_localizacao.get("casa_1", [])}
    assert npc.id not in {n.id for n in mundo.npcs_por_cidade.get(1, [])}


def test_indices_batem_com_reconstrucao_do_zero():
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
                      saude=1)  # vai morrer logo (saude baixa + metabolismo)

    mundo = mundo_de(npcs=[marido, esposa, filho, solteiro], locais=[casa_a, casa_b], cidades=[cidade])
    config = _config()
    loop = GameLoop(mundo, config)

    for _ in range(100):
        loop.executar_tick()

    por_casa, por_localizacao, por_cidade = _reconstruir_do_zero(mundo)

    assert _mesmos_ids_por_chave(mundo.npcs_por_casa, por_casa), "npcs_por_casa divergiu da reconstrução"
    assert _mesmos_ids_por_chave(mundo.npcs_por_localizacao, por_localizacao), "npcs_por_localizacao divergiu"
    assert _mesmos_ids_por_chave(mundo.npcs_por_cidade, por_cidade), "npcs_por_cidade divergiu"
