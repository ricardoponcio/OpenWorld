import os
import sys
import json
import zlib
import random
import numpy as np
try:
    from scipy.ndimage import distance_transform_edt
except ImportError:
    distance_transform_edt = None

# Garante que a raiz do projeto esteja no sys.path
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.ai.city_manager_ai import CityManagerAIClient, nome_procedural_de_cidade
from cartographer.math.climate import Bioma
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

MANIFEST_PATH = "database/world_manifest.json"
NPZ_PATH = "database/mapa_composto.npz"


def _garantir_nomes_unicos(cidades: list, manifest: dict, cont: dict) -> None:
    """G05 (docs/PLANO_MUNDO_CRIVEL.md, Bloco G): o nome da cidade é a chave que
    tudo a jusante usa — o slug do arquivo GeoJSON e os ids de lote/local
    (armadilha 3) — duas cidades com o mesmo nome compartilham namespace, e uma
    delas fica com ZERO locais pra sempre (achado real: duas "Cidade dos Ventos"
    no mesmo manifesto). Re-sorteia qualquer colisão contra as cidades JÁ no
    manifesto (outros continentes, cada um gerado num processo anterior deste
    mesmo `reset_cartography.sh`) e contra as deste MESMO continente — sempre
    determinístico (`zlib.crc32`, nunca `hash()`, D2 doc 1)."""
    nomes_em_uso = {
        c["nome"] for outro in manifest.get("continentes", []) if outro is not cont
        for c in outro.get("cidades", [])
    }
    for indice, cidade in enumerate(cidades):
        tentativa = 0
        while cidade["nome"] in nomes_em_uso:
            seed = zlib.crc32(f"{cont['nome']}_{indice}_{tentativa}".encode("utf-8"))
            cidade["nome"] = nome_procedural_de_cidade(random.Random(seed))
            tentativa += 1
        nomes_em_uso.add(cidade["nome"])


def _pontuar_sitio(sub_alt, sub_bioma, is_terra, bioma_id, nivel_mar, nivel_montanha, cfg, tipo=None):
    """
    D4 do DIAGNOSTICO_V3 (2026-09-11): reescrita da pontuação de sítio (era Fase 1.4/P1.4).
    Antes, score_costa (exp(-dist/escala)) e score_altitude (1 - clip((alt-nivel_mar)/faixa))
    eram MONÓTONOS e maximizavam os dois no mesmo lugar: o primeiro pixel de terra, colado
    na água. Com peso_costa=0.4 + peso_altitude=0.3, 70% da pontuação empurrava toda cidade
    pra beira d'água — foi assim que as 15 cidades do mundo medido saíram no percentil
    0,00-0,07% de altitude (Seção 6.2 do diagnóstico). Agora as duas curvas têm um PICO
    interno (perto demais da água é alagado; longe demais não tem acesso a água), e um
    descarte DURO remove candidatos colados na água antes mesmo de pontuar — não é possível
    pontuação boa o bastante pra escapar dessa restrição.
    """
    if distance_transform_edt is not None:
        # Distância (em px) até o pixel de água/fora-da-bbox mais próximo.
        dist_costa = distance_transform_edt(is_terra)
    else:
        dist_costa = np.full(is_terra.shape, 10.0, dtype=np.float32)  # fallback neutro sem scipy

    perfil = cfg_get(cfg, "cidades_perfil_por_tipo").get(tipo or "", {})

    ideal = perfil.get("distancia_costa_ideal_px", cfg_get(cfg, "cidades_distancia_costa_ideal_px"))
    largura = perfil.get("distancia_costa_largura_px", cfg_get(cfg, "cidades_distancia_costa_largura_px"))
    score_costa = np.exp(-((dist_costa - ideal) ** 2) / (2.0 * max(1e-6, largura) ** 2))

    margem = cfg_get(cfg, "cidades_altitude_margem_mar")
    if perfil.get("prefere_altitude_alta", False):
        # D4 Passo 4: cidade mineira prefere altitude alta, não baixa — o alvo fica a uma
        # fração do caminho entre o nível do mar e o nível de montanha.
        fracao = perfil.get("altitude_alvo_fracao", 0.5)
        alt_ideal = nivel_mar + (nivel_montanha - nivel_mar) * fracao
    else:
        # D4 Passo 2: terreno baixo é bom; terreno NO nível do mar é pântano. O alvo fica
        # ligeiramente acima do nível do mar, nunca em cima dele.
        alt_ideal = nivel_mar + margem
    score_altitude = 1.0 - np.clip(np.abs(sub_alt - alt_ideal) / max(1e-6, nivel_montanha - alt_ideal), 0.0, 1.0)

    score_bioma = np.where(sub_bioma == bioma_id, 1.0, 0.3)

    peso_costa = cfg_get(cfg, "cidades_peso_costa")
    peso_altitude = cfg_get(cfg, "cidades_peso_altitude")
    peso_bioma = cfg_get(cfg, "cidades_peso_bioma")

    score = peso_costa * score_costa + peso_altitude * score_altitude + peso_bioma * score_bioma

    # D4 Passo 3: restrição DURA. Um pixel cuja vizinhança já é metade água nunca é sítio
    # de cidade, por melhor que a pontuação dele seja.
    dist_min = cfg_get(cfg, "cidades_distancia_costa_minima_px")
    score = np.where(is_terra & (dist_costa >= dist_min), score, -np.inf)
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
    # ⚠️ Achado nesta sessão (histórico): `{k.replace("_"," ").title(): v for k,v in
    # BIOME_IDS.items()}` dava "Mediterraneo" (sem acento, de "MEDITERRANEO" em
    # climate.py) — mas o nome que circula de verdade em `biomas_predominantes`/prompt
    # da IA é "Mediterrâneo" (COM acento). O `.get()` falhava em silêncio e toda cidade
    # com `bioma_desejado="Mediterrâneo"` caía no fallback (Floresta Temperada) sem
    # aviso nenhum. R-B06: o mapa nome->id agora vem do enum `Bioma` (fonte única do
    # rótulo, com acento e tudo) — não há mais um segundo dicionário pra divergir.
    biome_map_to_id = {b.rotulo: b.id_numerico for b in Bioma}
    distancia_minima = cfg_get(CARTOGRAPHER_CONFIG, "cidades_distancia_minima_px")

    cidades_ja_colocadas = []  # [(x_global, y_global), ...]
    for cid in cidades:
        bioma_str = cid.get("bioma_desejado", biomas_disponiveis[0] if biomas_disponiveis else "Floresta Temperada").title()
        bioma_id = biome_map_to_id.get(bioma_str, Bioma.FLORESTA_TEMPERADA.id_numerico)

        score = _pontuar_sitio(sub_alt, sub_bioma, is_terra, bioma_id, nivel_mar, nivel_montanha, CARTOGRAPHER_CONFIG, tipo=(cid.get("tipo") or "").lower())

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

    # 7. G05: nome de cidade é único antes de persistir — nunca depois.
    _garantir_nomes_unicos(cidades, manifest, cont)
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
