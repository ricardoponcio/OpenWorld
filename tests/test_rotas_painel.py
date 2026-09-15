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

import json

from config import cfg_get, get_config
from engine.database import DatabaseManager
from engine.models import NPC, EstagioVida, MetaChave
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


def test_api_estado_traz_polling_ms_do_config():
    """P02 (docs/16_PLANO_PAINEL_E_IA.md): estado.js lê o intervalo daqui — nunca
    duplica painel.estado_polling_ms como número solto no JS."""
    resposta = app.test_client().get('/api/estado')
    data = resposta.get_json()

    assert data["polling_ms"] == cfg_get(get_config(), "painel", "estado_polling_ms")


def test_api_habitantes_pagina_e_filtra():
    """P02: ponta a ponta via Flask (não só o repositório) — página 1 de 10 da
    cidade 2, ordenada por nome."""
    _db_teste.npcs.salvar_completo(
        [_npc(f"hab_c2_{i}", nome=f"Hab C2 {i:02d}", cidade_id=2) for i in range(15)])

    resposta = app.test_client().get('/api/habitantes?cidade=2&pagina=1&por_pagina=10')
    data = resposta.get_json()

    assert data["total"] == 15
    assert data["pagina"] == 1
    assert data["por_pagina"] == 10
    assert len(data["habitantes"]) == 10
    assert data["habitantes"][0]["nome"] == "Hab C2 00"
    assert "status" in data["habitantes"][0] and "bio" in data["habitantes"][0]


def test_api_habitantes_situacao_invalida_devolve_400():
    resposta = app.test_client().get('/api/habitantes?situacao=zumbi')
    assert resposta.status_code == 400
    assert "error" in resposta.get_json()


def test_api_habitantes_por_pagina_respeita_teto_do_config():
    teto = cfg_get(get_config(), "painel", "habitantes_por_pagina_maximo")
    resposta = app.test_client().get(f'/api/habitantes?por_pagina={teto + 1000}')
    assert resposta.get_json()["por_pagina"] == teto


def test_api_habitantes_filtros_devolve_enums_e_config():
    resposta = app.test_client().get('/api/habitantes/filtros')
    data = resposta.get_json()

    assert "vivos" in data["situacoes"] and "mortos" in data["situacoes"]
    assert "adulto" in data["estagios"]
    assert data["painel"]["habitantes_por_pagina"] == cfg_get(get_config(), "painel", "habitantes_por_pagina")


def test_api_ficha_habitante_resolve_nomes_de_pais():
    """P03 (docs/16_PLANO_PAINEL_E_IA.md): ponta a ponta via Flask — GET
    /api/habitantes/<id> nunca colide com a rota estática /api/habitantes/filtros
    (Werkzeug prioriza a regra sem parâmetro)."""
    _db_teste.npcs.salvar_completo([
        _npc("ficha_mae", nome="Ficha Mãe"),
        _npc("ficha_filho", nome="Ficha Filho", mae_id="ficha_mae"),
    ])

    resposta = app.test_client().get('/api/habitantes/ficha_filho')
    data = resposta.get_json()

    assert data["mae_nome"] == "Ficha Mãe"
    assert data["bio"]["idade"] >= 0


def test_api_ficha_habitante_inexistente_devolve_404():
    resposta = app.test_client().get('/api/habitantes/npc_fantasma_xyz')
    assert resposta.status_code == 404


def test_api_estatisticas_devolve_o_json_gravado():
    """P05 (docs/16_PLANO_PAINEL_E_IA.md): a rota devolve o retrato de
    MetaChave.ESTATISTICAS como está — nunca recalcula nada (Armadilha 24)."""
    gravado = {"total": {"vivos_por_estagio": {"adulto": 5}}, "hoje": {"nascimento": 2}}
    _db_teste.meta.salvar(MetaChave.ESTATISTICAS, json.dumps(gravado))

    resposta = app.test_client().get('/api/estatisticas')
    data = resposta.get_json()

    assert data["total"]["vivos_por_estagio"]["adulto"] == 5
    assert data["hoje"]["nascimento"] == 2
    assert data["polling_ms"] == cfg_get(get_config(), "painel", "estatisticas_polling_ms")


def test_api_estatisticas_sem_nada_gravado_devolve_dict_vazio_mais_polling():
    _dir_vazio = tempfile.mkdtemp(prefix="openworld_test_estatisticas_vazio_")
    db_vazio = DatabaseManager(db_path=os.path.join(_dir_vazio, "teste.db"), pool_size=2)
    configurar_db(db_vazio)
    try:
        resposta = app.test_client().get('/api/estatisticas')
        data = resposta.get_json()
        assert "total" not in data
        assert data["polling_ms"] == cfg_get(get_config(), "painel", "estatisticas_polling_ms")
    finally:
        configurar_db(_db_teste)  # devolve o banco compartilhado pros outros testes deste arquivo
