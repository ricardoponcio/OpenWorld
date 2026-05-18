import numpy as np
from noise import pnoise2

class TileCartographer:
    def __init__(self, size=256, seed=0, config=None, layout_continentes=None):
        self.size = size
        self.seed = seed
        self.config = config
        self.layout_continentes = layout_continentes or {"continentes": []}
        # Cada Tile tem seus próprios dados
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

        # 1. Relevo com Coordenadas Globais (Garante a continuidade)
        v_pnoise2 = np.vectorize(lambda x, y: pnoise2(
            x / self.config["frequencia"], 
            y / self.config["frequencia"], 
            octaves=self.config["oitavas"],
            base=self.seed
        ))
        
        ruido = v_pnoise2(grid_x, grid_y)
        # Importante: Normalização fixa para evitar que tiles vizinhos tenham escalas diferentes
        relevo_base = (ruido + 1) / 2.0 

        # --- APLICAÇÃO DE MÁSCARAS DE CONTINENTES (ESTRATÉGIA IA + ARQUITETURA PYTHON) ---
        # Ruído de costa para criar penínsulas, cabos e baías irregulares (alta frequência)
        v_noise_costa = np.vectorize(lambda x, y: pnoise2(
            x / 60.0, 
            y / 60.0, 
            octaves=4, 
            base=(self.seed + 12345) % 50000
        ))
        ruido_costa = v_noise_costa(grid_x, grid_y)

        # Inicializa a máscara de continente vazia (tamanho do tile)
        mask_continente = np.zeros((self.size, self.size), dtype=np.float32)
        
        # Calor e umidade modificadores ponderados pela proximidade ao continente
        mod_calor_total = np.zeros((self.size, self.size), dtype=np.float32)
        mod_umidade_total = np.zeros((self.size, self.size), dtype=np.float32)
        
        for cont in self.layout_continentes.get("continentes", []):
            cx = cont["centro_x"]
            cy = cont["centro_y"]
            R = cont["raio"]
            irreg = cont["irregularidade"]
            
            # Distância euclidiana global de cada ponto do tile até o centro do continente
            dx = grid_x - cx
            dy = grid_y - cy
            distancia = np.sqrt(dx**2 + dy**2)
            
            # Perturba a distância calculada com o ruído de costa proporcional à irregularidade e ao raio
            dist_perturbada = distancia + (ruido_costa * irreg * R * 0.4)
            
            # Fator de gradiente radial: 1.0 no centro, cai para 0.0 na borda do raio perturbado
            fator_radial = 1.0 - (dist_perturbada / R)
            fator_radial = np.clip(fator_radial, 0.0, 1.0)
            
            # Combina os continentes acumulando com o máximo (para manter o pico de relevo onde se sobrepõem)
            mask_continente = np.maximum(mask_continente, fator_radial)
            
            # Modificadores de calor e umidade regionais ponderados pelo fator radial
            mod_calor_total += fator_radial * cont.get("modificador_calor", 0.0)
            mod_umidade_total += fator_radial * cont.get("modificador_umidade", 0.0)

        # Multiplica o relevo base pela máscara de continente:
        # Nas bordas e no meio do oceano, a máscara é 0, empurrando tudo para o oceano profundo!
        self.data[:, :, 0] = relevo_base * mask_continente
        
        # 2. Clima: Temperatura por Latitude Global, Altitude e modificadores IA
        # Supondo um mundo de 3x3 tiles (768 pixels) para a escala de latitude
        total_mundo_h = 768.0
        latitude_factor = 1.0 - (grid_y / total_mundo_h)
        latitude_factor = np.clip(latitude_factor, 0.0, 1.0)
        
        # Temperatura = Latitude - (Altitude * 0.4) + modificadores de calor regionais
        temp_base = latitude_factor - (self.data[:, :, 0] * 0.4) + mod_calor_total
        self.data[:, :, 1] = np.clip(temp_base, 0.0, 1.0)
        
        # Umidade = 0.8 se abaixo do mar, senão 0.4 + modificadores de umidade regionais
        umid_base = np.where(self.data[:, :, 0] < self.config["nivel_mar"], 0.8, 0.4 + mod_umidade_total)
        self.data[:, :, 2] = np.clip(umid_base, 0.0, 1.0)

        # 3. Classificação de Biomas
        BIOME_IDS = {
            "OCEANO": 1, "DESERTO": 2, "MEDITERRANEO": 3,
            "FLORESTA_TEMPERADA": 4, "MONTANHA_ROCHOSA": 5
        }
        
        height = self.data[:, :, 0]
        temp = self.data[:, :, 1]
        umid = self.data[:, :, 2]
        biomas = self.data[:, :, 3]

        biomas[height < self.config["nivel_mar"]] = BIOME_IDS["OCEANO"]
        biomas[height > self.config["nivel_montanha"]] = BIOME_IDS["MONTANHA_ROCHOSA"]
        
        # Máscaras para áreas de terra firme
        terra_firme = (height >= self.config["nivel_mar"]) & (height <= self.config["nivel_montanha"])
        
        # Lógica de Clima para terra firme
        biomas[terra_firme & (temp > 0.6) & (umid < 0.5)] = BIOME_IDS["DESERTO"]
        biomas[terra_firme & (temp > 0.4) & (umid >= 0.5)] = BIOME_IDS["MEDITERRANEO"]
        biomas[terra_firme & (biomas == 0)] = BIOME_IDS["FLORESTA_TEMPERADA"]

        return self.data