import numpy as np
import os
from cartographer import Cartographer 

def run_simulation_test():
    # --- PAINEL DE CONTROLE DO MESTRE ---
    CONFIG_MUNDO = {
        "frequencia": 200.0,      # MENOR = mais continentes/ilhas | MAIOR = mais "zoom"
        "oitavas": 8,             # Detalhe (4 a 10). Mais oitavas = terreno mais acidentado
        "persistencia": 0.5,      # Suavidade das oitavas
        "lacunariedade": 2.1,     # Espaçamento dos detalhes
        "nivel_mar": 0.35,        # 0.0 a 1.0. Aumente para ter mais água no mapa
        "nivel_montanha": 0.82    # Aumente para ter menos montanhas rochosas
    }
    
    TAMANHO_MAPA = 1000
    SEMENTE_MUNDO = 999 
    ARQUIVO_SAIDA = "database/mapa_mundo.npz"
    # ------------------------------------

    print("=== INICIANDO GERAÇÃO PARAMETRIZADA ===")
    cartografo = Cartographer(size=TAMANHO_MAPA, seed=SEMENTE_MUNDO, config=CONFIG_MUNDO)
    cartografo.build_world()
    cartografo.export_arquivao(ARQUIVO_SAIDA)

    # Validação rápida
    dados = np.load(ARQUIVO_SAIDA)["mapa"]
    print(f"Formato do mapa: {dados.shape}")
    print(f"Altitude Média: {np.mean(dados[:,:,0]):.2f}")

if __name__ == "__main__":
    run_simulation_test()