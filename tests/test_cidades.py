"""
Testes de geometria de cidade — docs/ESPEC_DESENHO_CIDADE.md, Seção 9.2.

Cobre os invariantes que a arquitetura de modelo de cidade (F4) precisa proteger: a base
sozinha basta pra um modelo mínimo gerar uma cidade completa (T5), todo modelo registrado
responde à interface (T6), o contrato de quadrilátero (T2) e o teto de notáveis por
quarteirão (T3, regressão do bug 3.2) sobrevivem à refatoração.
"""
import sys
import os
import json
import random

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.generate_city_geometry import GeradorCidade
from cartographer.cities.modelos import SitioCidade, MODELOS
from cartographer.cities.modelos.base import ModeloCidade, Quadra, Malha
from config import cfg_get

_CIDADE_TESTE = {"nome": "Aurora Vales", "tamanho": "medio", "tipo": "residencial",
                  "x_global": 300, "y_global": 400}


class _ModeloMinimo(ModeloCidade):
    """Só implementa o gancho obrigatório (construir_malha) — T5/F4.7: se isso não gerar
    uma cidade completa, a base não está fazendo o trabalho compartilhado dela."""
    nome = "_teste_minimo"

    def construir_malha(self):
        quadras = []
        for banda in (1, 2):
            for setor in range(4):
                lado = 40.0
                cx, cy = setor * 60.0, banda * 60.0
                quad = [(cx - lado, cy - lado), (cx + lado, cy - lado),
                        (cx + lado, cy + lado), (cx - lado, cy + lado)]
                quadras.append(Quadra(vertices=quad, classes_aresta=["secundaria"] * 4,
                                       banda=banda, bairro=f"Bairro{banda}", id=(banda, setor)))
        return Malha(ruas=[], quadras=quadras, portoes=[], centro_praca=(0.0, 0.0),
                     raio_praca=10.0, raio_nucleo=0.0, num_bandas=3, contorno=[
                         (-40.0, -40.0), (280.0, -40.0), (280.0, 160.0), (-40.0, 160.0)])


def _gerar(nome_modelo_cls=None):
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    rng = random.Random(sitio.seed)
    cls = nome_modelo_cls or MODELOS["radial"]
    modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
    gerador = GeradorCidade(modelo)
    return gerador.gerar()


def test_base_sozinha_basta():
    """T5 — um modelo que só implementa construir_malha gera lotes, edifícios e índice."""
    geo = _gerar(_ModeloMinimo)
    camadas = {f["properties"]["camada"] for f in geo["features"]}
    assert "lote" in camadas
    assert "edificio" in camadas
    assert "quarteirao" in camadas


def test_todo_modelo_registrado_responde_a_interface():
    """T6 — cada classe em MODELOS gera uma cidade sem quebrar, com um sítio sintético."""
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        assert geo["features"], f"modelo {nome} não gerou feature nenhuma"


def test_contrato_de_quadrilatero():
    """T2 — toda Quadra de todo modelo registrado tem exatamente 4 vértices."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    for nome, cls in MODELOS.items():
        rng = random.Random(sitio.seed)
        modelo = cls(sitio, CARTOGRAPHER_CONFIG, rng)
        malha = modelo.construir_malha()
        for quadra in malha.quadras:
            assert len(quadra.vertices) == 4, f"modelo {nome}: quadra com {len(quadra.vertices)} vértices"


def test_teto_de_notaveis_por_quarteirao():
    """T3 — regressão do bug 3.2 (Seção 3.2): marcos e comércio de bairro têm tetos
    INDEPENDENTES por quarteirão (F3.2 — "com o seu próprio teto, separado do dos
    marcos"), então o teto combinado é a soma dos dois. O bug 3.2 original estourava isso
    em ordens de grandeza (48 de 48 marcos num quarteirão só), não por uma unidade."""
    teto_marco = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_notaveis_max_por_quarteirao")
    teto_bairro = cfg_get(CARTOGRAPHER_CONFIG, "cidade_geo_comercio_bairro_max_por_quarteirao")
    teto_combinado = teto_marco + teto_bairro
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        import collections
        por_quarteirao = collections.Counter(
            f["properties"]["quarteirao_id"] for f in geo["features"]
            if f["properties"]["camada"] == "edificio" and f["properties"]["categoria"] != "residencia")
        pior = max(por_quarteirao.values(), default=0)
        assert pior <= teto_combinado, (
            f"modelo {nome}: {pior} notáveis num único quarteirão (teto combinado {teto_combinado})")


def test_aneis_nao_cruzam():
    """G01 — docs/PLANO_CIDADE_VIVA.md Seção 1.1: em radial e organica, o raio de cada
    vértice tem que crescer estritamente por setor (nenhum anel cruza o vizinho), em
    200 seeds por combinação de modelo x tamanho. Antes de G01 a chance de cruzamento
    chegava a 82,5% (radial, 6 anéis) e 100% (organica)."""
    for nome_modelo in ("radial", "organica"):
        for tamanho in ("medio", "grande"):
            for seed_i in range(200):
                cidade = {"nome": f"TesteAneis{nome_modelo}{tamanho}{seed_i}",
                          "tamanho": tamanho, "tipo": "residencial",
                          "x_global": 100 + seed_i, "y_global": 100 + seed_i}
                sitio = SitioCidade.medir(cidade, "ContinenteTeste", CARTOGRAPHER_CONFIG)
                rng = random.Random(sitio.seed)
                modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng)
                malha = modelo.construir_malha()  # a própria asserção de G01 já falha aqui se cruzar
                assert malha.quadras


def test_nenhum_poligono_auto_intersectante():
    """G02 — Seção 1.1: o inset de quadra só rejeitava área quase zero e orientação
    invertida; um quad com vértice muito obtuso passava disso e virava gravata-borboleta
    depois do recuo. Toda feature Polygon emitida (quarteirão e lote) tem que ser simples."""
    for nome, cls in MODELOS.items():
        geo = _gerar(cls)
        for f in geo["features"]:
            if f["geometry"]["type"] != "Polygon":
                continue
            anel = f["geometry"]["coordinates"][0][:-1]
            assert GeradorCidade._e_quad_simples(anel) if len(anel) == 4 else True, (
                f"modelo {nome}: polígono {f['properties']['camada']} auto-intersectante")


def test_encolher_quad_rejeita_quad_concavo():
    """G02: `_encolher_quad` devolve None para um quad de entrada já auto-intersectante
    (bowtie), em vez de tentar encolher e emitir geometria inválida."""
    sitio = SitioCidade.medir(_CIDADE_TESTE, "ContinenteTeste", CARTOGRAPHER_CONFIG)
    rng = random.Random(sitio.seed)
    modelo = MODELOS["radial"](sitio, CARTOGRAPHER_CONFIG, rng)
    gerador = GeradorCidade(modelo)
    bowtie = [(0.0, 0.0), (40.0, 40.0), (40.0, 0.0), (0.0, 40.0)]
    assert gerador._encolher_quad(bowtie, [3.0] * 4) is None


def test_determinismo():
    """T1 — gerar a mesma cidade duas vezes dá o mesmo GeoJSON, byte a byte."""
    a = _gerar()
    b = _gerar()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_praca_sem_lote_dentro():
    """T4 — nenhum centroide de lote cai dentro do polígono (aqui: círculo) da praça."""
    geo = _gerar()
    praca = next(f for f in geo["features"] if f["properties"]["camada"] == "praca")
    xs = [c[0] for c in praca["geometry"]["coordinates"][0]]
    ys = [c[1] for c in praca["geometry"]["coordinates"][0]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    raio = (max(xs) - min(xs)) / 2
    for f in geo["features"]:
        if f["properties"]["camada"] != "lote":
            continue
        coords = f["geometry"]["coordinates"][0][:-1]
        lx = sum(c[0] for c in coords) / len(coords)
        ly = sum(c[1] for c in coords) / len(coords)
        dist = ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5
        assert dist >= raio * 0.99, "lote com centroide dentro da praça"
