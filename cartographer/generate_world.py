import numpy as np
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.append(raiz)

from cartographer.world_manager import WorldManager

def gerar_mundo_composto():
    # 1. Configurações base
    CONFIG = {
        "frequencia": 200.0,
        "oitavas": 8,
        "persistencia": 0.5,
        "lacunariedade": 2.1,
        "nivel_mar": 0.35,
        "nivel_montanha": 0.8,
        
        # Parâmetros customizados para o ruído do relevo marinho (bancos de areia)
        "ruido_mar_escala": 80.0,     # Frequência horizontal do ruído (escala menor = mais detalhes de ilhotas/fossas)
        "ruido_mar_oitavas": 3,       # Complexidade do relevo do mar
        "ruido_mar_amplitude": 0.14,  # Amplitude do relevo do mar (0.14 garante transições suaves de praia)
        
        # Parâmetros adicionais expostos para controle total da cartografia
        "ruido_macro_escala": 220.0,  # Escala horizontal do relevo base dos continentes (tile_cartographer.py)
        "ruido_macro_oitavas": 3,     # Detalhamento tectônico do relevo base (tile_cartographer.py)
        "ruido_costa_escala": 60.0,   # Escala horizontal das reentrâncias das praias e costões (tile_cartographer.py)
        "ruido_costa_oitavas": 4,     # Rugosidade/irregularidade local das praias e enseadas (tile_cartographer.py)

        # Escala geográfica real
        "escala_pixel_area_km2": 250, # Área real representada por pixel de terra firme (world_manager.py)
        
        # Constantes climáticas (climate.py)
        "clima_damping_termico": 0.4,     # Resfriamento da temperatura por altitude
        "clima_umidade_oceano": 0.8,      # Umidade base do oceano
        "clima_umidade_terra_base": 0.4,  # Umidade base da terra firme
        
        # Ruído de dithering para transição de biomas (climate.py)
        "clima_dithering_escala": 350.0,
        "clima_dithering_temp_amp": 0.10,
        "clima_dithering_umid_amp": 0.10,
        
        # Limiares de classificação de biomas (climate.py)
        "limiar_temp_deserto": 0.6,
        "limiar_umid_deserto": 0.5,
        "limiar_temp_mediterraneo": 0.4,
        "limiar_umid_mediterraneo": 0.5
    }
    
    # 2. Instancia o Gerente
    # Tile size 256 é um padrão ouro para performance/detalhe
    # Usando uma semente inteira determinística
    manager = WorldManager(tile_size=256, seed=1337, config=CONFIG)

    print("=== Gerando Região Composta ===")
    
    # 3. Define a área (Começar no tile 0,0 e gerar uma grade de 3x3 tiles)
    # Isso gera os tiles (0,0), (1,0), (2,0), (0,1)... até (2,2)
    mapa_composto = manager.get_full_map_region(
        tx_start=0, 
        ty_start=0, 
        width_tiles=3, 
        height_tiles=3
    )

    # 4. Salva o resultado final
    np.savez_compressed("database/mapa_composto.npz", mapa=mapa_composto)
    
    # 5. Gera e salva o manifesto de continentes
    manager.save_world_manifest(mapa_composto, "database/world_manifest.json")
    
    print(f"Mundo composto gerado! Tamanho final: {mapa_composto.shape}")
    print("O arquivo 'mapa_composto.npz' e o 'world_manifest.json' estão prontos para uso.")

if __name__ == "__main__":
    gerar_mundo_composto()
