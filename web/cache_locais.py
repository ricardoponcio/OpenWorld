"""
MODULE: cache_locais.py
FUNÇÃO: Índice em memória local_id -> (x, y) para a camada de NPCs do Mapa Live.

DESCRIÇÃO:
    M04 (docs/16_PLANO_PAINEL_E_IA.md): a camada de NPCs precisa, a cada bbox
    pedida, saber quais locais caem dentro dela — reabrir e desserializar 24 mil
    linhas de `locais` por requisição seria o mesmo problema que
    `run_simulation.py::sincronizar_locais_se_mudou` já resolve do lado da
    engine. Mesmo contrato: recarrega só quando `MetaChave.LOCAIS_VERSAO` mudou
    desde a última vez, não a cada chamada.
"""
from engine.models import MetaChave
from web.banco import obter_db

_indice = []       # [{"id", "x", "y"}, ...]
_por_id = {}        # local_id -> (x, y)
_versao_vista = None


def _recarregar_se_preciso() -> None:
    global _indice, _por_id, _versao_vista
    db = obter_db()
    versao_atual = db.meta.carregar(MetaChave.LOCAIS_VERSAO)
    if versao_atual == _versao_vista and _indice:
        return
    locais = db.locais.listar_coordenadas()
    _indice = [{"id": l["id"], "x": l["coordenadas"][0], "y": l["coordenadas"][1]}
               for l in locais if l["coordenadas"]]
    _por_id = {l["id"]: (l["x"], l["y"]) for l in _indice}
    _versao_vista = versao_atual


def locais_na_bbox(x0: float, y0: float, x1: float, y1: float) -> list:
    _recarregar_se_preciso()
    return [l["id"] for l in _indice if x0 <= l["x"] <= x1 and y0 <= l["y"] <= y1]


def coordenada_do_local(local_id: str):
    """`(x, y)` do local, ou `None` se não existir/estiver inativo."""
    _recarregar_se_preciso()
    return _por_id.get(local_id)
