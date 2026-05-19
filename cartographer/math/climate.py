import numpy as np
from cartographer.math.noise import NoiseGenerator

class ClimateProcessor:
    """
    Processador de sistemas climatológicos, gradiente de latitude/altitude e
    classificação de biomas terrestres.
    """
    BIOME_IDS = {
        "OCEANO": 1, 
        "DESERTO": 2, 
        "MEDITERRANEO": 3,
        "FLORESTA_TEMPERADA": 4, 
        "MONTANHA_ROCHOSA": 5
    }

    # ------------------------------------------------------------------
    # Constantes Climatológicas Parametrizadas e Documentadas
    # ------------------------------------------------------------------
    DEFAULT_NIVEL_MAR = 0.35            # Nível padrão do mar
    DEFAULT_NIVEL_MONTANHA = 0.75       # Nível mínimo absoluto para montanhas rochosas
    
    DAMPING_TERMICO = 0.4               # Fator de resfriamento da temperatura baseado na altitude
    UMIDADE_OCEANO = 0.8                # Nível de umidade base do oceano
    UMIDADE_TERRA_BASE = 0.4            # Nível de umidade base da terra firme
    
    DITHERING_SCALE = 350.0             # Escala do ruído de dithering para fronteiras de biomas
    DITHERING_TEMP_AMP = 0.10           # Amplitude de variação climática de temperatura
    DITHERING_UMID_AMP = 0.10           # Amplitude de variação climática de umidade
    
    # Limiares de classificação de biomas
    LIMIAR_TEMP_DESERTO = 0.6           # Temperatura mínima para o Deserto
    LIMIAR_UMID_DESERTO = 0.5           # Umidade máxima para o Deserto
    LIMIAR_TEMP_MEDITERRANEO = 0.4      # Temperatura mínima para o Mediterrâneo
    LIMIAR_UMID_MEDITERRANEO = 0.5      # Umidade mínima para o Mediterrâneo

    @staticmethod
    def calculate_temperature(grid_y, heightmap, mod_calor, map_height=768.0):
        """
        Calcula a temperatura global baseada na latitude, altitude (damping térmico) e modificador IA.
        """
        latitude_factor = 1.0 - (grid_y / map_height)
        latitude_factor = np.clip(latitude_factor, 0.0, 1.0)
        
        temp_base = latitude_factor - (heightmap * ClimateProcessor.DAMPING_TERMICO) + mod_calor
        return np.clip(temp_base, 0.0, 1.0)

    @staticmethod
    def calculate_humidity(heightmap, mod_umidade, nivel_mar=None):
        """
        Calcula o índice de umidade baseado na presença de água e modificador IA regional.
        """
        if nivel_mar is None:
            nivel_mar = ClimateProcessor.DEFAULT_NIVEL_MAR
            
        umid_base = np.where(
            heightmap < nivel_mar, 
            ClimateProcessor.UMIDADE_OCEANO, 
            ClimateProcessor.UMIDADE_TERRA_BASE + mod_umidade
        )
        return np.clip(umid_base, 0.0, 1.0)

    @staticmethod
    def classify_biomes(heightmap, temperature, humidity, nivel_mar=None, nivel_montanha=None, grid_x=None, grid_y=None, seed=0):
        """
        Classifica cada pixel em seu respectivo bioma usando regras climáticas.
        """
        if nivel_mar is None:
            nivel_mar = ClimateProcessor.DEFAULT_NIVEL_MAR
        if nivel_montanha is None:
            nivel_montanha = ClimateProcessor.DEFAULT_NIVEL_MONTANHA
            
        biomas = np.zeros_like(heightmap)
        
        # Cópias para evitar mutar as matrizes de entrada originais
        temp_proc = temperature.copy()
        umid_proc = humidity.copy()
        
        if grid_x is not None and grid_y is not None:
            # Como grid_x e grid_y estão sempre no espaço de coordenadas globais [0, 768],
            # usamos uma escala de macro-onda de 350.0 com 1 única oitava (ruído puro e perfeitamente liso)
            # para garantir curvas geográficas suaves e elegantes sem nenhuma granulação ("sal e pimenta") ou manchas.
            ruido_fronteira_temp = NoiseGenerator.generate_noise_field(
                grid_x, grid_y, 
                scale=ClimateProcessor.DITHERING_SCALE, 
                octaves=1, seed=seed, offset=3333
            )
            ruido_fronteira_umid = NoiseGenerator.generate_noise_field(
                grid_x, grid_y, 
                scale=ClimateProcessor.DITHERING_SCALE, 
                octaves=1, seed=seed, offset=4444
            )
            
            # Ajustamos a perturbação climática
            temp_proc = temp_proc + (ruido_fronteira_temp - 0.5) * ClimateProcessor.DITHERING_TEMP_AMP
            umid_proc = umid_proc + (ruido_fronteira_umid - 0.5) * ClimateProcessor.DITHERING_UMID_AMP
            
        # Oceano e Montanha de altíssima altitude são absolutos
        biomas[heightmap < nivel_mar] = ClimateProcessor.BIOME_IDS["OCEANO"]
        biomas[heightmap > nivel_montanha] = ClimateProcessor.BIOME_IDS["MONTANHA_ROCHOSA"]
        
        # Máscaras de terra firme intermediária
        terra_firme = (heightmap >= nivel_mar) & (heightmap <= nivel_montanha)
        
        # Classificação por temperatura e umidade usando limiares documentados
        is_deserto = (temp_proc > ClimateProcessor.LIMIAR_TEMP_DESERTO) & (umid_proc < ClimateProcessor.LIMIAR_UMID_DESERTO)
        is_mediterraneo = (temp_proc > ClimateProcessor.LIMIAR_TEMP_MEDITERRANEO) & (umid_proc >= ClimateProcessor.LIMIAR_UMID_MEDITERRANEO)
        
        biomas[terra_firme & is_deserto] = ClimateProcessor.BIOME_IDS["DESERTO"]
        biomas[terra_firme & is_mediterraneo] = ClimateProcessor.BIOME_IDS["MEDITERRANEO"]
        biomas[terra_firme & (biomas == 0)] = ClimateProcessor.BIOME_IDS["FLORESTA_TEMPERADA"]
        
        return biomas
