"""
W03 (docs/PLANO_POPULACAO_E_ESCALA.md): teste de ida e volta contra um SQLite de
verdade. N02 é a única tarefa do plano capaz de PERDER DADO — troca a escrita de fim de
tick por um `UPDATE` estreito, e um `UPDATE` numa linha que não existe não é erro, só
não faz nada. Escrito antes de N02, não depois: monta um mundo real, roda um tick que
faz uma NPC dar à luz, fecha e reabre o banco por um `DatabaseManager` novo (simulando
um reinício do processo), e confirma que o recém-nascido e os pais sobreviveram com os
campos corretos.
"""
import engine.mechanics.reproduction as reproduction_mod
from engine.config_loader import carregar_config_global
from engine.database import DatabaseManager
from engine.loop import GameLoop
from engine.models import Cidade, EstagioVida, Genero, Local, NPC
from engine.mundo import EstadoDoMundo


def _montar_mundo(db_path, config):
    db = DatabaseManager(db_path=db_path, pool_size=2)
    continente_uuid = "continente-teste"
    db.mundo.salvar_continente(continente_uuid, "Continente Teste", 1.0)
    cidade_id = db.mundo.salvar_cidade(continente_uuid, "Vila Teste", "pequeno", "residencial", 0, 0)

    casa = Local(id="casa_1", nome="Casa da Família", tipo="Casa", cidade_id=cidade_id,
                 categoria="residencia", capacidade=5)
    db.locais.salvar(casa)

    pai = NPC(id="npc_pai", nome="Pai Testador", profissao="Ferreiro", profissao_id="ferreiro",
              cidade_id=cidade_id, casa_id="casa_1", local_trabalho_id="", localizacao_atual_id="casa_1",
              genero=Genero.MASCULINO.value, estagio_vida=EstagioVida.ADULTO.value,
              data_nascimento="1990-01-01T00:00:00")
    mae = NPC(id="npc_mae", nome="Mãe Testadora", profissao="Ferreira", profissao_id="ferreiro",
              cidade_id=cidade_id, casa_id="casa_1", local_trabalho_id="", localizacao_atual_id="casa_1",
              genero=Genero.FEMININO.value, estagio_vida=EstagioVida.ADULTO.value,
              data_nascimento="1992-01-01T00:00:00", gravidez_ticks=1)
    db.npcs.salvar_completo([pai, mae])

    mundo = EstadoDoMundo(
        npcs=db.npcs.carregar_todos(),
        locais=db.locais.carregar_por_id(),
        cidades=db.mundo.carregar_cidades_por_id(),
        data_simulada=__import__("engine.tempo", fromlist=["RelogioMundo"]).RelogioMundo.HORA_INICIAL_PADRAO,
        db=db,
    )
    return mundo, cidade_id


def test_npc_nascido_durante_o_tick_sobrevive_a_reabertura_do_banco(tmp_path, monkeypatch):
    # O batizado por IA roda numa thread à parte e chama um serviço externo — fora do
    # escopo deste teste, que é sobre persistência, não sobre nomes gerados.
    monkeypatch.setattr(
        reproduction_mod.NPCReproductionManager, "_iniciar_batizado_assincrono",
        lambda self, dados: None)

    db_path = str(tmp_path / "teste.db")
    config = carregar_config_global()
    mundo, cidade_id = _montar_mundo(db_path, config)

    loop = GameLoop(mundo, config)
    loop.executar_tick()  # gravidez_ticks 1 -> 0: dispara o parto neste mesmo tick

    # N04 (docs/PLANO_POPULACAO_E_ESCALA.md): num_dependentes não é persistido (é
    # recalculado em memória, `_atualizar_dependentes`) — a mãe tem que ganhar o
    # dependente a mais no MESMO tick do parto, não só no próximo.
    mae_em_memoria = next(n for n in mundo.npcs if n.id == "npc_mae")
    assert mae_em_memoria.num_dependentes == 1

    # "Reinício do processo": um DatabaseManager novo, apontando pro mesmo arquivo.
    db_reaberto = DatabaseManager(db_path=db_path, pool_size=2)
    npcs_reabertos = {n.id: n for n in db_reaberto.npcs.carregar_todos()}

    assert "npc_pai" in npcs_reabertos and "npc_mae" in npcs_reabertos
    bebes = [n for n in npcs_reabertos.values() if n.id not in ("npc_pai", "npc_mae")]
    assert len(bebes) == 1, "o parto devia ter criado exatamente um NPC novo"

    bebe = bebes[0]
    assert bebe.estagio_vida == EstagioVida.BEBE.value
    assert bebe.mae_id == "npc_mae"
    assert bebe.pai_id == "npc_pai"
    assert bebe.casa_id == "casa_1"

    mae_reaberta = npcs_reabertos["npc_mae"]
    assert mae_reaberta.gravidez_ticks == 0
