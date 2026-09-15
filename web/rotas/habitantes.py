"""
MODULE: habitantes.py
FUNÇÃO: Aba Habitantes do painel — lista paginada/filtrada no SQL.

DESCRIÇÃO:
    P02 (docs/16_PLANO_PAINEL_E_IA.md): antes `/api/update` mandava TODOS os NPCs
    do mundo e o JS filtrava/paginava em memória (Armadilha 24) — agora
    `RepositorioNPC.listar_habitantes`/`contar_habitantes` fazem isso no SQL.
"""
from flask import Blueprint, jsonify, request

from config import cfg_get, get_config
from engine.models import Acao, EstagioVida, SituacaoHabitante
from engine.repositorios.npc import FiltroHabitantes
from web.banco import obter_db
from web.rotas._erros import registrar_erro_handler
from web.serializadores import serializar_filtros_habitantes, serializar_habitante

habitantes_bp = Blueprint('habitantes', __name__)
registrar_erro_handler(habitantes_bp)


@habitantes_bp.errorhandler(ValueError)
def valor_invalido(e):
    """Mais específico que o `Exception` de `registrar_erro_handler` (Flask
    escolhe o handler mais próximo na MRO) — filtro/paginação com valor que não
    bate com o enum ou não é número vira 400, não 500."""
    return jsonify({"error": str(e)}), 400


def _filtro_da_query() -> FiltroHabitantes:
    cfg_painel = cfg_get(get_config(), "painel")
    por_pagina = min(int(request.args.get("por_pagina", cfg_get(cfg_painel, "habitantes_por_pagina"))),
                      cfg_get(cfg_painel, "habitantes_por_pagina_maximo"))
    estagio, acao = request.args.get("estagio"), request.args.get("acao")
    situacao = request.args.get("situacao", SituacaoHabitante.VIVOS.value)
    if estagio is not None: EstagioVida(estagio)
    if acao is not None: Acao(acao)
    SituacaoHabitante(situacao)

    cidade = request.args.get("cidade")
    return FiltroHabitantes(
        cidade_id=int(cidade) if cidade else None, busca_nome=request.args.get("busca", ""),
        estagio_vida=estagio, acao=acao, situacao=situacao,
        pagina=int(request.args.get("pagina", 1)), por_pagina=por_pagina)


@habitantes_bp.route('/api/habitantes')
def api_habitantes():
    filtro = _filtro_da_query()
    db = obter_db()
    return jsonify({
        "total": db.npcs.contar_habitantes(filtro),
        "pagina": filtro.pagina, "por_pagina": filtro.por_pagina,
        "habitantes": [serializar_habitante(r) for r in db.npcs.listar_habitantes(filtro)],
    })


@habitantes_bp.route('/api/habitantes/filtros')
def api_habitantes_filtros():
    return jsonify(serializar_filtros_habitantes(obter_db()))
