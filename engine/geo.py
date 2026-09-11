import os
import math
import random as random_module
from typing import List


class GeoUtils:
    """
    Fase 2.1 (P0.3): `Local.coordenadas` é coordenada de MUNDO (pixel, Seção 2.3 do
    plano), não mais um par aleatório 5–35. Centralizado aqui porque três lugares
    criam `Local` novo depois do povoamento inicial (builder/populate.py,
    engine/mechanics/housing.py — expansão urbana, engine/mechanics/mestre.py — Modo
    Mestre) e todos têm que sortear na mesma convenção, senão um local nasce em
    coordenada de mundo e outro na grade antiga — exatamente a inconsistência que esta
    fase existe pra eliminar.

    ⚠️ Paliativo consciente (documentado na Seção 2.1 do plano): espalhar edifícios num
    raio de poucos pixels de mundo é espalhá-los por dezenas de km — fisicamente
    absurdo, visualmente aceitável até a Fase 4 (cidade como geometria vetorial real).
    """
    _mapa_cache = None
    _mapa_cache_mtime = None

    @staticmethod
    def _carregar_mapa(caminho: str = "database/mapa_composto.npz"):
        import numpy as np
        mtime = os.path.getmtime(caminho) if os.path.exists(caminho) else None
        if GeoUtils._mapa_cache is None or GeoUtils._mapa_cache_mtime != mtime:
            GeoUtils._mapa_cache = np.load(caminho)["mapa"]
            GeoUtils._mapa_cache_mtime = mtime
        return GeoUtils._mapa_cache

    @staticmethod
    def sortear_ponto_em_terra(cx: float, cy: float, raio: float, nivel_mar: float,
                                rng=None, tentativas: int = 200) -> List[float]:
        """
        Sorteia um ponto uniforme no disco de raio `raio` (em px de mundo) ao redor de
        `(cx, cy)`, rejeitando pontos em água. Cai de volta no próprio `(cx, cy)` se
        `tentativas` esgotar sem achar terra (ex.: cidade cercada de água rasa demais).
        """
        rng = rng or random_module
        try:
            mapa = GeoUtils._carregar_mapa()
        except FileNotFoundError:
            return [float(cx), float(cy)]

        for _ in range(tentativas):
            ang = rng.uniform(0, 2 * math.pi)
            r = raio * math.sqrt(rng.random())
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            ix, iy = int(round(x)), int(round(y))
            if 0 <= ix < mapa.shape[1] and 0 <= iy < mapa.shape[0] and mapa[iy, ix, 0] >= nivel_mar:
                return [round(float(x), 3), round(float(y), 3)]
        return [float(cx), float(cy)]
