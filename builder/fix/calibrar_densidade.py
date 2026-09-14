"""
SCRIPT: calibrar_densidade.py
OBJETIVO: Medir k/e da fórmula `lotes = k * raio^e`, por modelo de cidade — R02 (docs/
          13_PLANO_POPULACAO_E_ESCALA.md, Bloco R). Nunca DEDUZA a fórmula: a densidade de
          lote por raio varia por modelo — `grade` cresce com raio² (é um disco
          preenchido), `linear` cresce quase linear (é uma fita ao longo de um eixo) — e
          só a medição real, na geometria de HOJE, dá o expoente certo.
MOMENTO DE USO: depois de qualquer mudança que toque a geometria de quadra/lote (Blocos
                S, L ou C, docs/13_PLANO_POPULACAO_E_ESCALA.md e
                docs/14_PLANO_AVANCO_E_CALIBRAGEM.md) — a densidade medida fica
                desatualizada, porque muda quantos lotes uma mesma cidade produz pro
                mesmo raio.

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine e fora do runtime — só produz
um número pra colar em `config.json`. Não é importada de dentro de `engine/`, `web/` ou
`cartographer/` (11_ARQUITETURA.md Seção 2).
"""
import os
import sys
import json
import math
import random
import statistics

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.modelos import SitioCidade, MODELOS
from cartographer.cities.geometria.gerador import GeradorCidade

# Dois pontos bem separados — perto o bastante pra não sair da faixa de raio real das
# cidades, longe o bastante pra o ajuste de e/k não amplificar ruído de amostragem.
RAIOS_MEDICAO_M = (300.0, 900.0)
# R02, Ação 2: "use ao menos 5 sementes por ponto e tire a mediana — uma cidade só
# varia com o terreno".
SEMENTES_POR_PONTO = 5
# Tamanho/tipo do sítio só afetam clima/terreno amostrados (não usados pra decidir
# raio, que é FORÇADO aqui) — "medio"/"residencial" são neutros o bastante.
TAMANHO_SITIO = "medio"
TIPO_SITIO = "residencial"


def _contar_lotes(nome_modelo: str, raio_m: float, indice_semente: int) -> int:
    """Gera uma cidade-semente com o raio FORÇADO (não derivado de domicílios — R01)
    e conta quantas features `lote` ela produz. Cada `indice_semente` vira um nome de
    cidade diferente, e portanto um `seed` (zlib.crc32) e uma sequência de `rng`
    diferentes — é o "ao menos 5 sementes" da Ação 2."""
    cidade = {
        "nome": f"Calibragem {nome_modelo} {raio_m:.0f}m #{indice_semente}",
        "tamanho": TAMANHO_SITIO, "tipo": TIPO_SITIO,
        "x_global": 200.0 + indice_semente, "y_global": 200.0 + indice_semente,
    }
    sitio = SitioCidade.medir(cidade, "ContinenteCalibragem", CARTOGRAPHER_CONFIG)
    rng = random.Random(sitio.seed)
    modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng, raio_m_forcado=raio_m)
    geojson = GeradorCidade(modelo).gerar()
    return sum(1 for f in geojson["features"] if f["properties"].get("camada") == "lote")


def medir_k_e(nome_modelo: str):
    """Ação 2 de R02: gera a mesma cidade-semente em DOIS raios, ajusta
    `lotes = k * raio^e` pelos dois pontos:
    `e = log(lotes2/lotes1) / log(raio2/raio1)`, `k = lotes1 / raio1**e`."""
    raio1, raio2 = RAIOS_MEDICAO_M
    lotes1 = statistics.median(_contar_lotes(nome_modelo, raio1, i) for i in range(SEMENTES_POR_PONTO))
    lotes2 = statistics.median(_contar_lotes(nome_modelo, raio2, i) for i in range(SEMENTES_POR_PONTO))
    e = math.log(lotes2 / lotes1) / math.log(raio2 / raio1)
    k = lotes1 / (raio1 ** e)
    return k, e, lotes1, lotes2


def main():
    print(f"Medindo lotes = k * raio^e por modelo, em raios {RAIOS_MEDICAO_M} m, "
          f"mediana de {SEMENTES_POR_PONTO} sementes por ponto.\n")
    cab_r1 = f"lotes@{RAIOS_MEDICAO_M[0]:.0f}m"
    cab_r2 = f"lotes@{RAIOS_MEDICAO_M[1]:.0f}m"
    print(f"{'modelo':<10} {cab_r1:>14} {cab_r2:>14} {'k':>14} {'e':>8}")

    resultado = {}
    for nome_modelo in MODELOS:
        k, e, lotes1, lotes2 = medir_k_e(nome_modelo)
        resultado[nome_modelo] = [round(k, 6), round(e, 4)]
        print(f"{nome_modelo:<10} {lotes1:>14.0f} {lotes2:>14.0f} {k:>14.6f} {e:>8.4f}")

    print('\nCole em config.json["cartografia"]["cidade_geo_densidade_lote_por_modelo"]:')
    print(json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    main()
