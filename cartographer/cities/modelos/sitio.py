"""
SitioCidade — os dados de posição/geografia/clima que todo modelo de cidade recebe
(09_ESPEC_DESENHO_CIDADE.md F4.2). Medido UMA VEZ por cidade, antes de instanciar o modelo,
e passado pronto — nenhum modelo chama `obter_cartografo()` nem lê `mapa_composto.npz`
diretamente.

Armadilha de determinismo (F4.6/Seção 10.1): `SitioCidade.medir()` precisa do RAIO da
cidade pra saber que janela de terreno amostrar, mas o raio real só é conhecido DEPOIS
que o modelo existe — desde R01 (docs/13_PLANO_POPULACAO_E_ESCALA.md, Bloco R) ele é
DERIVADO do número de domicílios sorteado (`escala.py:raio_para_lotes`), não mais
sorteado direto. A saída: a janela usa o TETO de `faixa_raio_m` (não mais uma amostra
do rng) — seguro por construção, porque `raio_para_lotes` sempre grampeia o raio
derivado dentro dessa mesma faixa, então o teto nunca é menor que o raio final.
"""
import os
import math
import zlib
from dataclasses import dataclass
from typing import Optional

import numpy as np

from cartographer.tiles.render import obter_cartografo
from cartographer.cities.escala import metros_por_pixel_mundo, faixa_raio_m
from config import cfg_get

NPZ_PATH = "database/mapa_composto.npz"

_agua_cache = None  # (xs, ys) em px de mundo — carregado uma vez, reusado por toda cidade


def _pixels_de_agua(config):
    global _agua_cache
    if _agua_cache is None:
        if not os.path.exists(NPZ_PATH):
            _agua_cache = (np.array([]), np.array([]))
        else:
            alt = np.load(NPZ_PATH)["mapa"][:, :, 0]
            nivel_mar = cfg_get(config, "nivel_mar")
            ys, xs = np.nonzero(alt <= nivel_mar)
            _agua_cache = (xs.astype(np.float64), ys.astype(np.float64))
    return _agua_cache


@dataclass(frozen=True)
class SitioCidade:
    # identidade (vem do manifesto — Regra 9: nada é acrescentado lá)
    nome: str
    tamanho: str
    tipo: str
    continente: str
    seed: int  # zlib.crc32(nome) — NUNCA hash()

    # posição
    x_mundo: float
    y_mundo: float
    metros_por_px: float

    # geografia/clima, da janela amostrada em medir() (Seção 4.2)
    altitude_media: float
    temperatura_media: float
    umidade_media: float
    bioma_dominante: int
    terreno: Optional[np.ndarray]  # canal 0 da janela, 128x128
    grad_x: Optional[np.ndarray]
    grad_y: Optional[np.ndarray]
    # G06 (armadilha 4, docs/12_PLANO_CIDADE_VIVA.md): meia-largura REAL da janela de
    # terreno, em metros — maior que raio_m (cidade_geo_janela_terreno_fator), pra dar
    # margem pro Bloco X ler terreno fora da muralha sem cair no np.clip silencioso que
    # devolvia a célula da borda pra qualquer ponto fora da cidade original.
    raio_janela_m: float

    # água (hoje sempre longe — Seção 4.3/4.7; entra agora pro futuro não exigir refatoração)
    distancia_agua_m: float
    direcao_agua_rad: float

    @staticmethod
    def medir(cidade: dict, continente_nome: str, config: dict) -> "SitioCidade":
        nome = cidade["nome"]
        tamanho = cidade.get("tamanho", "pequeno").lower()
        tipo = cidade.get("tipo", "").lower()
        seed = zlib.crc32(nome.encode("utf-8"))
        x_mundo = float(cidade["x_global"])
        y_mundo = float(cidade["y_global"])
        metros_por_px = metros_por_pixel_mundo(config)

        # R01 (docs/13_PLANO_POPULACAO_E_ESCALA.md, Bloco R): o raio real só é conhecido
        # DEPOIS do modelo existir (é derivado do número de domicílios sorteado, não
        # mais sorteado direto — `raio_para_lotes`). Dimensionar a janela de terreno
        # com o TETO de `faixa_raio_m` (não mais uma amostra provisória do rng) é
        # seguro por construção: `raio_para_lotes` sempre GRAMPEIA o raio derivado
        # dentro dessa mesma faixa, então o teto nunca é menor que o raio final —
        # a janela nunca fica pequena demais (G06/Q04, docs/12_PLANO_CIDADE_VIVA.md).
        _, teto_raio_m = faixa_raio_m(config, tamanho)
        fator_janela = cfg_get(config, "cidade_geo_janela_terreno_fator")
        raio_janela_m = teto_raio_m * fator_janela

        terreno = grad_x = grad_y = None
        altitude_media = temperatura_media = umidade_media = 0.0
        bioma_dominante = 0
        cartografo = obter_cartografo()
        if cartografo is not None:
            lado_px = 2.0 * raio_janela_m / metros_por_px
            janela = cartografo.gerar_janela(
                x_mundo - lado_px / 2, y_mundo - lado_px / 2,
                x_mundo + lado_px / 2, y_mundo + lado_px / 2,
                128, 128,
                oitavas_extra=cfg_get(config, "tile_oitavas_max") - cfg_get(config, "ruido_macro_oitavas"),
            )
            terreno = janela[:, :, 0]
            grad_y, grad_x = np.gradient(terreno)
            altitude_media = float(janela[:, :, 0].mean())
            temperatura_media = float(janela[:, :, 1].mean())
            umidade_media = float(janela[:, :, 2].mean())
            bioma_dominante = int(round(float(janela[:, :, 3].mean())))

        xs, ys = _pixels_de_agua(config)
        if xs.size > 0:
            dd = (xs - x_mundo) ** 2 + (ys - y_mundo) ** 2
            i = int(np.argmin(dd))
            distancia_agua_m = math.sqrt(float(dd[i])) * metros_por_px
            direcao_agua_rad = math.atan2(ys[i] - y_mundo, xs[i] - x_mundo)
        else:
            distancia_agua_m = float("inf")
            direcao_agua_rad = 0.0

        return SitioCidade(
            nome=nome, tamanho=tamanho, tipo=tipo, continente=continente_nome, seed=seed,
            x_mundo=x_mundo, y_mundo=y_mundo, metros_por_px=metros_por_px,
            altitude_media=altitude_media, temperatura_media=temperatura_media,
            umidade_media=umidade_media, bioma_dominante=bioma_dominante,
            terreno=terreno, grad_x=grad_x, grad_y=grad_y, raio_janela_m=raio_janela_m,
            distancia_agua_m=distancia_agua_m, direcao_agua_rad=direcao_agua_rad,
        )

    # ------------------------------------------------------------------
    # G06: o sítio é o dono do terreno — nem modelo nem gerador precisam saber como a
    # grade é indexada (11_ARQUITETURA.md P1). Substitui os dois `_indice_terreno`
    # idênticos que existiam em radial.py e generate_city_geometry.py.
    # ------------------------------------------------------------------
    def _indice(self, x_m: float, y_m: float):
        """`None` quando o ponto cai FORA da janela amostrada — o chamador decide (nunca
        0 silencioso, nunca a célula da borda). Antes disto era `np.clip`, que fazia toda
        checagem de terreno fora da cidade original dar a mesma resposta (armadilha 4)."""
        if self.terreno is None:
            return None
        n = self.terreno.shape[0]
        lado_m = 2.0 * self.raio_janela_m
        fx = (x_m + self.raio_janela_m) / lado_m
        fy = (y_m + self.raio_janela_m) / lado_m
        if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
            return None
        ix = min(int(fx * n), n - 1)
        iy = min(int(fy * n), n - 1)
        return iy, ix

    def altitude_em(self, x_m: float, y_m: float) -> Optional[float]:
        indice = self._indice(x_m, y_m)
        if indice is None:
            return None
        iy, ix = indice
        return float(self.terreno[iy, ix])

    def declividade_em(self, x_m: float, y_m: float) -> Optional[float]:
        indice = self._indice(x_m, y_m)
        if indice is None:
            return None
        iy, ix = indice
        m_por_celula = (2.0 * self.raio_janela_m) / self.terreno.shape[0]
        return float(math.hypot(self.grad_x[iy, ix], self.grad_y[iy, ix]) / m_por_celula)
