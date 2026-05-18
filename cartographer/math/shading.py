import numpy as np

class ShadingProcessor:
    """
    Processador de iluminação vetorial, relevo 3D normalizado e sombreamento cartográfico.
    """
    @staticmethod
    def calculate_northwest_hillshade(heightmap, escala_terreno=48.0, luz_dir=(-1.0, -1.0, 0.4)):
        """
        Calcula o sombreamento 3D clássico (hillshading) vindo de Noroeste.
        """
        dy, dx = np.gradient(heightmap)
        
        luz_x, luz_y, luz_z = luz_dir
        norm_luz = np.sqrt(luz_x**2 + luz_y**2 + luz_z**2)
        luz_x, luz_y, luz_z = luz_x / norm_luz, luz_y / norm_luz, luz_z / norm_luz
        
        # Normais da superfície baseadas nas inclinações
        nx = -dx * escala_terreno
        ny = -dy * escala_terreno
        nz = np.ones_like(heightmap)
        
        norm_n = np.sqrt(nx**2 + ny**2 + nz**2)
        nx, ny, nz = nx / norm_n, ny / norm_n, nz / norm_n
        
        # Produto escalar do vetor da luz com a normal da superfície
        sombreado = nx * luz_x + ny * luz_y + nz * luz_z
        sombreado = np.clip(sombreado, 0.0, 1.0)
        
        # Mapeia o sombreamento para o fator de iluminação (0.50 a 1.40)
        return 0.50 + (sombreado * 0.90)
