import numpy as np
import uuid
import json
import os
from cartographer.world.tile_cartographer import TileCartographer
from cartographer.ai.world_manager_ai import WorldManagerAIClient
from config import cfg_get

class WorldManager:
    def __init__(self, tile_size=256, seed=42, config=None):
        self.tile_size = tile_size
        self.seed = seed
        self.config = config
        self.loaded_tiles = {} # Dicionário {(tx, ty): array_de_dados}

        # Camada de Estratégia (IA/Ollama): Planeja os continentes globalmente.
        # "mundo_tiles_por_lado" é o único lugar que define o grid de tiles do
        # mundo composto — antes esse "3" também vivia solto em generate_world.py
        # (width_tiles/height_tiles) e podia divergir silenciosamente do usado
        # aqui para o planejamento de continentes.
        tiles_por_lado = cfg_get(self.config, "mundo_tiles_por_lado")
        self.tamanho_global = tiles_por_lado * self.tile_size
        self.layout_continentes = WorldManagerAIClient.planejar_continentes(self.seed, self.tamanho_global)

    def get_tile(self, tx, ty):
        """Retorna o tile se já existir, senão gera um novo."""
        if (tx, ty) not in self.loaded_tiles:
            cartografo = TileCartographer(
                size=self.tile_size,
                seed=self.seed,
                config=self.config,
                layout_continentes=self.layout_continentes,
                tamanho_global=self.tamanho_global
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

    def save_world_manifest(self, full_map, filepath="database/world_manifest.json"):
        """
        Analisa a região composta gerada e cria um manifesto estruturado dos continentes,
        mapeando cada um para um UUID e calculando suas estatísticas geográficas reais.
        """
        nivel_mar = self.config["nivel_mar"]
        continentes_list = self.layout_continentes.get("continentes", [])
        
        manifest = {
            "seed": self.seed,
            "tile_size": self.tile_size,
            "dimensao_global": full_map.shape[0],
            "continentes": []
        }
        
        biomas_nomes = {
            1: "Oceano",
            2: "Deserto",
            3: "Mediterrâneo",
            4: "Floresta Temperada",
            5: "Montanha Rochosa"
        }
        
        continentes_stats = {}
        for c in continentes_list:
            c_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"continente.{c['nome']}.{self.seed}"))
            continentes_stats[c["nome"]] = {
                "uuid": c_uuid,
                "nome": c["nome"],
                "centro_planejado": [c["centro_x"], c["centro_y"]],
                "area_planejada_km2": c.get("area_km2", 0),
                "pixels": [],
                "biomas": {}
            }
            
        total_h, total_w, _ = full_map.shape
        is_terra = full_map[:, :, 0] >= nivel_mar
        terra_y, terra_x = np.where(is_terra)
        
        if len(terra_x) > 0 and len(continentes_list) > 0:
            centros = np.array([[c["centro_x"], c["centro_y"]] for c in continentes_list])
            pixels_terra = np.column_stack((terra_x, terra_y))
            
            # Broadcasting de distância euclidiana para assinalar pixels com altíssima performance
            diff = centros[:, np.newaxis, :] - pixels_terra[np.newaxis, :, :]
            distancias = np.linalg.norm(diff, axis=2)
            closest_cont_indices = np.argmin(distancias, axis=0)
            
            for i, p in enumerate(pixels_terra):
                cont_idx = closest_cont_indices[i]
                c_nome = continentes_list[cont_idx]["nome"]
                continentes_stats[c_nome]["pixels"].append(p.tolist())
                
                bioma_id = int(full_map[p[1], p[0], 3])
                continentes_stats[c_nome]["biomas"][bioma_id] = continentes_stats[c_nome]["biomas"].get(bioma_id, 0) + 1
                
        for c_nome, stats in sorted(continentes_stats.items()):
            pixels = stats["pixels"]
            num_pixels = len(pixels)
            
            # FILTRO: Ignora continentes inexistentes (0 pixels) que não possuem nenhuma terra firme mapeada.
            if num_pixels == 0:
                print(f"⚠️ [WORLD-MANIFEST] Ignorando '{c_nome}': continente inexistente ou completamente submerso (0 pixels de terra).")
                continue
                
            if num_pixels > 0:
                pixels_arr = np.array(pixels)
                min_x, min_y = np.min(pixels_arr, axis=0)
                max_x, max_y = np.max(pixels_arr, axis=0)
                
                # Escala real em km² baseada puramente na configuração explícita
                area_real_km2 = int(num_pixels * self.config["escala_pixel_area_km2"])
                
                bbox = {
                    "min_x": int(min_x),
                    "min_y": int(min_y),
                    "max_x": int(max_x),
                    "max_y": int(max_y)
                }
                
                biomas_count = stats["biomas"]
                biomas_predominantes = []
                for b_id, count in sorted(biomas_count.items(), key=lambda item: item[1], reverse=True):
                    b_nome = biomas_nomes.get(b_id, f"Bioma {b_id}")
                    pct = (count / num_pixels) * 100.0
                    biomas_predominantes.append({
                        "id": b_id,
                        "nome": b_nome,
                        "percentual": round(pct, 2),
                        "pixels": count
                    })
            else:
                area_real_km2 = 0
                bbox = {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
                biomas_predominantes = []
                
            manifest["continentes"].append({
                "uuid": stats["uuid"],
                "nome": stats["nome"],
                "centro_planejado": stats["centro_planejado"],
                "area_planejada_km2": stats["area_planejada_km2"],
                "area_real_km2": area_real_km2,
                "pixels_terra": num_pixels,
                "bounding_box": bbox,
                "biomas_predominantes": biomas_predominantes
            })
            
        # Garante a existência do diretório pai
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)
            
        print(f"Manifesto do mundo salvo com sucesso em '{filepath}' contendo {len(manifest['continentes'])} continentes.")
