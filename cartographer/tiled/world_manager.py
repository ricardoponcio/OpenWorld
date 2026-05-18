import numpy as np
from tile_cartographer import TileCartographer
from cartographer.tiled.ai.world_manager_ai import WorldManagerAIClient

class WorldManager:
    def __init__(self, tile_size=256, seed=42, config=None):
        self.tile_size = tile_size
        self.seed = seed
        self.config = config
        self.loaded_tiles = {} # Dicionário {(tx, ty): array_de_dados}
        
        # Camada de Estratégia (IA/Ollama): Planeja os continentes globalmente
        # Um mundo composto de 3x3 tiles tem dimensões 768x768
        tamanho_global = 3 * self.tile_size
        self.layout_continentes = WorldManagerAIClient.planejar_continentes(self.seed, tamanho_global)

    def get_tile(self, tx, ty):
        """Retorna o tile se já existir, senão gera um novo."""
        if (tx, ty) not in self.loaded_tiles:
            cartografo = TileCartographer(
                size=self.tile_size, 
                seed=self.seed, 
                config=self.config, 
                layout_continentes=self.layout_continentes
            )
            self.loaded_tiles[(tx, ty)] = cartografo.generate_tile(tx, ty)
        return self.loaded_tiles[(tx, ty)]

    def get_full_map_region(self, tx_start, ty_start, width_tiles, height_tiles):
        # Cria o "tapete" vazio onde os tiles serão colados
        # 4 camadas: Relevo, Temp, Umidade, Bioma
        total_h = height_tiles * self.tile_size
        total_w = width_tiles * self.tile_size
        full_map = np.zeros((total_h, total_w, 4), dtype=np.float32)
        
        for ty in range(height_tiles):
            for tx in range(width_tiles):
                # Coordenadas do tile atual
                current_tx = tx_start + tx
                current_ty = ty_start + ty
                
                # Gera ou busca o tile
                tile_data = self.get_tile(current_tx, current_ty)
                
                # Calcula onde este tile entra na matriz mestre (fatiamento)
                row_start = ty * self.tile_size
                row_end = row_start + self.tile_size
                col_start = tx * self.tile_size
                col_end = col_start + self.tile_size
                
                # "Cola" o tile na posição
                full_map[row_start:row_end, col_start:col_end] = tile_data
                
                print(f"Tile ({current_tx}, {current_ty}) encaixado.")
                
        return full_map