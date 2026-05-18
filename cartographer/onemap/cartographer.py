import random
import numpy as np
from noise import pnoise2

class Cartographer:
    def __init__(self, size=1000, seed=None, config=None):
        self.size = size
        self.seed = seed if seed is not None else random.randint(0, 99999)
        
        # Configurações padrão caso o usuário não envie nada
        default_config = {
            "frequencia": 350.0,
            "oitavas": 6,
            "persistencia": 0.5,
            "lacunariedade": 2.0,
            "nivel_mar": 0.25,
            "nivel_montanha": 0.8
        }
        # Mescla as configs enviadas com as padrão
        self.config = {**default_config, **(config or {})}
        
        self.world_data = np.zeros((self.size, self.size, 4), dtype=np.float32)
        
        self.BIOME_IDS = {
            "OCEANO": 1, "DESERTO": 2, "MEDITERRANEO": 3,
            "FLORESTA_TEMPERADA": 4, "MONTANHA_ROCHOSA": 5
        }

    def generate_relevo(self):
        print(f" -> Gerando relevo (Escala: {self.config['frequencia']}, Oitavas: {self.config['oitavas']})...")
        x_idx, y_idx = np.meshgrid(np.arange(self.size), np.arange(self.size))
        
        v_pnoise2 = np.vectorize(lambda x, y: pnoise2(
            x / self.config["frequencia"], 
            y / self.config["frequencia"], 
            octaves=self.config["oitavas"], 
            persistence=self.config["persistencia"], 
            lacunarity=self.config["lacunariedade"], 
            base=self.seed % 50000
        ))
        
        ruido = v_pnoise2(x_idx, y_idx)
        # Normalização dinâmica para garantir que sempre haja picos e vales
        self.world_data[:, :, 0] = (ruido - ruido.min()) / (ruido.max() - ruido.min())

    def generate_clima(self):
        print(" -> Simulando Clima...")
        y_coords = np.linspace(0, 1, self.size).reshape(self.size, 1)
        latitude_factor = 1.0 - y_coords # Norte frio, Sul quente
        
        # Temperatura: Latitude - (Altitude * peso)
        self.world_data[:, :, 1] = np.clip(latitude_factor - (self.world_data[:, :, 0] * 0.4), 0, 1)
        
        # Umidade simplificada baseada em altitude e proximidade do "mar"
        # Onde altitude < nivel_mar, umidade é alta.
        self.world_data[:, :, 2] = np.where(self.world_data[:, :, 0] < self.config["nivel_mar"], 0.8, 0.4)

    def computar_biomas(self):
        print(" -> Classificando Biomas...")
        height = self.world_data[:, :, 0]
        temp = self.world_data[:, :, 1]
        umid = self.world_data[:, :, 2]
        biomas = self.world_data[:, :, 3]

        # Aplicação das regras parametrizadas
        biomas[height < self.config["nivel_mar"]] = self.BIOME_IDS["OCEANO"]
        biomas[height > self.config["nivel_montanha"]] = self.BIOME_IDS["MONTANHA_ROCHOSA"]
        
        # Máscaras para áreas de terra firme
        terra_firme = (height >= self.config["nivel_mar"]) & (height <= self.config["nivel_montanha"])
        
        # Lógica de Clima para terra firme
        biomas[terra_firme & (temp > 0.6) & (umid < 0.5)] = self.BIOME_IDS["DESERTO"]
        biomas[terra_firme & (temp > 0.4) & (umid >= 0.5)] = self.BIOME_IDS["MEDITERRANEO"]
        biomas[terra_firme & (biomas == 0)] = self.BIOME_IDS["FLORESTA_TEMPERADA"]

    def build_world(self):
        self.generate_relevo()
        self.generate_clima()
        self.computar_biomas()
        print("Mundo gerado!")

    def export_arquivao(self, filename="mapa.npz"):
        np.savez_compressed(filename, mapa=self.world_data)