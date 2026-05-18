"""
MODULE: roi_zoom.py
FUNÇÃO: Pipeline de Geração de Mapa por Demanda (ROI Zoom).
DESCRIÇÃO:
    Dado o UUID de um continente presente no world_manifest.json, esta pipeline:
    1. Localiza o continente e obtém sua Bounding Box no mapa global.
    2. Recorta as 4 camadas de dados do .npz global (altitude, temp, umidade, bioma).
    3. Interpola o recorte para a resolução de destino (ex: 3000x3000px).
    4. Sobrepõe uma camada de Ruído Perlin de Alta Frequência para sintetizar
       micro-detalhes de fraturas rochosas e recortes costeiros inéditos.
    5. Recalcula clima e biomas para a resolução ampliada.
    6. Salva o resultado em um arquivo .npz individual por continente.
"""
import json
import os
import numpy as np
from cartographer.math import NoiseGenerator, ClimateProcessor


class ROIZoomGenerator:
    """
    Gerador de mapas de alta resolução por demanda para um continente específico.

    A ideia central é o refinamento progressivo:
    - O mapa global (768x768) é a 'verdade macro': define continentes e biomas.
    - O mapa de zoom (~3000x3000) herda essa verdade e adiciona micro-detalhes
      que só existem nessa escala, como fiordes, vales e crateras.
    """

    # Padding em pixels no espaço global para incluir um pouco de oceano ao redor
    BORDER_PADDING = 20

    def __init__(
        self,
        manifest_path: str = "database/world_manifest.json",
        npz_path: str = "database/mapa_composto.npz",
        output_dir: str = "database/continentes",
        target_resolution: int = 3000,
        seed: int = 1337,
        config: dict = None,
    ):
        """
        Parâmetros:
            manifest_path:      Caminho para o world_manifest.json.
            npz_path:           Caminho para o mapa_composto.npz global.
            output_dir:         Diretório de saída para os .npz dos continentes.
            target_resolution:  Resolução final do mapa de zoom (pixels de lado).
            seed:               Semente global do mundo para reprodutibilidade.
            config:             Dicionário de configuração do mundo (nivels de mar, etc.).
        """
        self.manifest_path = manifest_path
        self.npz_path = npz_path
        self.output_dir = output_dir
        self.target_resolution = target_resolution
        self.seed = seed
        self.config = config or {
            "nivel_mar": 0.35,
            "nivel_montanha": 0.80,
        }

        self._manifest: dict = self._load_manifest()
        self._global_map: np.ndarray | None = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Carga de dados
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict:
        """Lê e valida o world_manifest.json."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(
                f"Manifesto não encontrado em '{self.manifest_path}'. "
                "Execute generate_world.py primeiro."
            )
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_global_map(self) -> np.ndarray:
        """Carrega o .npz global de forma lazy (uma única vez por instância)."""
        if self._global_map is None:
            if not os.path.exists(self.npz_path):
                raise FileNotFoundError(
                    f"Mapa global não encontrado em '{self.npz_path}'. "
                    "Execute generate_world.py primeiro."
                )
            data = np.load(self.npz_path)
            # A chave usada em generate_world.py é 'mapa'
            self._global_map = data["mapa"]
        return self._global_map

    # ------------------------------------------------------------------
    # Resolução de UUID → entrada do manifesto
    # ------------------------------------------------------------------

    def _find_continent(self, uuid_or_name: str) -> dict:
        """
        Localiza o continente pelo UUID (exato) ou pelo nome (case-insensitive).

        Retorna o dicionário completo do continente do manifesto.
        Lança ValueError se não encontrado.
        """
        needle = uuid_or_name.strip().lower()
        for cont in self._manifest.get("continentes", []):
            if cont["uuid"] == uuid_or_name or cont["nome"].lower() == needle:
                return cont
        nomes = [c["nome"] for c in self._manifest.get("continentes", [])]
        raise ValueError(
            f"Continente '{uuid_or_name}' não encontrado no manifesto. "
            f"Disponíveis: {nomes}"
        )

    # ------------------------------------------------------------------
    # Recorte (crop) do mapa global
    # ------------------------------------------------------------------

    def _crop_global(self, bbox: dict, global_map: np.ndarray) -> np.ndarray:
        """
        Recorta a região da Bounding Box do mapa global com padding de borda.

        Retorna array (H_crop, W_crop, 4).
        """
        H, W, _ = global_map.shape
        min_x = max(0, bbox["min_x"] - self.BORDER_PADDING)
        min_y = max(0, bbox["min_y"] - self.BORDER_PADDING)
        max_x = min(W - 1, bbox["max_x"] + self.BORDER_PADDING)
        max_y = min(H - 1, bbox["max_y"] + self.BORDER_PADDING)

        # NumPy: eixo 0 = linhas = Y, eixo 1 = colunas = X
        return global_map[min_y : max_y + 1, min_x : max_x + 1, :]

    # ------------------------------------------------------------------
    # Interpolação (upscale)
    # ------------------------------------------------------------------

    @staticmethod
    def _upscale(crop: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
        """
        Interpola bilinearmente cada canal do recorte para a resolução de destino.

        Usa scipy se disponível (melhor qualidade), cai em numpy puro via zoom.
        """
        try:
            from scipy.ndimage import zoom as scipy_zoom

            # Fatores de escala por eixo (H e W) — canal 4 não é redimensionado
            fh = target_h / crop.shape[0]
            fw = target_w / crop.shape[1]
            # order=1 → interpolação bilinear
            return scipy_zoom(crop, (fh, fw, 1), order=1).astype(np.float32)
        except ImportError:
            # Fallback manual sem scipy
            out = np.zeros((target_h, target_w, crop.shape[2]), dtype=np.float32)
            for c in range(crop.shape[2]):
                # Coordenadas de destino em espaço de origem
                src_y = np.linspace(0, crop.shape[0] - 1, target_h)
                src_x = np.linspace(0, crop.shape[1] - 1, target_w)
                gx, gy = np.meshgrid(src_x, src_y)
                gy0 = np.floor(gy).astype(int).clip(0, crop.shape[0] - 2)
                gx0 = np.floor(gx).astype(int).clip(0, crop.shape[1] - 2)
                gy1, gx1 = gy0 + 1, gx0 + 1
                dy, dx = gy - gy0, gx - gx0
                ch = crop[:, :, c]
                out[:, :, c] = (
                    ch[gy0, gx0] * (1 - dy) * (1 - dx)
                    + ch[gy1, gx0] * dy * (1 - dx)
                    + ch[gy0, gx1] * (1 - dy) * dx
                    + ch[gy1, gx1] * dy * dx
                )
            return out

    # ------------------------------------------------------------------
    # Refinamento de micro-detalhes via Perlin de Alta Frequência
    # ------------------------------------------------------------------

    def _apply_micro_detail(
        self,
        upscaled: np.ndarray,
        cont_seed_offset: int,
    ) -> np.ndarray:
        """
        Injeta micro-detalhes geológicos na camada de altitude do mapa ampliado.

        A estratégia é hierárquica:
          - Ruído Perlin de ALTA frequência (escala ~30px) → fraturas e relevos locais.
          - Ruído Perlin de MÉDIA frequência (escala ~120px) → vales e colinas suaves.
          - Os dois são misturados e modulados pela altitude macro para que o detalhe
            seja PROPORCIONAL à elevação: montanhas recebem mais relevo, praias menos.

        O resultado é somado ao canal 0 (altitude) já interpolado, mantendo
        o nível do mar estável.
        """
        H, W, _ = upscaled.shape
        y_range = np.arange(H, dtype=np.float32)
        x_range = np.arange(W, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(x_range, y_range)

        # Ruído de alta frequência: micro-fraturas e costões
        ruido_hf = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=30.0,
            octaves=6,
            seed=self.seed,
            offset=cont_seed_offset + 11111,
        )

        # Ruído de média frequência: vales e colinas regionais
        ruido_mf = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=120.0,
            octaves=4,
            seed=self.seed,
            offset=cont_seed_offset + 22222,
        )

        # Ruído composto normalizado em [-0.5, 0.5]
        ruido_composto = (0.60 * ruido_hf + 0.40 * ruido_mf) - 0.5

        # Máscara de modulação: aplica mais detalhe onde há terra e altitude
        nivel_mar = self.config.get("nivel_mar", 0.35)
        alt_macro = upscaled[:, :, 0]
        # Normaliza a altitude acima do nível do mar para [0, 1]
        mask_terra = np.clip((alt_macro - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)

        # Amplitude do ruído proporcional à altitude (máximo ±8% de relevo extra)
        amplitude = mask_terra * 0.08

        resultado = upscaled.copy()
        resultado[:, :, 0] = np.clip(alt_macro + ruido_composto * amplitude, 0.0, 1.0)
        return resultado

    # ------------------------------------------------------------------
    # Recálculo de clima e biomas na resolução de zoom
    # ------------------------------------------------------------------

    def _recompute_climate_and_biomes(self, data: np.ndarray, offset_y_global: int) -> np.ndarray:
        """
        Recalcula temperatura, umidade e biomas para o mapa de zoom.

        O offset_y_global posiciona o tile na latitude correta do mundo
        para que o cálculo de temperatura respeite o gradiente latitudinal.
        """
        H, W, _ = data.shape
        nivel_mar = self.config.get("nivel_mar", 0.35)
        nivel_montanha = self.config.get("nivel_montanha", 0.80)

        # Grade de posições globais fictícias para calcular temperatura corretamente
        y_range = np.arange(offset_y_global, offset_y_global + H, dtype=np.float32)
        x_range = np.arange(W, dtype=np.float32)
        _, grid_y = np.meshgrid(x_range, y_range)

        result = data.copy()
        result[:, :, 1] = ClimateProcessor.calculate_temperature(
            grid_y, data[:, :, 0], np.zeros((H, W), dtype=np.float32), map_height=768.0
        )
        result[:, :, 2] = ClimateProcessor.calculate_humidity(
            data[:, :, 0], np.zeros((H, W), dtype=np.float32), nivel_mar=nivel_mar
        )
        result[:, :, 3] = ClimateProcessor.classify_biomes(
            data[:, :, 0], result[:, :, 1], result[:, :, 2],
            nivel_mar=nivel_mar, nivel_montanha=nivel_montanha,
        )
        return result

    # ------------------------------------------------------------------
    # Ponto de entrada público
    # ------------------------------------------------------------------

    def generate(self, uuid_or_name: str) -> str:
        """
        Executa a pipeline completa de ROI Zoom para o continente especificado.

        Parâmetros:
            uuid_or_name: UUID exato ou nome do continente (case-insensitive).

        Retorna:
            Caminho absoluto do arquivo .npz gerado.
        """
        print(f"[ROI-ZOOM] Iniciando geração de zoom para: '{uuid_or_name}'")

        # 1. Resolve UUID → metadados do manifesto
        cont = self._find_continent(uuid_or_name)
        nome = cont["nome"]
        bbox = cont["bounding_box"]
        cont_uuid = cont["uuid"]
        print(f"[ROI-ZOOM] Continente: {nome} | UUID: {cont_uuid}")
        print(f"[ROI-ZOOM] Bounding Box global: {bbox}")

        if bbox["max_x"] == 0 and bbox["max_y"] == 0:
            raise ValueError(
                f"Continente '{nome}' tem 0 pixels de terra no mapa global "
                "(possivelmente fora dos limites do mapa de 768x768). "
                "Regenere o mundo com 'generate_world.py'."
            )

        # 2. Carrega o mapa global e faz o crop
        global_map = self._load_global_map()
        crop = self._crop_global(bbox, global_map)
        print(f"[ROI-ZOOM] Recorte obtido: {crop.shape[1]}x{crop.shape[0]}px")

        # 3. Interpola para a resolução-alvo
        target = self.target_resolution
        upscaled = self._upscale(crop, target, target)
        print(f"[ROI-ZOOM] Interpolado para: {target}x{target}px")

        # 4. Injeção de micro-detalhes de alta frequência
        #    Usa um offset derivado do UUID para que cada continente tenha
        #    um relevo micro-detalhado único e reprodutível
        cont_seed_offset = abs(hash(cont_uuid)) % 40000
        refined = self._apply_micro_detail(upscaled, cont_seed_offset)
        print("[ROI-ZOOM] Micro-detalhes geológicos aplicados.")

        # 5. Recalcula clima e biomas na nova resolução
        min_y_global = max(0, bbox["min_y"] - self.BORDER_PADDING)
        final = self._recompute_climate_and_biomes(refined, offset_y_global=min_y_global)
        print("[ROI-ZOOM] Clima e biomas recalculados.")

        # 6. Persiste o resultado
        os.makedirs(self.output_dir, exist_ok=True)
        slug = nome.lower().replace(" ", "_")
        out_path = os.path.join(self.output_dir, f"mapa_{slug}.npz")
        np.savez_compressed(out_path, mapa=final, uuid=cont_uuid, nome=nome)
        print(f"[ROI-ZOOM] Mapa de zoom salvo em '{out_path}' ({final.shape[1]}x{final.shape[0]}px, 4 canais).")

        return os.path.abspath(out_path)
