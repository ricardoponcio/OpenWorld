import numpy as np
from cartographer.math import NoiseGenerator, TectonicsProcessor, ClimateProcessor

class TileCartographer:
    """
    Cartógrafo procedural responsável por gerar os dados geográficos e climáticos
    de tiles individuais de forma perfeitamente contínua e determinística.
    """
    def __init__(self, size=256, seed=0, config=None, layout_continentes=None):
        self.size = size
        self.seed = seed
        self.config = config
        self.layout_continentes = layout_continentes or {"continentes": []}
        # Cada Tile possui 4 canais de dados de ponto flutuante:
        # [0: Altitude, 1: Temperatura, 2: Umidade, 3: ID do Bioma]
        self.data = np.zeros((self.size, self.size, 4), dtype=np.float32)

    def generate_tile(self, offset_x, offset_y):
        """
        Gera um pedaço do mundo baseado na sua posição global.
        offset_x/y são as coordenadas do tile (ex: 0, 1, 2...)
        """
        # Transformamos o índice do tile em pixels globais
        start_x = offset_x * self.size
        start_y = offset_y * self.size
        
        # Geramos a grade de coordenadas globais para este Tile
        y_range = np.arange(start_y, start_y + self.size)
        x_range = np.arange(start_x, start_x + self.size)
        grid_x, grid_y = np.meshgrid(x_range, y_range)

        # 1. Geração da base geológica contínua via Perlin noise
        ruido_macro = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=220.0, octaves=3, seed=self.seed)
        relevo_base = NoiseGenerator.generate_tectonic_base(grid_x, grid_y, seed=self.seed)

        # 2. Costa de alta frequência para distorções locais
        ruido_costa = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=60.0, octaves=4, seed=self.seed, offset=12345)

        # Inicializa a máscara de continente vazia e o relevo acumulado
        mask_continente = np.zeros((self.size, self.size), dtype=np.float32)
        relevo_continentes = np.zeros((self.size, self.size), dtype=np.float32)
        
        nivel_mar = self.config["nivel_mar"]
        nivel_montanha = self.config["nivel_montanha"]
        
        # Calor e umidade modificadores ponderados pela proximidade ao continente
        mod_calor_total = np.zeros((self.size, self.size), dtype=np.float32)
        mod_umidade_total = np.zeros((self.size, self.size), dtype=np.float32)
        
        for cont in self.layout_continentes.get("continentes", []):
            cx = cont["centro_x"]
            cy = cont["centro_y"]
            
            # Conversão de escala (pixels vs km²) com teto de segurança
            area = cont.get("area_km2", 0)
            if area > 0:
                R = np.sqrt(area / np.pi) / 10.0
            else:
                R = cont.get("raio_visual", cont.get("raio", 200.0))
            
            R = np.clip(R, 65.0, 155.0)
                
            irreg = cont["irregularidade"]
            elev_max = cont.get("elevacao_maxima", 0.8)
            perfil = cont.get("perfil_geologico", "Alpino")
            
            # Distância euclidiana e raio modulado dinamicamente pelas correntes tectônicas
            distancia = TectonicsProcessor.calculate_distance_grid(grid_x, grid_y, cx, cy)
            raio_dinamico = TectonicsProcessor.calculate_tectonic_radius(R, ruido_macro)
            
            # Distorção costeira
            dist_perturbada = TectonicsProcessor.apply_coastal_distortion(distancia, ruido_costa, irreg, R)
            
            # Fator de gradiente radial perturbado
            fator_radial = np.clip(1.0 - (dist_perturbada / raio_dinamico), 0.0, 1.0)
            
            # Acumula a máscara continental
            mask_continente = np.maximum(mask_continente, fator_radial)
            
            # Modelagem do perfil geológico do continente
            relevo_perfil = TectonicsProcessor.calculate_geological_profile(perfil, relevo_base, grid_x, grid_y, self.seed)
            
            # Altitude continental garantida acima da costa
            f_terra = np.clip((fator_radial - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)
            altura_terra = nivel_mar + (elev_max - nivel_mar) * relevo_perfil * f_terra
            altura_terra = np.where(fator_radial >= nivel_mar, altura_terra, 0.0)
            
            # Acumula relevo continental
            relevo_continentes = np.maximum(relevo_continentes, altura_terra)
            
            # Climatologia regional baseada nos modificadores da IA
            modificadores = cont.get("modificadores", {})
            mod_calor = modificadores.get("calor", cont.get("modificador_calor", 0.0))
            mod_umidade = modificadores.get("umidade", cont.get("modificador_umidade", 0.0))
            
            mod_calor_total += fator_radial * mod_calor
            mod_umidade_total += fator_radial * mod_umidade
            
        # Máscara de Vignette de Cosseno global para as bordas do mundo (768x768)
        fator_borda = TectonicsProcessor.apply_cosine_vignette(grid_x, grid_y, map_size=768.0)
        
        mask_continente = mask_continente * fator_borda
        relevo_continentes = relevo_continentes * fator_borda
        
        # Ruído marinho para fossas e bancos de areia
        f_mar = self.config.get("ruido_mar_escala", 80.0)
        oct_mar = self.config.get("ruido_mar_oitavas", 3)
        amp_mar = self.config.get("ruido_mar_amplitude", 0.14)
        
        ruido_mar = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=f_mar, octaves=oct_mar, seed=self.seed, offset=9999)
        max_ruido_mar = min(nivel_mar * 0.90, 0.02 + amp_mar)
        ruido_mar_suave = 0.02 + (ruido_mar * (max_ruido_mar - 0.02))
        
        # Mesclagem terra-mar final no canal 0 (Altitude)
        self.data[:, :, 0] = np.where(
            mask_continente >= nivel_mar,
            relevo_continentes,
            (1.0 - (mask_continente / nivel_mar)) * ruido_mar_suave + (mask_continente / nivel_mar) * nivel_mar
        )
        
        # 3. Cálculo climático e classificação dos biomas
        self.data[:, :, 1] = ClimateProcessor.calculate_temperature(
            grid_y, self.data[:, :, 0], mod_calor_total, map_height=768.0
        )
        self.data[:, :, 2] = ClimateProcessor.calculate_humidity(
            self.data[:, :, 0], mod_umidade_total, nivel_mar=nivel_mar
        )
        self.data[:, :, 3] = ClimateProcessor.classify_biomes(
            self.data[:, :, 0], self.data[:, :, 1], self.data[:, :, 2],
            nivel_mar=nivel_mar, nivel_montanha=nivel_montanha
        )
        
        return self.data
