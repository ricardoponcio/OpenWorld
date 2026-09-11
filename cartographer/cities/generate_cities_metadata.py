import os
import sys
import json
import numpy as np
try:
    from scipy.ndimage import distance_transform_edt
except ImportError:
    distance_transform_edt = None

# Garante que a raiz do projeto esteja no sys.path
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.ai.city_manager_ai import CityManagerAIClient
from cartographer.math.climate import ClimateProcessor
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"
NPZ_PATH = "database/mapa_composto.npz"


def _pontuar_sitio(sub_alt, sub_bioma, is_terra, bioma_id, nivel_mar, nivel_montanha, cfg):
    """
    Fase 1.4 (P1.4): pontuação de sítio — substitui `random.choice` entre pixels do bioma
    por uma escolha informada. 3 critérios, cada um em [0,1], combinados por peso de config:
    adjacência à costa (porto), altitude baixa/plana (construível), e bioma pedido.
    """
    if distance_transform_edt is not None:
        # Distância (em px) até o pixel de água/fora-da-bbox mais próximo — pontuação alta
        # perto da costa, sem precisar varrer vizinhança manualmente.
        dist_costa = distance_transform_edt(is_terra)
    else:
        dist_costa = np.full(is_terra.shape, 10.0, dtype=np.float32)  # fallback neutro sem scipy
    escala_costa = cfg_get(cfg, "cidades_escala_distancia_costa_px")
    score_costa = np.exp(-dist_costa / max(1e-6, escala_costa))

    score_altitude = 1.0 - np.clip((sub_alt - nivel_mar) / max(1e-6, nivel_montanha - nivel_mar), 0.0, 1.0)

    score_bioma = np.where(sub_bioma == bioma_id, 1.0, 0.3)

    peso_costa = cfg_get(cfg, "cidades_peso_costa")
    peso_altitude = cfg_get(cfg, "cidades_peso_altitude")
    peso_bioma = cfg_get(cfg, "cidades_peso_bioma")

    score = peso_costa * score_costa + peso_altitude * score_altitude + peso_bioma * score_bioma
    score = np.where(is_terra, score, -np.inf)
    return score

def gerar_metadados_cidades(uuid_ou_nome: str):
    if not os.path.exists(MANIFEST_PATH):
        print(f"Erro: Manifesto não encontrado em {MANIFEST_PATH}")
        sys.exit(1)

    # 1. Carregar o manifesto
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    # 2. Localizar o continente
    cont = next((c for c in manifest.get("continentes", []) if c["uuid"] == uuid_ou_nome or c["nome"].lower() == uuid_ou_nome.lower()), None)
    if not cont:
        print(f"Continente '{uuid_ou_nome}' não encontrado no manifesto.")
        sys.exit(1)

    print(f"=== Gerando Cidades para o continente: {cont['nome']} ===")

    # 3. Extrair lista de biomas reais presentes no continente
    # "Oceano" pode aparecer aqui com percentual residual (pixels de fronteira entre
    # mask_continente>=nivel_mar e a classificação de bioma — achado nesta sessão, <1,2%
    # medido) mas não faz sentido como bioma DESEJADO de uma cidade (cidade é feature de
    # terra, por definição). Filtrado antes de virar opção pro prompt da IA / fallback.
    biomas_disponiveis = [b['nome'] for b in cont.get("biomas_predominantes", []) if b['nome'] != "Oceano"]
    if not biomas_disponiveis:
        # Fallback seguro
        biomas_disponiveis = ["Floresta Temperada", "Deserto", "Montanha Rochosa"]
    
    # 4. Chamar a IA delegando a responsabilidade para o Client Especializado — com retry e
    # fallback procedural (Fase 1.4, P1.4): antes uma resposta ruim da IA matava o processo
    # inteiro; agora `generate_cities_for_continent` garante `min_cids` sempre.
    min_cids = cfg_get(CARTOGRAPHER_CONFIG, "cidades_min_por_continente")
    max_cids = cfg_get(CARTOGRAPHER_CONFIG, "cidades_max_por_continente")
    retries = cfg_get(CARTOGRAPHER_CONFIG, "cidades_retry_ia")

    cidades = CityManagerAIClient.generate_cities_for_continent(
        nome_continente=cont['nome'],
        biomas_disponiveis=biomas_disponiveis,
        min_cidades=min_cids,
        max_cidades=max_cids,
        retries=retries,
    )

    print(f"IA fundou {len(cidades)} cidades! Alocando coordenadas geográficas baseadas na topografia...")

    # 5. Ler o mapa global para validar as posições
    if not os.path.exists(NPZ_PATH):
        print(f"Erro: Mapa base não encontrado em {NPZ_PATH}")
        sys.exit(1)

    data = np.load(NPZ_PATH)
    mapa = data["mapa"] # shape (H, W, 4) - 0: Altitude, 1: Temp, 2: Umid, 3: Bioma ID

    nivel_mar = CARTOGRAPHER_CONFIG["nivel_mar"]
    bbox = cont["bounding_box"]
    min_x, max_x = bbox["min_x"], bbox["max_x"]
    min_y, max_y = bbox["min_y"], bbox["max_y"]

    sub_alt = mapa[min_y:max_y + 1, min_x:max_x + 1, 0]
    sub_bioma = mapa[min_y:max_y + 1, min_x:max_x + 1, 3]
    is_terra = sub_alt > nivel_mar
    nivel_montanha = cfg_get(CARTOGRAPHER_CONFIG, "nivel_montanha")

    if not is_terra.any():
        print("Erro: Este continente não possui pixels de terra firme suficientes para abrigar cidades!")
        sys.exit(1)

    # 6. Alocar as cidades em posições compatíveis — pontuação de sítio (Fase 1.4, P1.4):
    # substitui `random.choice` por adjacência à costa + altitude baixa/plana + bioma
    # pedido, com distância mínima entre cidades como restrição dura.
    #
    # ⚠️ Achado nesta sessão: `{k.replace("_"," ").title(): v for k,v in BIOME_IDS.items()}`
    # dava "Mediterraneo" (sem acento, de "MEDITERRANEO" em climate.py) — mas o nome que
    # circula de verdade em `biomas_predominantes`/prompt da IA é "Mediterrâneo" (COM
    # acento, de `world_manager.py:biomas_nomes`). O `.get()` falhava em silêncio e toda
    # cidade com `bioma_desejado="Mediterrâneo"` caía no fallback (Floresta Temperada) sem
    # aviso nenhum. Mapa fixo, batendo com a grafia real usada no resto do pipeline — é o
    # mesmo ponto de manutenção "4 lugares" já avisado na Seção 1.2 do plano.
    biome_map_to_id = {"Oceano": 1, "Deserto": 2, "Mediterrâneo": 3, "Floresta Temperada": 4, "Montanha Rochosa": 5}
    distancia_minima = cfg_get(CARTOGRAPHER_CONFIG, "cidades_distancia_minima_px")

    cidades_ja_colocadas = []  # [(x_global, y_global), ...]
    for cid in cidades:
        bioma_str = cid.get("bioma_desejado", biomas_disponiveis[0] if biomas_disponiveis else "Floresta Temperada").title()
        bioma_id = biome_map_to_id.get(bioma_str, ClimateProcessor.BIOME_IDS.get("FLORESTA_TEMPERADA", 4))

        score = _pontuar_sitio(sub_alt, sub_bioma, is_terra, bioma_id, nivel_mar, nivel_montanha, CARTOGRAPHER_CONFIG)

        # Restrição dura: rejeita candidatos perto de uma cidade já colocada.
        for (ox, oy) in cidades_ja_colocadas:
            ys, xs = np.indices(score.shape)
            dist = np.sqrt((xs + min_x - ox) ** 2 + (ys + min_y - oy) ** 2)
            score = np.where(dist < distancia_minima, -np.inf, score)

        if not np.any(np.isfinite(score)):
            # Todo o continente já está "reservado" pela distância mínima — relaxa e usa
            # qualquer terra firme livre, mesmo perto de outra cidade (raro; continente
            # pequeno com muitas cidades).
            score = np.where(is_terra, 0.0, -np.inf)

        iy, ix = np.unravel_index(np.argmax(score), score.shape)
        x_global, y_global = int(ix + min_x), int(iy + min_y)
        cidades_ja_colocadas.append((x_global, y_global))

        cid["x_global"] = x_global
        cid["y_global"] = y_global

        print(f" -> 🏰 {cid['nome']} [{cid['tamanho']}, {cid['tipo']}] -> Fixada em ({x_global}, {y_global}) | Bioma de interesse: {bioma_str} (ID: {bioma_id}) | score={score[iy,ix]:.2f}")

    # 7. Persistir as cidades no Manifesto do Mundo
    cont["cidades"] = cidades

    # 8. Também podemos instanciar as tabelas/metadados no banco sqlite futuramente.
    # Por ora, deixar no manifesto permite ao UI carregar diretamente junto com os continentes.
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
    
    print("\n✅ Manifesto atualizado com sucesso! Cidades fundadas e registradas.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 generate_cities_metadata.py <uuid_ou_nome_continente>")
        sys.exit(1)
    
    gerar_metadados_cidades(sys.argv[1])
