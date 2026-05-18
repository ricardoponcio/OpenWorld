import numpy as np
from noise import pnoise2

class NoiseGenerator:
    """
    Gerador e manipulador de campos de ruído Perlin multi-frequência.
    """
    @staticmethod
    def generate_noise_field(grid_x, grid_y, scale, octaves=4, seed=0, offset=0):
        """
        Gera uma grade 2D de ruído Perlin contínuo normalizado de [0, 1].
        """
        v_pnoise2 = np.vectorize(lambda x, y: pnoise2(
            x / scale, 
            y / scale, 
            octaves=octaves, 
            base=(seed + offset) % 50000
        ))
        ruido = v_pnoise2(grid_x, grid_y)
        return (ruido + 1.0) / 2.0

    @staticmethod
    def generate_tectonic_base(grid_x, grid_y, seed):
        """
        Gera a base geológica unindo macro-formas tectônicas e micro-detalhes de alta frequência.
        """
        ruido_macro = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=220.0, octaves=3, seed=seed)
        ruido_detalhe = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=60.0, octaves=4, seed=seed, offset=500)
        return 0.65 * ruido_macro + 0.35 * ruido_detalhe
