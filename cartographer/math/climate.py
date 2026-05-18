import numpy as np

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

    @staticmethod
    def calculate_temperature(grid_y, heightmap, mod_calor, map_height=768.0):
        """
        Calcula a temperatura global baseada na latitude, altitude (damping térmico) e modificador IA.
        """
        latitude_factor = 1.0 - (grid_y / map_height)
        latitude_factor = np.clip(latitude_factor, 0.0, 1.0)
        
        temp_base = latitude_factor - (heightmap * 0.4) + mod_calor
        return np.clip(temp_base, 0.0, 1.0)

    @staticmethod
    def calculate_humidity(heightmap, mod_umidade, nivel_mar=0.35):
        """
        Calcula o índice de umidade baseado na presença de água e modificador IA regional.
        """
        umid_base = np.where(heightmap < nivel_mar, 0.8, 0.4 + mod_umidade)
        return np.clip(umid_base, 0.0, 1.0)

    @staticmethod
    def classify_biomes(heightmap, temperature, humidity, nivel_mar=0.35, nivel_montanha=0.75):
        """
        Classifica cada pixel em seu respectivo bioma usando regras climáticas.
        """
        biomas = np.zeros_like(heightmap)
        
        # Oceano e Montanha de altíssima altitude são absolutos
        biomas[heightmap < nivel_mar] = ClimateProcessor.BIOME_IDS["OCEANO"]
        biomas[heightmap > nivel_montanha] = ClimateProcessor.BIOME_IDS["MONTANHA_ROCHOSA"]
        
        # Máscaras de terra firme intermediária
        terra_firme = (heightmap >= nivel_mar) & (heightmap <= nivel_montanha)
        
        # Classificação por temperatura e umidade
        biomas[terra_firme & (temperature > 0.6) & (humidity < 0.5)] = ClimateProcessor.BIOME_IDS["DESERTO"]
        biomas[terra_firme & (temperature > 0.4) & (humidity >= 0.5)] = ClimateProcessor.BIOME_IDS["MEDITERRANEO"]
        biomas[terra_firme & (biomas == 0)] = ClimateProcessor.BIOME_IDS["FLORESTA_TEMPERADA"]
        
        return biomas
