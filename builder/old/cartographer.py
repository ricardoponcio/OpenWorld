"""
SCRIPT: cartographer.py
FUNÇÃO: Mestre de Coordenadas e Geometria do Mundo.
DESCRIÇÃO: Gerencia o posicionamento espacial de casas e locais, garantindo que 
           novas construções não se sobreponham e respeitem o layout da vila.
"""
import random
import json

class Cartographer:
    def __init__(self, size=20):
        self.size = size
        # 0: Grama, 1: Água, 2: Estrada, 3: Árvore
        self.grid = [[0 for _ in range(size)] for _ in range(size)]

    def generate_terrain(self):
        """Gera um terreno básico com um rio e algumas árvores."""
        # Criar um Rio (vertical)
        river_x = random.randint(2, self.size - 3)
        for y in range(self.size):
            self.grid[y][river_x] = 1
            # Margem do rio (chance de árvore)
            if random.random() < 0.3:
                self.grid[y][river_x + (1 if random.random() > 0.5 else -1)] = 3

        # Espalhar Árvores aleatórias
        for _ in range(self.size):
            rx, ry = random.randint(0, self.size-1), random.randint(0, self.size-1)
            if self.grid[ry][rx] == 0:
                self.grid[ry][rx] = 3
        
        return self.grid

    def assign_coordinates(self, locais_ids):
        """Distribui os locais na grade evitando a água."""
        posicoes = {}
        for loc_id in locais_ids:
            tentativas = 0
            colocado = False
            while not colocado and tentativas < 100:
                x = random.randint(1, self.size - 2)
                y = random.randint(1, self.size - 2)
                
                # Só coloca se for grama (0) e não tiver vizinho muito grudado
                if self.grid[y][x] == 0:
                    posicoes[loc_id] = [x, y]
                    self.grid[y][x] = 2 # Marca como "Construção/Estrada" na grade
                    colocado = True
                tentativas += 1
        
        return posicoes

    def export_map(self):
        return json.dumps(self.grid)
