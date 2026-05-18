import numpy as np
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.append(raiz)

from world_manager import WorldManager

def gerar_mundo_composto():
    # 1. Configurações base (Mesmas do seu teste anterior)
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
        "ruido_mar_amplitude": 0.14    # Amplitude do relevo do mar (0.14 garante transições suaves de praia)
    }
    
    # 2. Instancia o Gerente
    # Tile size 256 é um padrão ouro para performance/detalhe
    # Usando uma semente inteira determinística
    manager = WorldManager(tile_size=256, seed=1337, config=CONFIG)

    print("=== Gerando Região Composta ===")
    
    # 3. Define a área (Ex: Começar no tile 0,0 e gerar uma grade de 3x3 tiles)
    # Isso vai gerar os tiles (0,0), (1,0), (2,0), (0,1)... até (2,2)
    mapa_composto = manager.get_full_map_region(
        tx_start=0, 
        ty_start=0, 
        width_tiles=3, 
        height_tiles=3
    )

    # 4. Salva o resultado final (O "Arquivão" de sempre)
    # O formato .npz continua o mesmo, seu simulador nem percebe que foi feito em pedaços
    np.savez_compressed("database/mapa_composto.npz", mapa=mapa_composto)
    
    print(f"Mundo composto gerado! Tamanho final: {mapa_composto.shape}")
    print("O arquivo 'mapa_composto.npz' está pronto para o dashboard.")

if __name__ == "__main__":
    gerar_mundo_composto()