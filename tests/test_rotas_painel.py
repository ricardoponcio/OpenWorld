"""
Teste de `GET /api/estado` (P01, docs/16_PLANO_PAINEL_E_IA.md) — substitui
`/api/update` (23 MB/s, Seção 2.1 do plano): nunca devolve a lista de NPCs/locais
(Armadilha 24).

`web/dashboard.py` faz `db = obter_db()` na própria importação — para nunca criar
um `DatabaseManager` apontando pro `database/openworld.db` de produção durante os
testes, configuramos um banco de teste (`web.banco.configurar_db`) ANTES da
primeira importação de `web.dashboard` neste processo (mesmo padrão de
`config.resolver.configurar_fonte`).
"""
import tempfile
import os

from engine.database import DatabaseManager
from engine.models import NPC, EstagioVida
from web.banco import configurar_db

_dir_teste = tempfile.mkdtemp(prefix="openworld_test_rotas_painel_")
_db_teste = DatabaseManager(db_path=os.path.join(_dir_teste, "teste.db"), pool_size=2)
configurar_db(_db_teste)

from web.dashboard import app  # noqa: E402 — só depois de configurar_db (ver docstring)


def _npc(npc_id, **campos):
    base = dict(id=npc_id, nome=f"NPC {npc_id}", profissao="Ferreiro",
                local_trabalho_id="", localizacao_atual_id="casa_1", casa_id="casa_1",
                cidade_id=1, estagio_vida=EstagioVida.ADULTO.value)
    base.update(campos)
    return NPC(**base)


def test_api_estado_nao_devolve_npcs_nem_locais():
    _db_teste.npcs.salvar_completo([_npc(f"npc_{i}") for i in range(500)])

    resposta = app.test_client().get('/api/estado')
    data = resposta.get_json()

    assert "npcs" not in data
    assert "locs" not in data
    assert "locais" not in data
    assert len(resposta.data) < 5 * 1024


def test_api_estado_traz_velocidade_efetiva_nula_sem_estatisticas():
    resposta = app.test_client().get('/api/estado')
    data = resposta.get_json()

    assert data["velocidade_efetiva"] is None
    assert data["hora"]
    assert isinstance(data["cronicas"], list)
