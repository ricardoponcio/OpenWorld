"""
O laço sobre `world_manifest.json`: mede o sítio de cada cidade, escolhe e instancia o
modelo, gera o GeoJSON (`GeradorCidade`) e escreve arquivo + índice (Q02, docs/
12_PLANO_CIDADE_VIVA.md).
"""
import os
import sys
import json
import random
from datetime import datetime

from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.cities.modelos import SitioCidade, MODELOS, escolher_modelo
from cartographer.cities.escala import corrigir_raio_por_newton

from .gerador import GeradorCidade

MANIFEST_PATH = "database/world_manifest.json"
OUTPUT_DIR = "database/cidades"


def gerar_geometria_para_manifesto(nome_filtro=None):
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ Manifesto não encontrado em {MANIFEST_PATH}.")
        sys.exit(1)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # E5: índice por cidade (database/cidades/_indice.json — extensão .json, não
    # .geojson, pra `_listar_arquivos_geojson_cidades` não confundir com uma "cidade"
    # fantasma). Regeração de UMA cidade (nome_filtro) faz merge com o índice existente
    # em vez de sobrescrever as outras 14.
    indice_path = os.path.join(OUTPUT_DIR, "_indice.json")
    indice_por_slug = {}
    if nome_filtro and os.path.exists(indice_path):
        with open(indice_path, "r", encoding="utf-8") as f:
            indice_por_slug = {c["slug"]: c for c in json.load(f).get("cidades", [])}

    total = 0
    sem_nucleo_urbanizavel = []  # F1.2: cidades onde a praça toma o núcleo inteiro
    for cont in manifest.get("continentes", []):
        for cidade in cont.get("cidades", []):
            if nome_filtro and cidade["nome"].lower() != nome_filtro.lower():
                continue
            if "x_global" not in cidade or "y_global" not in cidade:
                continue

            # F4.5/F8.2: sítio medido primeiro (posição/geografia/clima) — o modelo é
            # escolhido por tipo+seed (lista de possibilidades + sorteio ponderado, rng
            # DERIVADO pra não deslocar a sequência do rng principal — Seção 10 item 1),
            # e só depois instanciado com o sítio e o rng principal prontos.
            sitio = SitioCidade.medir(cidade, cont["nome"], CARTOGRAPHER_CONFIG)
            nome_modelo = escolher_modelo(sitio, CARTOGRAPHER_CONFIG)
            rng = random.Random(sitio.seed)
            modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng)

            gerador = GeradorCidade(modelo)
            geojson = gerador.gerar()

            # R02, Ação 5: `lotes = k*raio^e` é medido, não deduzido — mas continua uma
            # ESTIMATIVA; se a geometria real desta cidade especificamente desviar mais
            # de 15% do alvo, corrige o raio UMA vez (nunca em laço) e regera.
            n_lotes_reais = sum(1 for f in geojson["features"] if f["properties"].get("camada") == "lote")
            raio_corrigido, precisa_regerar = corrigir_raio_por_newton(
                CARTOGRAPHER_CONFIG, nome_modelo, sitio.tamanho, modelo.raio_m,
                modelo.lotes_alvo, n_lotes_reais)
            if precisa_regerar and raio_corrigido != modelo.raio_m:
                print(f"  🔧 {cidade['nome']}: {n_lotes_reais} lote(s) reais desviaram "
                      f">15% do alvo ({modelo.lotes_alvo:.0f}) — corrigindo raio de "
                      f"{modelo.raio_m:.0f}m pra {raio_corrigido:.0f}m e regerando uma vez.")
                rng = random.Random(sitio.seed)
                modelo = MODELOS[nome_modelo](sitio, CARTOGRAPHER_CONFIG, rng,
                                               raio_m_forcado=raio_corrigido)
                gerador = GeradorCidade(modelo)
                geojson = gerador.gerar()

            slug = cidade["nome"].lower().replace(" ", "_")
            caminho = os.path.join(OUTPUT_DIR, f"{slug}.geojson")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False, indent=2)
            indice_por_slug[slug] = gerador.indice(slug)
            n_edificios = sum(1 for feat in geojson["features"] if feat["properties"].get("camada") == "edificio")
            print(f"  🏰 {cidade['nome']:<24} -> {caminho} ({n_edificios} edifícios)")
            if modelo.malha.raio_nucleo == 0.0:
                sem_nucleo_urbanizavel.append(cidade["nome"])
            total += 1

    with open(indice_path, "w", encoding="utf-8") as f:
        json.dump({
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "cidades": list(indice_por_slug.values()),
        }, f, ensure_ascii=False, indent=2)

    if sem_nucleo_urbanizavel:
        print(f"  ℹ️  {len(sem_nucleo_urbanizavel)} cidade(s) com núcleo cívico não-urbanizável "
              f"(praça toma o disco inteiro — F1.2): {', '.join(sem_nucleo_urbanizavel)}")
    print(f"✅ [GEOMETRIA-CIDADE] {total} cidade(s) geradas. Índice: {indice_path}")
