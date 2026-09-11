"""
OrganicaModelo — radial degradado de propósito (F7, ESPEC_DESENHO_CIDADE.md). Herda de
`RadialModelo` (permitido e esperado, Seção 5.5/F7.1) e aplica quatro degradações sobre a
malha já pronta: irregularidade maior, anéis que não fecham, quadras faltando, radiais
tortas. Custo real: ~60 linhas sobre o radial, o melhor retorno por linha do documento.
"""
import math

from config import cfg_get
from .base import Rua
from .radial import RadialModelo


class OrganicaModelo(RadialModelo):
    nome = "organica"

    def __init__(self, sitio, config, rng):
        super().__init__(sitio, config, rng)
        # F7.1.1: irregularidade maior — muda só o PARÂMETRO que o radial já usa pra
        # perturbar vértice (self.irreg), não consome rng nenhum a mais.
        fator = cfg_get(config, "cidade_geo_organica_fator_irregularidade")
        self.irreg *= fator

    def construir_malha(self):
        malha = super().construir_malha()

        # F7.1.2: anéis que não fecham — cada `rua` tipo_via="anel" perde um arco
        # contíguo de 1 a 3 setores; a rua vira polilinha aberta, não um loop. As
        # quadras que dependiam daquele trecho continuam existindo (muda a rua, não a
        # quadra — simplificação aceita: ver o desvio no log de execução).
        malha.ruas = [self._abrir_anel(r) if r.tipo_via == "anel" else r for r in malha.ruas]

        # F7.1.4: radiais tortas — deslocamento lateral senoidal de baixa amplitude nos
        # pontos intermediários de cada radial.
        malha.ruas = [self._torcer_radial(r) if r.tipo_via == "radial" else r for r in malha.ruas]

        # F7.1.3: quadras faltando — uma fração sorteada da cidade vira chão livre (nem
        # quarteirão, nem lotes), não um buraco decidido setor a setor.
        fracao_vazias = self.rng.uniform(*cfg_get(self.cfg, "cidade_geo_organica_fracao_quadras_vazias"))
        malha.quadras = [q for q in malha.quadras if self.rng.random() >= fracao_vazias]

        return malha

    def _abrir_anel(self, rua):
        linha = rua.pontos[:-1]  # tira o ponto de fechamento duplicado (radial.py fecha o loop)
        n = len(linha)
        if n < 4:
            return rua  # anel pequeno demais pra abrir sem sumir
        gap_len = self.rng.randint(1, min(3, n - 2))
        gap_start = self.rng.randrange(n)
        mantidos = [linha[(gap_start + gap_len + i) % n] for i in range(n - gap_len)]
        return Rua(pontos=mantidos, classe_via=rua.classe_via, tipo_via=rua.tipo_via, indice=rua.indice)

    def _torcer_radial(self, rua):
        pontos = rua.pontos
        n = len(pontos)
        if n < 3:
            return rua
        amplitude = self.raio_m * 0.015
        fase = self.rng.uniform(0, 2 * math.pi)
        novos = [pontos[0]]
        for i in range(1, n - 1):
            p0, p1 = pontos[i - 1], pontos[i]
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            comprimento = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / comprimento, dx / comprimento
            offset = amplitude * math.sin(fase + i * 1.3)
            novos.append((p1[0] + nx * offset, p1[1] + ny * offset))
        novos.append(pontos[-1])
        return Rua(pontos=novos, classe_via=rua.classe_via, tipo_via=rua.tipo_via, indice=rua.indice)
