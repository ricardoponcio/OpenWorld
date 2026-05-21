"""
MODULE: city_roi_zoom.py
FUNÇÃO: Geração de Mapa de Zoom por Demanda para uma Cidade (City ROI Zoom).
DESCRIÇÃO:
    Localiza a cidade pelo nome no world_manifest.json, pega suas coordenadas globais (x_global, y_global),
    recorta um pequeno raio no mapa_composto.npz, interpola para alta resolução e aplica ruído
    para gerar o mapa base de relevo da cidade.
"""
import json
import os
import numpy as np
import sys

# Setup sys.path for cartographer module
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from cartographer.math import NoiseGenerator, ClimateProcessor
from cartographer.config import CARTOGRAPHER_CONFIG
try:
    from scipy.ndimage import zoom as scipy_zoom
except ImportError:
    scipy_zoom = None

class CityROIZoomGenerator:
    def __init__(
        self,
        manifest_path: str = "database/world_manifest.json",
        npz_path: str = "database/mapa_composto.npz",
        output_dir: str = "database/cidades",
        target_resolution: int = 800,
        seed: int = 1337,
    ):
        self.manifest_path = os.path.abspath(manifest_path)
        self.npz_path = os.path.abspath(npz_path)
        self.output_dir = os.path.abspath(output_dir)
        self.target_resolution = target_resolution
        self.seed = seed
        self.config = CARTOGRAPHER_CONFIG
        self._manifest = self._load_manifest()
        self._global_map = None

    def _load_manifest(self) -> dict:
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Manifesto não encontrado em '{self.manifest_path}'.")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_global_map(self) -> np.ndarray:
        if self._global_map is None:
            if not os.path.exists(self.npz_path):
                raise FileNotFoundError(f"Mapa global não encontrado em '{self.npz_path}'.")
            data = np.load(self.npz_path)
            self._global_map = data["mapa"]
        return self._global_map

    def _find_city(self, city_name: str) -> dict:
        needle = city_name.strip().lower()
        for cont in self._manifest.get("continentes", []):
            for cid in cont.get("cidades", []):
                if cid["nome"].lower() == needle:
                    # Anexar informações do continente à cidade
                    cid["continente_uuid"] = cont["uuid"]
                    cid["continente_nome"] = cont["nome"]
                    return cid
        raise ValueError(f"Cidade '{city_name}' não encontrada no manifesto.")

    def _crop_global(self, cx: int, cy: int, radius: int, global_map: np.ndarray) -> np.ndarray:
        H, W, _ = global_map.shape
        min_x = max(0, cx - radius)
        min_y = max(0, cy - radius)
        max_x = min(W - 1, cx + radius)
        max_y = min(H - 1, cy + radius)
        return global_map[min_y : max_y + 1, min_x : max_x + 1, :]

    def _upscale(self, crop: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
        if scipy_zoom is not None:
            fh = target_h / crop.shape[0]
            fw = target_w / crop.shape[1]
            return scipy_zoom(crop, (fh, fw, 1), order=1).astype(np.float32)
        else:
            # Fallback manual sem scipy
            out = np.zeros((target_h, target_w, crop.shape[2]), dtype=np.float32)
            for c in range(crop.shape[2]):
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

    def _apply_micro_detail(self, upscaled: np.ndarray, seed_offset: int) -> np.ndarray:
        H, W, _ = upscaled.shape
        y_range = np.arange(H, dtype=np.float32)
        x_range = np.arange(W, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(x_range, y_range)

        ruido_hf = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=80.0,
            octaves=2,
            seed=self.seed,
            offset=seed_offset + 9999,
        )

        ruido_composto = ruido_hf - 0.5
        amplitude = 0.015
        
        resultado = upscaled.copy()
        resultado[:, :, 0] = np.clip(upscaled[:, :, 0] + ruido_composto * amplitude, 0.0, 1.0)
        return resultado

    def generate(self, city_name: str) -> str:
        print(f"[CITY-ZOOM] Gerando mapa de zoom para cidade: '{city_name}'")
        cid = self._find_city(city_name)
        
        cx, cy = cid["x_global"], cid["y_global"]
        print(f"[CITY-ZOOM] Coordenadas Globais: ({cx}, {cy})")

        global_map = self._load_global_map()
        # Corta um raio de 1 pixel em volta do ponto (ou seja, matriz 3x3 global)
        crop = self._crop_global(cx, cy, 2, global_map) 
        
        target = self.target_resolution
        upscaled = self._upscale(crop, target, target)
        
        seed_offset = abs(hash(cid["nome"])) % 40000
        final = self._apply_micro_detail(upscaled, seed_offset)

        # Não recalculamos clima para evitar distorções microscópicas; herdamos e suavizamos
        # o bioma predominante da célula global usando nearest_neighbor na renderização

        os.makedirs(self.output_dir, exist_ok=True)
        slug = cid["nome"].lower().replace(" ", "_")
        out_path = os.path.join(self.output_dir, f"mapa_{slug}.npz")
        np.savez_compressed(out_path, mapa=final, nome=cid["nome"], continente_nome=cid["continente_nome"])
        print(f"[CITY-ZOOM] Mapa salvo em '{out_path}' ({target}x{target}px).")

        return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 city_roi_zoom.py <nome_da_cidade>")
        sys.exit(1)
        
    gen = CityROIZoomGenerator()
    gen.generate(sys.argv[1])
