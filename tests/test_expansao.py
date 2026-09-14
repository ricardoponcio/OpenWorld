"""
Testes de `cartographer.cities.expansao` — X02, docs/12_PLANO_CIDADE_VIVA.md: a geometria
do arrabalde é uma função pura, sem banco, sem NPC. Mesmo padrão de `tests/test_cidades.py`
(sítio real, `SitioCidade.medir` contra o terreno cacheado do projeto) — os testes que
dependem de terreno pulam graciosamente se `sitio.terreno` vier `None` (ambiente sem
`database/mapa_composto.npz`), igual `test_sitio_declividade_em_fora_da_janela`.
"""
import sys
import os
import random

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.generate_city_geometry import GeradorCidade
from cartographer.cities.geometria import quad
from cartographer.cities.modelos import SitioCidade, MODELOS
from cartographer.cities import expansao

_CIDADE_TESTE = {"nome": "Vale do Arrabalde", "tamanho": "medio", "tipo": "residencial",
                  "x_global": 300, "y_global": 400}

_LOTES_ALVO = 15
_COMPRIMENTO_M = 180
_COMPRIMENTO_MAX_M = 520


def _cidade_e_sitio(nome_modelo="radial"):
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    rng = random.Random(sitio.seed)
    modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng)
    gerador = GeradorCidade(modelo)
    return sitio, gerador.gerar()


def _local(sitio, coords):
    """Desfaz `_geojson_coord`: de [lng, lat] pra metros locais (centro da cidade = origem)."""
    pontos = []
    for lng, lat in coords[:-1]:
        x_m = (lng - sitio.x_mundo) * sitio.metros_por_px
        y_m = (-lat - sitio.y_mundo) * sitio.metros_por_px
        pontos.append((x_m, y_m))
    return pontos


def _arrabalde_de_teste(sitio, geo):
    seed_expansao = sitio.seed ^ (0xA53F * 1)
    return expansao.gerar_arrabalde(sitio, geo, _LOTES_ALVO, seed_expansao, CARTOGRAPHER_CONFIG,
                                     _COMPRIMENTO_M, _COMPRIMENTO_MAX_M)


def test_arrabalde_nao_intersecta_quarteirao_existente():
    sitio, geo = _cidade_e_sitio()
    if sitio.terreno is None:
        return  # sem cartógrafo disponível neste ambiente — nada a checar
    features, _ = _arrabalde_de_teste(sitio, geo)
    assert features, "cidade de teste devia ter ao menos uma direção de saída viável"

    existentes = [_local(sitio, f["geometry"]["coordinates"][0]) for f in geo["features"]
                  if f["properties"].get("camada") == "quarteirao"]
    novos = [_local(sitio, f["geometry"]["coordinates"][0]) for f in features
             if f["properties"].get("camada") in ("quarteirao", "lote", "patio")]

    def arestas(poligono):
        n = len(poligono)
        return [(poligono[i], poligono[(i + 1) % n]) for i in range(n)]

    for novo in novos:
        for existente in existentes:
            for a0, a1 in arestas(novo):
                for b0, b1 in arestas(existente):
                    assert not quad.segmentos_cruzam(a0, a1, b0, b1), (
                        "uma quadra/lote do arrabalde cruza um quarteirão existente")


def test_todo_lote_do_arrabalde_tem_frente():
    sitio, geo = _cidade_e_sitio()
    if sitio.terreno is None:
        return
    features, lotes_meta = _arrabalde_de_teste(sitio, geo)
    lotes_feats = [f for f in features if f["properties"].get("camada") == "lote"]
    assert lotes_feats, "nenhum lote gerado pra cidade de teste"
    assert all(f["properties"].get("classe_frente") for f in lotes_feats)
    assert len(lotes_meta) == len(lotes_feats)


def test_ocupacao_inicial_do_arrabalde_e_zero():
    """X02 item 9 — tudo nasce livre; a expansão cria espaço, não edifício."""
    sitio, geo = _cidade_e_sitio()
    if sitio.terreno is None:
        return
    features, _ = _arrabalde_de_teste(sitio, geo)
    lotes_feats = [f for f in features if f["properties"].get("camada") == "lote"]
    assert lotes_feats and all(f["properties"].get("estado") == "livre" for f in lotes_feats)
    assert not any(f["properties"].get("camada") == "edificio" for f in features)


def test_arrabalde_marca_banda_acima_da_maior_existente():
    sitio, geo = _cidade_e_sitio()
    if sitio.terreno is None:
        return
    banda_max_antes = max(f["properties"].get("banda", 0) for f in geo["features"]
                          if f["properties"].get("camada") == "quarteirao")
    features, _ = _arrabalde_de_teste(sitio, geo)
    bandas_novas = {f["properties"]["banda"] for f in features
                    if f["properties"].get("camada") == "quarteirao"}
    assert bandas_novas == {banda_max_antes + 1}


def test_arrabalde_e_deterministico():
    """`gerar_arrabalde` chamada duas vezes com a mesma seed dá o mesmo resultado —
    X02, seção "Validar"."""
    sitio, geo = _cidade_e_sitio()
    if sitio.terreno is None:
        return
    r1 = _arrabalde_de_teste(sitio, geo)
    r2 = _arrabalde_de_teste(sitio, geo)
    assert r1 == r2


def test_sem_portao_nenhum_devolve_vazio():
    """Função pura, sem gancho escondido: sem portão nenhum no GeoJSON, não há de onde
    sair — devolve listas vazias, nunca uma exceção."""
    sitio, geo = _cidade_e_sitio()
    geo_sem_portao = dict(geo, features=[f for f in geo["features"]
                                          if f["properties"].get("camada") != "portao"])
    features, lotes_meta = _arrabalde_de_teste(sitio, geo_sem_portao)
    assert features == [] and lotes_meta == []
