import numpy as np

class ColoringProcessor:
    """
    Processador de preenchimento e interpolação de paletas altitudinais e renderização marinha.
    """
    CORES_BASE = {
        2: (224, 192, 114),  # DESERTO
        3: (114, 166, 102),  # MEDITERRANEO
        4: (43, 94, 60),     # FLORESTA_TEMPERADA
        5: (110, 110, 110)   # MONTANHA_ROCHOSA
    }

    @staticmethod
    def render_ocean(heightmap, nivel_mar=0.35):
        """
        Gera um sombreamento dinâmico e brilhante de recifes e mar profundo usando potência 6.
        """
        alt_norm = np.clip(heightmap / nivel_mar, 0.0, 1.0)
        alt_shading = np.power(alt_norm, 6.0)
        
        r_chan = 10 * (1.0 - alt_shading) + 50 * alt_shading
        g_chan = 36 * (1.0 - alt_shading) + 150 * alt_shading
        b_chan = 70 * (1.0 - alt_shading) + 190 * alt_shading
        
        return np.stack([r_chan, g_chan, b_chan], axis=-1).astype(np.uint8)

    @staticmethod
    def interpolate_land_biome(bioma_id, alt_terra_norm):
        """
        Faz a interpolação de cor baseada no bioma e na altitude da terra firme (Verde -> Rocha -> Neve).
        """
        if bioma_id == 4:  # Floresta Temperada
            r_c = np.where(alt_terra_norm < 0.65, 43 * (1.0 - alt_terra_norm/0.65) + 110 * (alt_terra_norm/0.65), 110 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            g_c = np.where(alt_terra_norm < 0.65, 94 * (1.0 - alt_terra_norm/0.65) + 105 * (alt_terra_norm/0.65), 105 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            b_c = np.where(alt_terra_norm < 0.65, 60 * (1.0 - alt_terra_norm/0.65) + 95 * (alt_terra_norm/0.65), 95 * (1.0 - (alt_terra_norm-0.65)/0.35) + 250 * ((alt_terra_norm-0.65)/0.35))
        elif bioma_id == 3:  # Mediterrâneo
            r_c = np.where(alt_terra_norm < 0.65, 114 * (1.0 - alt_terra_norm/0.65) + 115 * (alt_terra_norm/0.65), 115 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            g_c = np.where(alt_terra_norm < 0.65, 166 * (1.0 - alt_terra_norm/0.65) + 110 * (alt_terra_norm/0.65), 110 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            b_c = np.where(alt_terra_norm < 0.65, 102 * (1.0 - alt_terra_norm/0.65) + 100 * (alt_terra_norm/0.65), 100 * (1.0 - (alt_terra_norm-0.65)/0.35) + 250 * ((alt_terra_norm-0.65)/0.35))
        elif bioma_id == 2:  # Deserto
            r_c = np.where(alt_terra_norm < 0.65, 224 * (1.0 - alt_terra_norm/0.65) + 140 * (alt_terra_norm/0.65), 140 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            g_c = np.where(alt_terra_norm < 0.65, 192 * (1.0 - alt_terra_norm/0.65) + 100 * (alt_terra_norm/0.65), 100 * (1.0 - (alt_terra_norm-0.65)/0.35) + 245 * ((alt_terra_norm-0.65)/0.35))
            b_c = np.where(alt_terra_norm < 0.65, 114 * (1.0 - alt_terra_norm/0.65) + 85 * (alt_terra_norm/0.65), 85 * (1.0 - (alt_terra_norm-0.65)/0.35) + 250 * ((alt_terra_norm-0.65)/0.35))
        elif bioma_id == 5:  # Montanha Rochosa
            r_c = 110 * (1.0 - alt_terra_norm) + 245 * alt_terra_norm
            g_c = 110 * (1.0 - alt_terra_norm) + 245 * alt_terra_norm
            b_c = 110 * (1.0 - alt_terra_norm) + 250 * alt_terra_norm
        else:
            r_c = np.zeros_like(alt_terra_norm)
            g_c = np.zeros_like(alt_terra_norm)
            b_c = np.zeros_like(alt_terra_norm)
            
        return r_c.astype(np.uint8), g_c.astype(np.uint8), b_c.astype(np.uint8)
