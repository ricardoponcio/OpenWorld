"""
Testes de engine/identificadores.py — docs/16_PLANO_PAINEL_E_IA.md, Bloco C, C03.

Protege a Armadilha 25: o padrão antigo (`f"{prefixo}_{int(time.time())}_
{random.randint(0,999)}"`) tinha só 1.000 valores possíveis por segundo real, e
`RepositorioNPC.salvar` faz `INSERT OR REPLACE` — a colisão virava sobrescrita
silenciosa (3 de 495 bebês perdidos numa run real). `novo_id()` usa uuid4: os dois
testes abaixo congelam o relógio e o sorteio de `random.randint` (exatamente a
situação que colidia antes) e provam que a colisão deixou de acontecer.
"""
import random
import time

import engine.mechanics.reproduction as reproduction_mod
from engine.config_loader import carregar_config_global
from engine.database import DatabaseManager
from engine.identificadores import PrefixoId, novo_id
from engine.mechanics.reproduction import NPCReproductionManager
from engine.models import EstagioVida, Genero, Local, NPC
from engine.mundo import EstadoDoMundo
from engine.tempo import RelogioMundo


def test_ids_nao_colidem_com_relogio_e_sorteio_fixos(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1700000000.0)
    monkeypatch.setattr(random, "randint", lambda a, b: 42)

    ids = {novo_id(PrefixoId.NPC_NASCIDO) for _ in range(100_000)}

    assert len(ids) == 100_000


def test_dois_partos_no_mesmo_segundo_geram_bebes_distintos(tmp_path, monkeypatch):
    """C03: mesmo com `time.time()` e `random.randint()` congelados — o cenário
    exato que colidia com o gerador antigo — os dois bebês gravados no banco têm
    ids distintos. Banco de verdade em `tmp_path` (nunca `:memory:`, ARQUITETURA
    §13): é o `INSERT OR REPLACE` real que transformava a colisão em sobrescrita."""
    monkeypatch.setattr(time, "time", lambda: 1700000000.0)
    monkeypatch.setattr(random, "randint", lambda a, b: 42)
    monkeypatch.setattr(
        reproduction_mod.NPCReproductionManager, "_iniciar_batizado_assincrono",
        lambda self, dados: None)

    config = carregar_config_global()
    db = DatabaseManager(db_path=str(tmp_path / "teste.db"), pool_size=2)
    continente_uuid = "continente-teste"
    db.mundo.salvar_continente(continente_uuid, "Continente Teste", 1.0)
    cidade_id = db.mundo.salvar_cidade(
        continente_uuid, "Vila Teste", "pequeno", "residencial", 0, 0)

    db.locais.salvar(Local(id="casa_1", nome="Casa 1", tipo="Casa", cidade_id=cidade_id,
                            categoria="residencia", capacidade=5))
    db.locais.salvar(Local(id="casa_2", nome="Casa 2", tipo="Casa", cidade_id=cidade_id,
                            categoria="residencia", capacidade=5))

    mae1 = NPC(id="npc_mae1", nome="Mãe Um", profissao="Ferreira", profissao_id="ferreiro",
               cidade_id=cidade_id, casa_id="casa_1", local_trabalho_id="",
               localizacao_atual_id="casa_1", genero=Genero.FEMININO.value,
               estagio_vida=EstagioVida.ADULTO.value, data_nascimento="1992-01-01T00:00:00",
               gravidez_ticks=1)
    mae2 = NPC(id="npc_mae2", nome="Mãe Dois", profissao="Ferreira", profissao_id="ferreiro",
               cidade_id=cidade_id, casa_id="casa_2", local_trabalho_id="",
               localizacao_atual_id="casa_2", genero=Genero.FEMININO.value,
               estagio_vida=EstagioVida.ADULTO.value, data_nascimento="1992-01-01T00:00:00",
               gravidez_ticks=1)
    db.npcs.salvar_completo([mae1, mae2])

    mundo = EstadoDoMundo(
        npcs=db.npcs.carregar_todos(),
        locais=db.locais.carregar_por_id(),
        cidades=db.mundo.carregar_cidades_por_id(),
        data_simulada=RelogioMundo.HORA_INICIAL_PADRAO,
        db=db,
    )
    gerenciador = NPCReproductionManager(mundo, config)
    mae1_mem = next(n for n in mundo.npcs if n.id == "npc_mae1")
    mae2_mem = next(n for n in mundo.npcs if n.id == "npc_mae2")

    gerenciador.processar_parto(mae1_mem)
    gerenciador.processar_parto(mae2_mem)

    bebes_no_banco = [n for n in db.npcs.carregar_todos() if n.id not in ("npc_mae1", "npc_mae2")]
    assert len(bebes_no_banco) == 2, "os dois partos no mesmo segundo tinham que gerar bebês distintos"
