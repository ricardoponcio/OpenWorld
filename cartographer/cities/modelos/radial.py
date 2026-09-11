"""
RadialModelo — o traçado de hoje (burgo medieval em anéis + radiais ao redor de um
mercado), movido pra cá pela refatoração do F4. A F4.7 exige que a saída seja BYTE A BYTE
igual à de antes da refatoração — nenhuma linha de matemática foi reescrita, só movida e
reembalada em `Malha`/`Quadra`/`Rua`.
"""
import math

import numpy as np

from config import cfg_get
from .base import ModeloCidade, Rua, Quadra, Malha


class RadialModelo(ModeloCidade):
    nome = "radial"

    def __init__(self, sitio, config, rng):
        super().__init__(sitio, config, rng)
        # ⚠️ Ordem de consumo do self.rng idêntica à do GeradorCidade de antes do F4
        # (raio -> anéis -> fator de lote -> setores) — mudar a ordem muda todas as
        # cidades do mundo, silenciosamente (Seção 10 item 1).
        faixa_raio = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(
            sitio.tamanho, [500.0, 500.0])
        self.raio_m = self.rng.uniform(*faixa_raio)
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(sitio.tamanho, 2)
        faixa_aneis = cfg_get(config, "cidade_geo_num_aneis_faixa_por_tamanho").get(
            sitio.tamanho, [2, 2])
        self.num_aneis = self.rng.randint(int(faixa_aneis[0]), int(faixa_aneis[1]))
        self.irreg = cfg_get(config, "cidade_geo_irregularidade_via")
        faixa_fator_cidade = cfg_get(config, "cidade_geo_lote_fator_cidade_faixa")
        self.lote_fator_cidade = self.rng.uniform(*faixa_fator_cidade)
        faixa_setores_por_portao = cfg_get(config, "cidade_geo_setores_por_portao_faixa")
        sorteio_setores = self.rng.uniform(*faixa_setores_por_portao)
        self.num_setores = max(self.num_portoes * 2, round(self.num_portoes * sorteio_setores))

        self.praca_fracao_nucleo = cfg_get(config, "cidade_geo_praca_fracao_nucleo")
        self.praca_raio_min = cfg_get(config, "cidade_geo_praca_raio_min_m")
        self.praca_raio_max = cfg_get(config, "cidade_geo_praca_raio_max_m")
        raio_banda0 = self.raio_m / (self.num_aneis + 1)
        self.praca_raio = min(self.praca_raio_max,
                               max(self.praca_raio_min, self.praca_fracao_nucleo * raio_banda0))
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")
        self.via_largura_por_classe = cfg_get(config, "cidade_via_largura_m_por_classe")

    # ------------------------------------------------------------------
    # Leitura de terreno local — mesma lógica de GeradorCidade._declividade_local, mas
    # lendo `self.sitio.terreno`/`raio_m` do próprio modelo (F4.2: o modelo não sabe de
    # `GeradorCidade`, só do `SitioCidade`).
    # ------------------------------------------------------------------
    def _indice_terreno(self, x_m, y_m):
        n = self.sitio.terreno.shape[0]
        lado_m = 2.0 * self.raio_m
        fx = (x_m + self.raio_m) / lado_m
        fy = (y_m + self.raio_m) / lado_m
        ix = int(np.clip(fx * n, 0, n - 1))
        iy = int(np.clip(fy * n, 0, n - 1))
        return iy, ix

    def _declividade_local(self, x_m, y_m):
        if self.sitio.terreno is None:
            return 0.0
        iy, ix = self._indice_terreno(x_m, y_m)
        m_por_celula = (2.0 * self.raio_m) / self.sitio.terreno.shape[0]
        return float(math.hypot(self.sitio.grad_x[iy, ix], self.sitio.grad_y[iy, ix]) / m_por_celula)

    @staticmethod
    def _polar(raio, angulo):
        return (raio * math.cos(angulo), raio * math.sin(angulo))

    def _distancia_faixa_dominio(self, classe):
        largura = self.via_largura_por_classe.get(classe, self.via_largura_por_classe.get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    def _classe_via_radial(self, indice_setor, setores_portao):
        return "principal" if indice_setor in setores_portao else "secundaria"

    def _melhor_centro_praca(self, raio_banda0):
        if self.sitio.terreno is None:
            return (0.0, 0.0)
        raio_disponivel = max(0.0, raio_banda0 - self.praca_raio) * 0.6
        if raio_disponivel <= 0.0:
            return (0.0, 0.0)
        melhor = (0.0, 0.0)
        melhor_declive = self._declividade_local(0.0, 0.0)
        n_candidatos = 12
        for k in range(n_candidatos):
            ang = 2 * math.pi * k / n_candidatos
            x, y = raio_disponivel * math.cos(ang), raio_disponivel * math.sin(ang)
            declive = self._declividade_local(x, y)
            if declive < melhor_declive:
                melhor_declive, melhor = declive, (x, y)
        return melhor

    # ------------------------------------------------------------------
    def construir_malha(self) -> Malha:
        angulos = [2 * math.pi * i / self.num_setores for i in range(self.num_setores)]
        raios_base = [self.raio_m * (j + 1) / (self.num_aneis + 1) for j in range(self.num_aneis)]

        perturb = self.np_rng.uniform(-1.0, 1.0, size=(self.num_aneis + 1, self.num_setores))

        vertices = []
        for j in range(self.num_aneis):
            raio_linha = []
            for i in range(self.num_setores):
                r = raios_base[j] * (1.0 + self.irreg * perturb[j, i])
                raio_linha.append(self._polar(r, angulos[i]))
            vertices.append(raio_linha)
        borda = []
        for i in range(self.num_setores):
            r = self.raio_m * (1.0 + self.irreg * 0.5 * perturb[self.num_aneis, i])
            borda.append(self._polar(r, angulos[i]))
        vertices.append(borda)

        passo = max(1, self.num_setores // self.num_portoes)

        def _rotacao_uniforme(deslocamento):
            return [(deslocamento + k * passo) % self.num_setores for k in range(self.num_portoes)]

        if self.sitio.terreno is not None:
            declividades = [self._declividade_local(*borda[i]) for i in range(self.num_setores)]
            ordem = sorted(range(self.num_setores), key=lambda i: declividades[i])
            espacamento_min = passo
            indices_portao = []
            for i in ordem:
                if all(min((i - j) % self.num_setores, (j - i) % self.num_setores) >= espacamento_min
                       for j in indices_portao):
                    indices_portao.append(i)
                if len(indices_portao) == self.num_portoes:
                    break
            if len(indices_portao) < self.num_portoes:
                indices_portao = min(
                    (_rotacao_uniforme(d) for d in range(passo)),
                    key=lambda ids: sum(declividades[i] for i in ids),
                )
        else:
            indices_portao = _rotacao_uniforme(0)
        setores_portao = set(indices_portao)

        # F1.2/F1.3: posiciona a praça primeiro, depois define o raio do núcleo cívico a
        # partir dela — garante por construção que a praça caiba dentro do núcleo.
        centro_praca = self._melhor_centro_praca(raios_base[0])
        raio_banda0 = raios_base[0]
        raio_nucleo_candidato = (math.hypot(*centro_praca) + self.praca_raio +
                                  self._distancia_faixa_dominio("anel"))
        nucleo_urbanizavel = raio_nucleo_candidato < raio_banda0 * 0.9
        nucleo = None
        raio_nucleo = 0.0
        ruas = []
        if nucleo_urbanizavel:
            raio_nucleo = raio_nucleo_candidato
            perturb_nucleo = self.np_rng.uniform(-1.0, 1.0, size=self.num_setores)
            nucleo = [self._polar(raio_nucleo * (1.0 + self.irreg * perturb_nucleo[i]), angulos[i])
                      for i in range(self.num_setores)]
            ruas.append(Rua(pontos=nucleo + [nucleo[0]], classe_via="anel", tipo_via="anel", indice=-1))

        for j, linha in enumerate(vertices):
            ruas.append(Rua(pontos=linha + [linha[0]], classe_via="anel", tipo_via="anel", indice=j))
        for i in range(self.num_setores):
            origem = nucleo[i] if nucleo is not None else (0.0, 0.0)
            pontos = [origem] + [vertices[j][i] for j in range(self.num_aneis + 1)]
            classe = "principal" if i in setores_portao else "secundaria"
            ruas.append(Rua(pontos=pontos, classe_via=classe, tipo_via="radial", indice=i))

        portoes = [(borda[i][0], borda[i][1], f"Portão de {self.sitio.nome} #{i}") for i in indices_portao]

        # Quadras — banda 0 (núcleo, se urbanizável) até num_aneis (borda). Vertices e
        # classes_aresta crus, SEM inset — GeradorCidade._gerar_quarteiroes_e_lotes é
        # quem encolhe pela faixa de domínio (F4.4: "o que não é gancho mora na base").
        quadras = []
        banda_inicial = 0 if nucleo_urbanizavel else 1
        for j in range(banda_inicial, self.num_aneis + 1):
            raio_interno = nucleo if j == 0 else vertices[j - 1]
            raio_externo = vertices[j]
            if j == 0:
                bairro = "Núcleo"
            elif j == 1:
                bairro = "Centro"
            elif j < self.num_aneis:
                bairro = "Bairro Médio"
            else:
                bairro = "Bairro Externo"
            for i in range(self.num_setores):
                i2 = (i + 1) % self.num_setores
                quad = [raio_interno[i], raio_externo[i], raio_externo[i2], raio_interno[i2]]
                classes_aresta = [
                    self._classe_via_radial(i, setores_portao),
                    "anel",
                    self._classe_via_radial(i2, setores_portao),
                    "anel",
                ]
                quadras.append(Quadra(vertices=quad, classes_aresta=classes_aresta,
                                       banda=j, bairro=bairro, id=(j, i)))

        # Muralha + torres — sempre computadas (custam pouco: um np_rng.uniform), mesmo
        # quando `precisa_muralha()` vai acabar não usando; GeradorCidade decide se
        # emite. Isso preserva a ordem de consumo do np_rng idêntica à de antes do F4
        # (perturb -> perturb_nucleo -> perturb_muralha), sem precisar saber aqui se a
        # cidade vai ter muralha ou não (essa pergunta é o gancho `precisa_muralha`).
        folga = cfg_get(self.cfg, "cidade_geo_muralha_folga_m")
        espacamento_torres = cfg_get(self.cfg, "cidade_geo_muralha_torres_espacamento_m")
        raio_muralha = self.raio_m + folga
        perturb_muralha = self.np_rng.uniform(-1.0, 1.0, size=self.num_setores)
        contorno = [self._polar(raio_muralha * (1.0 + self.irreg * 0.3 * perturb_muralha[i]), angulos[i])
                    for i in range(self.num_setores)]
        perimetro = raio_muralha * 2 * math.pi
        num_torres = max(4, int(perimetro / max(1.0, espacamento_torres)))
        torres = [self._polar(raio_muralha, 2 * math.pi * k / num_torres) for k in range(num_torres)]

        return Malha(ruas=ruas, quadras=quadras, portoes=portoes, centro_praca=centro_praca,
                     raio_praca=self.praca_raio, raio_nucleo=raio_nucleo,
                     num_bandas=self.num_aneis + 1, contorno=contorno, torres=torres)
