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
import zlib
import numpy as np
from cartographer.math import NoiseGenerator, ClimateProcessor
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get
from engine.logger import WorldLogger
try:
    from scipy.ndimage import zoom as scipy_zoom, gaussian_filter
except ImportError:
    scipy_zoom = None
    gaussian_filter = None



class ROIZoomGenerator:
    """
    Gerador de mapas de alta resolução por demanda para um continente específico.

    A ideia central é o refinamento progressivo:
    - O mapa global (768x768) é a 'verdade macro': define continentes e biomas.
    - O mapa de zoom (~3000x3000) herda essa verdade e adiciona micro-detalhes
      que só existem nessa escala, como fiordes, vales e crateras.
    """

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
            config:             Bloco config["cartografia"]. Se omitido, usa o
                                 config único do projeto (antes o default era um
                                 dict reduzido de 2 chaves, hardcoded aqui mesmo —
                                 mais uma cópia de nivel_mar/nivel_montanha).
        """
        self.manifest_path = manifest_path
        self.npz_path = npz_path
        self.output_dir = output_dir
        self.target_resolution = target_resolution
        self.seed = seed
        self.config = config if config is not None else CARTOGRAPHER_CONFIG

        # Padding em pixels no espaço global para incluir um pouco de oceano ao redor
        self.border_padding = cfg_get(self.config, "zoom_border_padding_px")

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
        min_x = max(0, bbox["min_x"] - self.border_padding)
        min_y = max(0, bbox["min_y"] - self.border_padding)
        max_x = min(W - 1, bbox["max_x"] + self.border_padding)
        max_y = min(H - 1, bbox["max_y"] + self.border_padding)

        # NumPy: eixo 0 = linhas = Y, eixo 1 = colunas = X
        return global_map[min_y : max_y + 1, min_x : max_x + 1, :]

    # ------------------------------------------------------------------
    # Interpolação (upscale)
    # ------------------------------------------------------------------

    @staticmethod
    def _upscale(crop: np.ndarray, target_h: int, target_w: int, ordem: int) -> np.ndarray:
        """
        Interpola cada canal do recorte para a resolução de destino.

        Usa scipy (spline de ordem `ordem` — 3 = bicúbica) se disponível; cai em
        interpolação bilinear manual em numpy puro caso contrário, com aviso de log
        (a qualidade do fallback é inferior — ver docs/ROADMAP.md, Frente 2).
        """
        if scipy_zoom is not None:
            # Fatores de escala por eixo (H e W) — canal 4 não é redimensionado
            fh = target_h / crop.shape[0]
            fw = target_w / crop.shape[1]
            return scipy_zoom(crop, (fh, fw, 1), order=ordem).astype(np.float32)
        else:
            WorldLogger.warning(
                "[ROI-ZOOM] scipy não está instalado — usando fallback bilinear manual "
                "(qualidade inferior à interpolação configurada). Instale 'scipy' "
                "(requirements.txt) para o resultado pretendido."
            )
            # Fallback manual sem scipy (sempre bilinear, independente de `ordem`)
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

    @staticmethod
    def _suavizar_altitude(upscaled: np.ndarray, sigma_px: float) -> np.ndarray:
        """
        Aplica um leve borrão gaussiano só no canal de altitude (canal 0), logo após o
        upscale e antes de qualquer máscara não-linear ou hillshading.

        Mesmo com interpolação bicúbica, pode sobrar uma sutilíssima estrutura de
        "célula" do pixel de baixa resolução original — invisível na altitude crua, mas
        amplificada pelas máscaras de `_apply_micro_detail` e pelo gradiente do
        hillshading num padrão de grade visível ("papel amassado"). Este passo garante
        que nenhuma estrutura residual sobreviva. Ver docs/ROADMAP.md, Frente 2.
        """
        if sigma_px <= 0:
            return upscaled

        resultado = upscaled.copy()
        if gaussian_filter is not None:
            resultado[:, :, 0] = gaussian_filter(upscaled[:, :, 0], sigma=sigma_px)
        else:
            # Fallback sem scipy: box blur simples via médias móveis cumulativas (numpy puro)
            k = max(1, int(round(sigma_px * 2)) | 1)  # tamanho de janela ímpar
            alt = upscaled[:, :, 0]
            pad = k // 2
            alt_pad = np.pad(alt, pad, mode="edge")
            cumsum = np.cumsum(np.cumsum(alt_pad, axis=0), axis=1)
            cumsum = np.pad(cumsum, ((1, 0), (1, 0)), mode="constant")
            H, W = alt.shape
            soma = (
                cumsum[k:k + H, k:k + W] - cumsum[0:H, k:k + W]
                - cumsum[k:k + H, 0:W] + cumsum[0:H, 0:W]
            )
            resultado[:, :, 0] = soma / (k * k)
        return resultado

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
            scale=self.config["zoom_micro_hf_escala"],
            octaves=self.config["zoom_micro_hf_oitavas"],
            seed=self.seed,
            offset=cont_seed_offset + 11111,
        )

        # Ruído de média frequência: vales e colinas regionais
        ruido_mf = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=self.config["zoom_micro_mf_escala"],
            octaves=self.config["zoom_micro_mf_oitavas"],
            seed=self.seed,
            offset=cont_seed_offset + 22222,
        )

        # Ruído composto normalizado em [-0.5, 0.5]
        ruido_composto = (
            self.config["zoom_micro_hf_peso"] * ruido_hf 
            + self.config["zoom_micro_mf_peso"] * ruido_mf
        ) - 0.5

        # Máscara de modulação: aplica mais detalhe onde há terra e altitude
        nivel_mar = self.config["nivel_mar"]
        alt_macro = upscaled[:, :, 0]
        # Normaliza a altitude acima do nível do mar para [0, 1]
        mask_terra = np.clip((alt_macro - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)

        # Máscara para evitar criar ilhas artificiais espúrias em oceano muito profundo.
        # Permite perturbação apenas perto da costa e na terra.
        profundidade_min = cfg_get(self.config, "zoom_costa_profundidade_min")
        profundidade_faixa = cfg_get(self.config, "zoom_costa_profundidade_faixa")
        mask_proxima_costa = np.clip((alt_macro - profundidade_min) / profundidade_faixa, 0.0, 1.0)

        # Amplitude do ruído: base constante na costa + modulação por altitude
        amplitude = mask_proxima_costa * (
            self.config["zoom_micro_amp_base"] 
            + mask_terra * self.config["zoom_micro_amp_terra"]
        )

        resultado = upscaled.copy()
        resultado[:, :, 0] = np.clip(alt_macro + ruido_composto * amplitude, 0.0, 1.0)
        return resultado

    # ------------------------------------------------------------------
    # Recálculo de clima e biomas na resolução de zoom
    # ------------------------------------------------------------------

    def _recompute_climate_and_biomes(self, data: np.ndarray, min_x_global: int, max_x_global: int, min_y_global: int, max_y_global: int) -> np.ndarray:
        """
        Classifica os biomas na resolução de zoom com base na altitude micro-detalhada
        e na temperatura/umidade herdadas e interpoladas do mapa global.
        Garante consistência perfeita e 100% de paridade com o Mapa Mundi.
        """
        result = data.copy()

        # Geramos a grade de coordenadas perfeitamente mapeadas no espaço global do mundo
        # para alinhar o ruído Perlin de dithering entre o Mapa Mundi e o Zoom
        H, W, _ = data.shape
        y_range = np.linspace(min_y_global, max_y_global, H, dtype=np.float32)
        x_range = np.linspace(min_x_global, max_x_global, W, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(x_range, y_range)

        result[:, :, 3] = ClimateProcessor.classify_biomes(
            data[:, :, 0], result[:, :, 1], result[:, :, 2], config=self.config,
            grid_x=grid_x, grid_y=grid_y, seed=self.seed
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
        ordem = cfg_get(self.config, "zoom_upscale_ordem")
        upscaled = self._upscale(crop, target, target, ordem)
        print(f"[ROI-ZOOM] Interpolado para: {target}x{target}px (ordem={ordem})")

        # 3.5. Suaviza a altitude para eliminar estrutura de célula residual do upscale
        # (causa raiz do artefato de "papel amassado" — Frente 2)
        sigma_px = cfg_get(self.config, "zoom_suavizacao_sigma_px")
        upscaled = self._suavizar_altitude(upscaled, sigma_px)

        # 4. Injeção de micro-detalhes de alta frequência
        #    Usa um offset derivado do UUID para que cada continente tenha
        #    um relevo micro-detalhado único e reprodutível.
        #    IMPORTANTE: usamos zlib.crc32 (determinístico) em vez de hash() nativo —
        #    hash() de string em Python é aleatorizado por processo (PYTHONHASHSEED),
        #    então o relevo mudava a cada regeneração do .npz (achado #7 da auditoria).
        cont_seed_offset = zlib.crc32(cont_uuid.encode("utf-8")) % 40000
        refined = self._apply_micro_detail(upscaled, cont_seed_offset)
        print("[ROI-ZOOM] Micro-detalhes geológicos aplicados.")

        # 5. Recalcula clima e biomas na nova resolução
        min_x_global = max(0, bbox["min_x"] - self.border_padding)
        max_x_global = min(global_map.shape[1] - 1, bbox["max_x"] + self.border_padding)
        min_y_global = max(0, bbox["min_y"] - self.border_padding)
        max_y_global = min(global_map.shape[0] - 1, bbox["max_y"] + self.border_padding)
        final = self._recompute_climate_and_biomes(
            refined, 
            min_x_global=min_x_global, 
            max_x_global=max_x_global, 
            min_y_global=min_y_global, 
            max_y_global=max_y_global
        )
        print("[ROI-ZOOM] Clima e biomas recalculados.")

        # 6. Persiste o resultado
        os.makedirs(self.output_dir, exist_ok=True)
        slug = nome.lower().replace(" ", "_")
        out_path = os.path.join(self.output_dir, f"mapa_{slug}.npz")
        np.savez_compressed(out_path, mapa=final, uuid=cont_uuid, nome=nome)
        print(f"[ROI-ZOOM] Mapa de zoom salvo em '{out_path}' ({final.shape[1]}x{final.shape[0]}px, 4 canais).")

        return os.path.abspath(out_path)
