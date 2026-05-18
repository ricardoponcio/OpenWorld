import numpy as np

class TectonicsProcessor:
    """
    Processador geográfico responsável pelas placas tectônicas, perfis geológicos e
    modulações de relevo continental.
    """
    @staticmethod
    def calculate_distance_grid(grid_x, grid_y, cx, cy, seed=0, scale=120.0, amplitude=65.0):
        """
        Calcula a distância euclidiana de cada ponto da grade ao centro (cx, cy)
        aplicando Domain Warping de alta intensidade para distorcer a forma circular.
        """
        from cartographer.math.noise import NoiseGenerator
        
        # Geramos ruído Perlin vetorizado normalizado na faixa [0, 1]
        noise_x = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale, octaves=3, seed=seed, offset=7777)
        noise_y = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale, octaves=3, seed=seed, offset=9999)
        
        # Trazemos o ruído para a faixa [-1, 1] para aplicar distorção bidirecional (Domain Warping)
        warp_x = (noise_x * 2.0 - 1.0) * amplitude
        warp_y = (noise_y * 2.0 - 1.0) * amplitude
        
        dx = grid_x + warp_x - cx
        dy = grid_y + warp_y - cy
        return np.sqrt(dx**2 + dy**2)

    @staticmethod
    def calculate_tectonic_radius(base_radius, ruido_macro):
        """
        Modula o raio de influência continental dinamicamente com base nas correntes tectônicas.
        """
        return base_radius * (0.65 + 0.75 * ruido_macro)

    @staticmethod
    def apply_coastal_distortion(distancia, ruido_costa, irregularidade, base_radius):
        """
        Aplica perturbação de alta frequência à distância euclidiana para simular costões rochosos.
        Aumentamos a amplitude significativamente para criar bordas muito mais recortadas e interessantes.
        """
        return distancia + (ruido_costa * irregularidade * base_radius * 0.85)

    @staticmethod
    def normalize_profile(relevo_perfil):
        """
        Normaliza dinamicamente o perfil geológico para ocupar a amplitude vertical total [0, 1].
        """
        p_min = np.min(relevo_perfil)
        p_max = np.max(relevo_perfil)
        if p_max > p_min:
            return (relevo_perfil - p_min) / (p_max - p_min)
        return relevo_perfil

    @staticmethod
    def calculate_geological_profile(perfil_nome, relevo_base, grid_x, grid_y, seed):
        """
        Aplica o modelo matemático do perfil geológico especificado.
        """
        if perfil_nome == "Alpino":
            relevo_perfil = np.power(relevo_base, 1.5)
        elif perfil_nome == "Platô":
            limiar_plato = 0.6
            relevo_perfil = np.where(
                relevo_base > limiar_plato, 
                limiar_plato + (relevo_base - limiar_plato) * 0.08, 
                relevo_base
            )
        elif perfil_nome == "Arquipélago":
            from cartographer.math.noise import NoiseGenerator
            ruido_arqui = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=18.0, octaves=3, seed=seed, offset=8888)
            relevo_perfil = relevo_base * np.where(ruido_arqui > 0.45, 1.0, 0.1)
        elif perfil_nome == "Erosivo":
            relevo_perfil = np.sqrt(relevo_base) * 0.8
        else:
            relevo_perfil = relevo_base
            
        return TectonicsProcessor.normalize_profile(relevo_perfil)

    @staticmethod
    def apply_cosine_vignette(grid_x, grid_y, map_size=768.0, margem_segura=40.0, largura_fade=80.0):
        """
        Gera uma máscara de atenuação de borda ultra-suave baseada na curva de cosseno.
        """
        dist_x = np.minimum(grid_x, map_size - grid_x)
        dist_y = np.minimum(grid_y, map_size - grid_y)
        menor_dist = np.minimum(dist_x, dist_y)
        
        fator_borda = np.clip((menor_dist - margem_segura) / largura_fade, 0.0, 1.0)
        return 0.5 * (1.0 - np.cos(fator_borda * np.pi))
