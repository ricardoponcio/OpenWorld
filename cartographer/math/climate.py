import numpy as np
from cartographer.math.noise import NoiseGenerator
from config import cfg_get

class ClimateProcessor:
    """
    Processador de sistemas climatológicos, gradiente de latitude/altitude e
    classificação de biomas terrestres.

    Todos os parâmetros climáticos vêm de `config` (o bloco config["cartografia"]),
    lidos via `cfg_get` — sem constantes de classe duplicadas. Ver docs/ROADMAP.md
    (Frente 1) e docs/AUDITORIA_HARDCODE.md.
    """
    BIOME_IDS = {
        "OCEANO": 1,
        "DESERTO": 2,
        "MEDITERRANEO": 3,
        "FLORESTA_TEMPERADA": 4,
        "MONTANHA_ROCHOSA": 5
    }

    @staticmethod
    def calculate_temperature(grid_y, heightmap, mod_calor, map_height, config):
        """
        Calcula a temperatura global baseada na latitude, altitude (damping térmico) e modificador IA.

        `map_height` é a dimensão vertical real do mundo composto (calculada pelo
        chamador, não um parâmetro de cartografia) — antes era um literal 768.0 fixo.
        """
        damping_termico = cfg_get(config, "clima_damping_termico")

        latitude_factor = 1.0 - (grid_y / map_height)
        latitude_factor = np.clip(latitude_factor, 0.0, 1.0)

        temp_base = latitude_factor - (heightmap * damping_termico) + mod_calor
        return np.clip(temp_base, 0.0, 1.0)

    @staticmethod
    def calculate_humidity(heightmap, mod_umidade, config, nivel_mar=None):
        """
        Calcula o índice de umidade baseado na presença de água e modificador IA regional.
        """
        if nivel_mar is None:
            nivel_mar = cfg_get(config, "nivel_mar")
        umidade_oceano = cfg_get(config, "clima_umidade_oceano")
        umidade_terra_base = cfg_get(config, "clima_umidade_terra_base")

        umid_base = np.where(
            heightmap < nivel_mar,
            umidade_oceano,
            umidade_terra_base + mod_umidade
        )
        return np.clip(umid_base, 0.0, 1.0)

    @staticmethod
    def classify_biomes(heightmap, temperature, humidity, config, nivel_mar=None, nivel_montanha=None,
                         grid_x=None, grid_y=None, seed=0):
        """
        Classifica cada pixel em seu respectivo bioma usando regras climáticas.
        """
        if nivel_mar is None:
            nivel_mar = cfg_get(config, "nivel_mar")
        if nivel_montanha is None:
            nivel_montanha = cfg_get(config, "nivel_montanha")

        limiar_temp_deserto = cfg_get(config, "limiar_temp_deserto")
        limiar_umid_deserto = cfg_get(config, "limiar_umid_deserto")
        limiar_temp_mediterraneo = cfg_get(config, "limiar_temp_mediterraneo")
        limiar_umid_mediterraneo = cfg_get(config, "limiar_umid_mediterraneo")

        biomas = np.zeros_like(heightmap)

        # Cópias para evitar mutar as matrizes de entrada originais
        temp_proc = temperature.copy()
        umid_proc = humidity.copy()

        if grid_x is not None and grid_y is not None:
            dithering_escala = cfg_get(config, "clima_dithering_escala")
            dithering_temp_amp = cfg_get(config, "clima_dithering_temp_amp")
            dithering_umid_amp = cfg_get(config, "clima_dithering_umid_amp")

            # Como grid_x e grid_y estão sempre no espaço de coordenadas globais do mundo,
            # usamos uma escala de macro-onda com 1 única oitava (ruído puro e perfeitamente
            # liso) para garantir curvas geográficas suaves sem granulação ("sal e pimenta").
            ruido_fronteira_temp = NoiseGenerator.generate_noise_field(
                grid_x, grid_y,
                scale=dithering_escala,
                octaves=1, seed=seed, offset=3333
            )
            ruido_fronteira_umid = NoiseGenerator.generate_noise_field(
                grid_x, grid_y,
                scale=dithering_escala,
                octaves=1, seed=seed, offset=4444
            )

            # Ajustamos a perturbação climática
            temp_proc = temp_proc + (ruido_fronteira_temp - 0.5) * dithering_temp_amp
            umid_proc = umid_proc + (ruido_fronteira_umid - 0.5) * dithering_umid_amp

        # Oceano e Montanha de altíssima altitude são absolutos
        biomas[heightmap < nivel_mar] = ClimateProcessor.BIOME_IDS["OCEANO"]
        biomas[heightmap > nivel_montanha] = ClimateProcessor.BIOME_IDS["MONTANHA_ROCHOSA"]

        # Máscaras de terra firme intermediária
        terra_firme = (heightmap >= nivel_mar) & (heightmap <= nivel_montanha)

        # Classificação por temperatura e umidade usando limiares de config
        is_deserto = (temp_proc > limiar_temp_deserto) & (umid_proc < limiar_umid_deserto)
        is_mediterraneo = (temp_proc > limiar_temp_mediterraneo) & (umid_proc >= limiar_umid_mediterraneo)

        biomas[terra_firme & is_deserto] = ClimateProcessor.BIOME_IDS["DESERTO"]
        biomas[terra_firme & is_mediterraneo] = ClimateProcessor.BIOME_IDS["MEDITERRANEO"]
        biomas[terra_firme & (biomas == 0)] = ClimateProcessor.BIOME_IDS["FLORESTA_TEMPERADA"]

        return biomas
