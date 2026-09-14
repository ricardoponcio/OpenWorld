"""
Testes de `GerenciadorUrbanismo.avaliar_expansao`/`_aplicar_arrabalde` — X01/X03,
docs/12_PLANO_CIDADE_VIVA.md. Ao contrário de `tests/test_urbanismo.py` (O02, tudo em
memória), estes tocam disco de verdade: um GeoJSON de cidade real (gerado pela mesma
pipeline de `cartographer/cities/`, escrito num diretório temporário) e a mesma
sequência ler → gerar_arrabalde → escrever atômico → reindexar que a simulação real usa.
"""
import json
import os
import random

import pytest

import engine.mechanics.urbanismo as urbanismo_mod
from engine.mechanics.urbanismo import GerenciadorUrbanismo, SpecObra
from engine.models import Cidade, Lote, LoteEstado, TipoEvento

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.generate_city_geometry import GeradorCidade
from cartographer.cities.modelos import SitioCidade, MODELOS

from tests.mundo_sintetico import mundo_de

_CIDADE_TESTE = {"nome": "Vale da Expansao", "tamanho": "medio", "tipo": "residencial",
                  "x_global": 300, "y_global": 400}
_SLUG = "vale_da_expansao"


def _sitio_de_teste():
    return SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)


def _gerar_geojson_real(sitio):
    rng = random.Random(sitio.seed)
    modelo = MODELOS["radial"](sitio, CARTOGRAPHER_CONFIG, rng)
    gerador = GeradorCidade(modelo)
    return gerador.gerar(), gerador.indice(_SLUG)


def _config_x01(**overrides):
    base = {
        "lotes_livres_minimo": 8,
        "fracao_livre_minima": 0.03,
        "arrabalde_comprimento_m": 180,
        "arrabalde_comprimento_max_m": 520,
    }
    base.update(overrides)
    return {"urbanismo": base}


def _cidade_teste(cidade_id=1):
    return Cidade(id=cidade_id, continente_uuid="continente-teste", nome="Vale da Expansao",
                  tamanho="medio", tipo="residencial", x_global=300, y_global=400)


def _semear_lotes(mundo, geojson, cidade_id, estado):
    lotes = []
    for feat in geojson["features"]:
        if feat["properties"].get("camada") != "lote":
            continue
        p = feat["properties"]
        lotes.append(Lote(id=p["id"], cidade_id=cidade_id, quarteirao_id=p["quarteirao_id"],
                           bairro=p["bairro"], banda=p["banda"], classe_frente=p["classe_frente"],
                           area_m2=p["area_m2"], x=0.0, y=0.0, estado=estado, estado_inicial=estado))
    mundo.db.lotes.salvar_em_lote(lotes)


@pytest.fixture
def cidade_no_disco(tmp_path, monkeypatch):
    """Escreve um GeoJSON de cidade real (mesma pipeline de `cartographer/cities/`) e o
    `_indice.json` correspondente num diretório temporário, e aponta
    `GerenciadorUrbanismo` pra lá — `_aplicar_arrabalde` (X03) escreve em arquivo de
    verdade, não faz sentido testar sem tocar disco."""
    sitio = _sitio_de_teste()
    if sitio.terreno is None:
        pytest.skip("sem cartógrafo disponível neste ambiente (database/mapa_composto.npz ausente)")
    geojson, indice = _gerar_geojson_real(sitio)

    (tmp_path / f"{_SLUG}.geojson").write_text(json.dumps(geojson, ensure_ascii=False))
    (tmp_path / "_indice.json").write_text(
        json.dumps({"gerado_em": "teste", "cidades": [indice]}, ensure_ascii=False))
    monkeypatch.setattr(urbanismo_mod, "CIDADES_GEOJSON_DIR", str(tmp_path))
    return geojson


def test_avaliar_expansao_satura_e_cria_arrabalde(cidade_no_disco):
    geojson = cidade_no_disco
    cidade = _cidade_teste()
    mundo = mundo_de(cidades=[cidade])
    _semear_lotes(mundo, geojson, cidade.id, LoteEstado.OCUPADO.value)  # 0 livre — satura na certa

    gerenciador = GerenciadorUrbanismo(mundo, _config_x01())
    assert gerenciador.avaliar_expansao(cidade.id) is True

    caminho = os.path.join(urbanismo_mod.CIDADES_GEOJSON_DIR, f"{_SLUG}.geojson")
    with open(caminho, "r", encoding="utf-8") as f:
        geojson_novo = json.load(f)
    assert len(geojson_novo["features"]) > len(geojson["features"])

    # Armadilha 3 (o padrão de crescimento real deste projeto é sempre ACRESCENTAR,
    # nunca remover/renumerar — X02/X03 nunca editam feature existente): toda feature
    # original sobrevive intacta, byte a byte, na mesma posição — nenhum id ou
    # geometria pré-existente foi tocado por causa das features novas.
    assert geojson_novo["features"][:len(geojson["features"])] == geojson["features"]

    lotes_novos_feats = [f for f in geojson_novo["features"]
                         if f["properties"].get("camada") == "lote"
                         and f["properties"].get("arrabalde") is not None]
    assert lotes_novos_feats, "arrabalde devia ter gerado ao menos um lote novo"

    contagem = mundo.db.lotes.contar_por_estado(cidade.id)
    assert contagem.get(LoteEstado.LIVRE.value, 0) == len(lotes_novos_feats)

    with open(os.path.join(urbanismo_mod.CIDADES_GEOJSON_DIR, "_indice.json"), "r", encoding="utf-8") as f:
        indice_novo = json.load(f)
    entrada = next(c for c in indice_novo["cidades"] if c["slug"] == _SLUG)
    assert entrada["arrabaldes"] == 1
    assert entrada["camadas"]["lote"]["n"] == sum(
        1 for f in geojson_novo["features"] if f["properties"].get("camada") == "lote")

    eventos = mundo.db.eventos.salvos
    assert any(getattr(e, "tipo_evento", None) == TipoEvento.EXPANSAO_URBANA.value for e in eventos)


def test_avaliar_expansao_no_maximo_uma_vez_por_dia(cidade_no_disco):
    geojson = cidade_no_disco
    cidade = _cidade_teste()
    mundo = mundo_de(cidades=[cidade])
    _semear_lotes(mundo, geojson, cidade.id, LoteEstado.OCUPADO.value)

    gerenciador = GerenciadorUrbanismo(mundo, _config_x01())
    assert gerenciador.avaliar_expansao(cidade.id) is True
    assert gerenciador.avaliar_expansao(cidade.id) is False  # mesmo dia simulado — no-op


def test_avaliar_expansao_nao_dispara_sem_saturacao(cidade_no_disco):
    geojson = cidade_no_disco
    cidade = _cidade_teste()
    mundo = mundo_de(cidades=[cidade])
    _semear_lotes(mundo, geojson, cidade.id, LoteEstado.LIVRE.value)  # tudo livre

    gerenciador = GerenciadorUrbanismo(mundo, _config_x01())
    assert gerenciador.avaliar_expansao(cidade.id) is False

    caminho = os.path.join(urbanismo_mod.CIDADES_GEOJSON_DIR, f"{_SLUG}.geojson")
    with open(caminho, "r", encoding="utf-8") as f:
        geojson_intacto = json.load(f)
    assert len(geojson_intacto["features"]) == len(geojson["features"])


def test_abrir_obra_sem_lote_dispara_avaliacao_imediata(cidade_no_disco):
    """X01 item 3: `abrir_obra` devolvendo `None` também dispara a avaliação, sem
    esperar a varredura diária."""
    geojson = cidade_no_disco
    cidade = _cidade_teste()
    mundo = mundo_de(cidades=[cidade])
    _semear_lotes(mundo, geojson, cidade.id, LoteEstado.OCUPADO.value)

    from tests.mundo_sintetico import adulto
    npc = adulto("npc_1", "Testador", cidade_id=cidade.id, dinheiro_total_pc=1000.0)
    gerenciador = GerenciadorUrbanismo(mundo, _config_x01())

    spec = SpecObra(categoria="taverna", tipo_local="Taverna", nome="Taverna Nova", capacidade=15)
    resultado = gerenciador.abrir_obra(cidade.id, spec, dono_npc=npc)
    assert resultado is None  # sem lote livre nenhum antes da expansão

    contagem = mundo.db.lotes.contar_por_estado(cidade.id)
    assert contagem.get(LoteEstado.LIVRE.value, 0) > 0, (
        "abrir_obra sem lote devia ter disparado avaliar_expansao imediatamente")
