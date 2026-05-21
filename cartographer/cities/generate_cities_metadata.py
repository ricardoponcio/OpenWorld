import os
import sys
import json
import random
import numpy as np

# Garante que a raiz do projeto esteja no sys.path
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.ai.city_manager_ai import CityManagerAIClient
from cartographer.math.climate import ClimateProcessor
from cartographer.config import CARTOGRAPHER_CONFIG

MANIFEST_PATH = "database/world_manifest.json"
NPZ_PATH = "database/mapa_composto.npz"

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
    biomas_disponiveis = [b['nome'] for b in cont.get("biomas_predominantes", [])]
    if not biomas_disponiveis:
        # Fallback seguro
        biomas_disponiveis = ["Floresta Temperada", "Deserto", "Montanha Rochosa"]
    
    # 4. Chamar a IA delegando a responsabilidade para o Client Especializado
    min_cids = CARTOGRAPHER_CONFIG.get("cidades_min_por_continente", 3)
    max_cids = CARTOGRAPHER_CONFIG.get("cidades_max_por_continente", 6)
    
    try:
        # Você pode passar model_name="llama3" etc aqui no futuro
        cidades = CityManagerAIClient.generate_cities_for_continent(
            nome_continente=cont['nome'],
            biomas_disponiveis=biomas_disponiveis,
            min_cidades=min_cids,
            max_cidades=max_cids
        )
    except Exception as e:
        print(f"Erro Crítico: {e}")
        sys.exit(1)

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

    # Encontrar todos os pixels acima do nível do mar dentro da Bounding Box do continente
    y_coords, x_coords = np.where(mapa[min_y:max_y+1, min_x:max_x+1, 0] > nivel_mar)
    
    # Transladar coordenadas locais do BBOX para as coordenadas globais
    y_coords += min_y
    x_coords += min_x

    terra_pixels = list(zip(x_coords, y_coords))
    if not terra_pixels:
        print("Erro: Este continente não possui pixels de terra firme suficientes para abrigar cidades!")
        sys.exit(1)

    # 6. Alocar as cidades em posições compatíveis
    
    # Criar um mapa reverso de Nome do Bioma -> ID
    # No climate.py os nomes estão em maiusculo com _, ex: "FLORESTA_TEMPERADA": 4
    biome_map_to_id = {k.replace("_", " ").title(): v for k, v in ClimateProcessor.BIOME_IDS.items()}
    
    for cid in cidades:
        # Identifica qual bioma a IA escolheu
        bioma_str = cid.get("bioma_desejado", biomas_disponiveis[0] if biomas_disponiveis else "Floresta Temperada").title()
        bioma_id = biome_map_to_id.get(bioma_str, ClimateProcessor.BIOME_IDS.get("FLORESTA_TEMPERADA", 4))
        
        # Filtrar o mapa (dentro da bbox) buscando altitude de terra firme E o ID do bioma escolhido
        y_coords_bioma, x_coords_bioma = np.where(
            (mapa[min_y:max_y+1, min_x:max_x+1, 0] > nivel_mar) & 
            (mapa[min_y:max_y+1, min_x:max_x+1, 3] == bioma_id)
        )
        
        y_coords_bioma += min_y
        x_coords_bioma += min_x
        
        pixels_validos = list(zip(x_coords_bioma, y_coords_bioma))
        
        # Se por algum motivo o bioma não existir na prática na caixa (apesar de estar na lista),
        # usamos a terra firme genérica como fallback
        if not pixels_validos:
            pixels_validos = terra_pixels.copy()
            
        escolhido = random.choice(pixels_validos)
        
        # Removemos dos dois conjuntos para evitar colisão
        if escolhido in terra_pixels:
            terra_pixels.remove(escolhido)
        
        cid["x_global"] = int(escolhido[0])
        cid["y_global"] = int(escolhido[1])
        
        print(f" -> 🏰 {cid['nome']} [{cid['tamanho']}, {cid['tipo']}] -> Fixada em ({cid['x_global']}, {cid['y_global']}) | Bioma de interesse: {bioma_str} (ID: {bioma_id})")

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
