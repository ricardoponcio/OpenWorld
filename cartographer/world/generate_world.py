import numpy as np
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.world.world_manager import WorldManager

from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get


def gerar_mundo_composto():
    # 2. Instancia o Gerente
    # Tile size 256 é um padrão ouro para performance/detalhe
    # Usando uma semente inteira determinística
    manager = WorldManager(tile_size=256, seed=1337, config=CARTOGRAPHER_CONFIG)

    print("=== Gerando Região Composta ===")

    # 3. Define a área da grade de tiles a partir do mesmo config que o
    # WorldManager usa para planejar os continentes (config["cartografia"]
    # ["mundo_tiles_por_lado"]) — antes esse "3x3" era um literal independente
    # aqui, podendo divergir do usado internamente pelo WorldManager.
    tiles_por_lado = cfg_get(CARTOGRAPHER_CONFIG, "mundo_tiles_por_lado")
    mapa_composto = manager.get_full_map_region(
        tx_start=0,
        ty_start=0,
        width_tiles=tiles_por_lado,
        height_tiles=tiles_por_lado
    )

    # 4. Salva o resultado final
    np.savez_compressed("database/mapa_composto.npz", mapa=mapa_composto)
    
    # 5. Gera e salva o manifesto de continentes
    manager.save_world_manifest(mapa_composto, "database/world_manifest.json")
    
    print(f"Mundo composto gerado! Tamanho final: {mapa_composto.shape}")
    print("O arquivo 'mapa_composto.npz' e o 'world_manifest.json' estão prontos para uso.")

if __name__ == "__main__":
    gerar_mundo_composto()
