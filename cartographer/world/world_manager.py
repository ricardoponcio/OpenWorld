import numpy as np
import uuid
import json
import os
import hashlib
from cartographer.world.tile_cartographer import TileCartographer
from cartographer.ai.world_manager_ai import WorldManagerAIClient
from cartographer.math.climate import Bioma
from config import cfg_get

class WorldManager:
    def __init__(self, tile_size=256, seed=42, config=None, layout_continentes=None):
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
        # P0.5: o layout de continentes é a única entrada de `generate_tile` que não
        # vinha de config nem de disco — era obtido de uma chamada de LLM a cada
        # instância e nunca persistido. Isso torna o mundo irreprodutível e bloqueia
        # o servidor de tiles (que não pode rechamar a IA a cada requisição). Agora
        # quem já tem o layout (lido do manifesto) pode reinjetá-lo aqui; só se
        # planeja de novo (IA/fallback) quando ninguém fornece um.
        self.layout_continentes = layout_continentes if layout_continentes is not None \
            else WorldManagerAIClient.planejar_continentes(self.seed, self.tamanho_global)
        self._calibrar_continentes()

    def _calibrar_continentes(self, rounds=3):
        """
        Fase 1.1 (P1.2): acha, por bisseção, o `compensacao_calibrada` de cada continente
        que ainda não tem um — o multiplicador de raio que aproxima a área real da área
        planejada. Necessário porque a compensação de irregularidade em
        `TileCartographer.gerar_janela` corrige só o viés médio; o desvio residual de cada
        continente específico vem do valor real do campo de ruído macro-tectônico naquela
        posição exata do mundo, que só se conhece renderizando.

        ⚠️ Achado durante a implementação: calibrar cada continente ISOLADO (sozinho no
        layout) supera o alvo isoladamente, mas o resultado final (com todos os
        continentes competindo pelo `np.maximum` de `mask_continente`) fica bem abaixo —
        um continente perdeu 36% de área real mesmo com o raio "certo" em isolamento.
        Não é bug de atribuição: é competição real por território de fronteira entre
        vizinhos próximos (a distância mínima da IA entre centros é só 220px, e R pode
        passar de 200px). A calibração TEM que rodar com todos os continentes presentes,
        medindo com `retornar_donos` (atribuição exata) — só medir "sou terra?" sem saber
        de quem não captura a disputa de fronteira.

        `rounds`: como os continentes competem entre si, calibrar um afeta o resultado dos
        outros — algumas iterações de "todo mundo se recalibra vendo o estado atual dos
        vizinhos" convergem pra um equilíbrio, no estilo Gauss-Seidel.

        Persistido em `layout_continentes` (não recalculado a cada load — P0.5): um mundo
        já calibrado e salvo no manifesto não paga o custo de novo, e continua reproduzível.
        """
        cfg = self.config
        continentes = self.layout_continentes.get("continentes", [])
        pendentes = [c for c in continentes if c.get("area_km2", 0) > 0 and "compensacao_calibrada" not in c]
        if not pendentes:
            return
        for c in pendentes:
            c["compensacao_calibrada"] = 1.0  # ponto de partida neutro pras rodadas de competição

        escala_pixel_area_km2 = cfg_get(cfg, "escala_pixel_area_km2")
        amostras = 200  # full extent, resolução baixa de propósito — só a PROPORÇÃO de área importa
        tentativas = 6
        lado = float(self.tamanho_global)
        area_px_mundo = (lado / amostras) ** 2

        for rodada in range(rounds):
            for cont in pendentes:
                idx = continentes.index(cont)
                area_alvo = cont["area_km2"]
                lo, hi, melhor = 0.3, 4.0, cont["compensacao_calibrada"]
                for _ in range(tentativas):
                    melhor = (lo + hi) / 2
                    cont["compensacao_calibrada"] = melhor
                    cartografo = TileCartographer(
                        size=self.tile_size, seed=self.seed, config=cfg,
                        layout_continentes={"continentes": continentes},
                        tamanho_global=self.tamanho_global,
                    )
                    _, donos = cartografo.gerar_janela(0, 0, lado, lado, amostras, amostras, retornar_donos=True)
                    pixels_terra = int(np.sum(donos == idx))
                    area_real = pixels_terra * area_px_mundo * escala_pixel_area_km2
                    if area_real < area_alvo:
                        lo = melhor
                    else:
                        hi = melhor
                cont["compensacao_calibrada"] = round(melhor, 4)

        for cont in pendentes:
            print(f"[CALIBRACAO] Continente '{cont['nome']}': compensacao_calibrada={cont['compensacao_calibrada']:.3f}")

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
            # P0.5: grava o layout cru exatamente como `TileCartographer` o recebe (não
            # normalize/"limpe" — qualquer transformação vira uma segunda convenção que
            # diverge). É isto que torna o mundo reproduzível sem chamar a IA de novo, e
            # o que o servidor de tiles (Fase 0.4) vai carregar do manifesto.
            "layout_continentes": self.layout_continentes,
            # Chave de invalidação de cache de tiles (Fase 0.4): muda sempre que a config
            # de cartografia muda, então tile velho nunca serve terreno gerado com config
            # antiga em silêncio.
            "config_hash": hashlib.sha256(
                json.dumps(self.config, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16],
            "continentes": []
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

        if len(continentes_list) > 0:
            # Fase 1.1 (achado na calibração de área, P1.2): atribuir cada pixel de terra
            # ao continente de centro mais próximo (bruto ou normalizado pelo raio) "rouba"
            # pixels de um continente pequeno perto de um grande — mesmo quando o pixel foi
            # literalmente pintado pela máscara do vizinho, não a distância ao centro que
            # decide se aquele ponto é terra. Medido: um continente perdeu 40% da própria
            # área real assim, mesmo com o raio corretamente calibrado.
            #
            # `donos` é a atribuição EXATA: o índice do continente cujo `fator_radial`
            # venceu o `np.maximum` naquele pixel dentro de `gerar_janela` — por
            # construção, é sempre igual a quem realmente decidiu que ali é terra. Chamado
            # uma vez sobre a extensão inteira (F2 garante bit a bit igual ao `full_map`
            # já montado por tile).
            cartografo = TileCartographer(
                size=self.tile_size, seed=self.seed, config=self.config,
                layout_continentes=self.layout_continentes, tamanho_global=self.tamanho_global,
            )
            _, donos = cartografo.gerar_janela(0, 0, total_w, total_h, total_w, total_h, retornar_donos=True)

            for cont_idx, cont in enumerate(continentes_list):
                c_nome = cont["nome"]
                ys, xs = np.where(donos == cont_idx)
                continentes_stats[c_nome]["pixels"] = np.column_stack((xs, ys)).tolist()
                bioma_ids = full_map[ys, xs, 3].astype(int)
                for bioma_id in bioma_ids:
                    continentes_stats[c_nome]["biomas"][int(bioma_id)] = \
                        continentes_stats[c_nome]["biomas"].get(int(bioma_id), 0) + 1
                
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
                    bioma = Bioma.por_id(b_id)
                    b_nome = bioma.rotulo if bioma else f"Bioma {b_id}"
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
