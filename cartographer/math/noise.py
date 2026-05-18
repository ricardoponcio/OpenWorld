import numpy as np

def perlin_noise_2d_vectorized(x, y, seed=0):
    """
    Vetorização pura em NumPy do algoritmo Perlin Noise 2D clássico com interpolação quíntica.
    Extremamente rápida, Thread-Safe, livre de Segmentation Faults e totalmente portátil.
    """
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    
    # Coordenadas inteiras dos cantos da célula do grid
    x0 = np.floor(x).astype(np.int32)
    x1 = x0 + 1
    y0 = np.floor(y).astype(np.int32)
    y1 = y0 + 1
    
    # Distâncias relativas na célula [0, 1]
    sx = x - x0
    sy = y - y0
    
    # Interpolação quíntica (fade de Ken Perlin): 6t^5 - 15t^4 + 10t^3
    u = sx * sx * sx * (sx * (sx * 6.0 - 15.0) + 10.0)
    v = sy * sy * sy * (sy * (sy * 6.0 - 15.0) + 10.0)
    
    # Função hash determinística de alta performance para grade inteira 2D vetorizada
    def hash_2d(xi, yi):
        with np.errstate(over='ignore'):
            h = xi.astype(np.uint32) * np.uint32(7324447) + yi.astype(np.uint32) * np.uint32(9125369) + np.uint32(seed) * np.uint32(1378233)
            h = np.bitwise_xor(h, h >> 16)
            h = h * np.uint32(2246822519)
            h = np.bitwise_xor(h, h >> 13)
            h = h * np.uint32(3266489917)
            h = np.bitwise_xor(h, h >> 16)
        return h
    
    # Hashes determinísticos de cada um dos 4 cantos
    h00 = hash_2d(x0, y0)
    h10 = hash_2d(x1, y0)
    h01 = hash_2d(x0, y1)
    h11 = hash_2d(x1, y1)
    
    # Conversão dos hashes em ângulos determinísticos de [0, 2pi]
    scale_angle = 2.0 * np.pi / 4294967295.0
    theta00 = h00.astype(np.float32) * scale_angle
    theta10 = h10.astype(np.float32) * scale_angle
    theta01 = h01.astype(np.float32) * scale_angle
    theta11 = h11.astype(np.float32) * scale_angle
    
    # Produtos escalares entre os vetores gradientes unitários de cada canto e as distâncias
    g00 = np.cos(theta00) * sx + np.sin(theta00) * sy
    g10 = np.cos(theta10) * (sx - 1.0) + np.sin(theta10) * sy
    g01 = np.cos(theta01) * sx + np.sin(theta01) * (sy - 1.0)
    g11 = np.cos(theta11) * (sx - 1.0) + np.sin(theta11) * (sy - 1.0)
    
    # Interpolação bilinear suave das contribuições de cada canto
    val0 = g00 + u * (g10 - g00)
    val1 = g01 + u * (g11 - g01)
    
    return val0 + v * (val1 - val0)

class NoiseGenerator:
    """
    Gerador e manipulador de campos de ruído Perlin multi-frequência (fBm) puramente vetorizado.
    """
    @staticmethod
    def generate_noise_field(grid_x, grid_y, scale, octaves=4, seed=0, offset=0):
        """
        Gera uma grade 2D de ruído fractal Perlin (fBm) contínuo normalizado na faixa [0, 1].
        """
        grid_x = np.asarray(grid_x, dtype=np.float32)
        grid_y = np.asarray(grid_y, dtype=np.float32)
        scale = max(0.001, scale)
        
        total = np.zeros_like(grid_x, dtype=np.float32)
        amplitude = 1.0
        frequency = 1.0
        max_val = 0.0
        
        for i in range(octaves):
            val = perlin_noise_2d_vectorized(
                (grid_x / scale) * frequency, 
                (grid_y / scale) * frequency, 
                seed=seed + offset + i * 100
            )
            total += val * amplitude
            max_val += amplitude
            amplitude *= 0.5
            frequency *= 2.0
            
        limite = max_val * 0.707
        total_normalizado = np.clip(total / (limite if limite > 0 else 1.0), -1.0, 1.0)
        return (total_normalizado + 1.0) / 2.0

    @staticmethod
    def generate_tectonic_base(grid_x, grid_y, seed):
        """
        Gera a base geológica unindo macro-formas tectônicas e micro-detalhes de alta frequência.
        """
        ruido_macro = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=220.0, octaves=3, seed=seed)
        ruido_detalhe = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=60.0, octaves=4, seed=seed, offset=500)
        return 0.65 * ruido_macro + 0.35 * ruido_detalhe
