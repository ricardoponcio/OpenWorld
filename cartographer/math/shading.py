import numpy as np
from config import cfg_get


class ShadingProcessor:
    """
    Processador de iluminação vetorial, relevo 3D normalizado e sombreamento cartográfico.
    """

    @staticmethod
    def calculate_northwest_hillshade(heightmap, config, escala_terreno=None):
        """
        Calcula o sombreamento 3D clássico (hillshading) vindo de Noroeste com alto contraste.
        Garante que áreas 100% planas mantenham iluminação neutra (1.0), encostas viradas
        para a luz ganhem brilho (>1.0) e encostas opostas ganhem sombras profundas (<1.0).

        `escala_terreno` pode ser passado explicitamente pelo chamador quando precisa ser
        proporcional à resolução da imagem (ex.: `web/helpers.py` escala para 3000px de
        zoom); se omitido, usa o valor base de `config["cartografia"]["shading_escala_terreno"]`.
        """
        if escala_terreno is None:
            escala_terreno = cfg_get(config, "shading_escala_terreno")
        luz_dir = cfg_get(config, "shading_luz_direcao")
        contraste = cfg_get(config, "shading_contraste")
        brilho_min = cfg_get(config, "shading_brilho_min")
        brilho_max = cfg_get(config, "shading_brilho_max")

        dy, dx = np.gradient(heightmap)

        # Normais da superfície baseadas nas inclinações
        nx = -dx * escala_terreno
        ny = -dy * escala_terreno
        nz = np.ones_like(heightmap)

        norm_n = np.sqrt(nx**2 + ny**2 + nz**2)
        nx, ny, nz = nx / norm_n, ny / norm_n, nz / norm_n

        # Vetor de luz normalizado
        luz_x, luz_y, luz_z = luz_dir
        norm_luz = np.sqrt(luz_x**2 + luz_y**2 + luz_z**2)
        luz_x, luz_y, luz_z = luz_x / norm_luz, luz_y / norm_luz, luz_z / norm_luz

        # Produto escalar do vetor da luz com a normal da superfície
        dp = nx * luz_x + ny * luz_y + nz * luz_z

        # Mapeia para iluminação relativa: encostas planas têm fator_luz = 1.0.
        fator_luz = 1.0 + (dp - luz_z) * contraste

        return np.clip(fator_luz, brilho_min, brilho_max)
