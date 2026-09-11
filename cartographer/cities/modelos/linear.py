"""
LinearModelo — vila de beira de estrada (F6, ESPEC_DESENHO_CIDADE.md). Uma rua principal
atravessando a cidade, quadras só nas laterais, cidade comprida e estreita. É o modelo que
mais prova a interface: não tem banda nem setor — tem "fileira" e "posição ao longo do
eixo" — e ainda assim responde às mesmas 7 perguntas que `radial`/`grade`.
"""
import math

from config import cfg_get
from .base import ModeloCidade, Rua, Quadra, Malha


class LinearModelo(ModeloCidade):
    nome = "linear"

    def __init__(self, sitio, config, rng):
        super().__init__(sitio, config, rng)
        faixa_raio = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(
            sitio.tamanho, [500.0, 500.0])
        self.raio_m = self.rng.uniform(*faixa_raio)
        faixa_fator_cidade = cfg_get(config, "cidade_geo_lote_fator_cidade_faixa")
        self.lote_fator_cidade = self.rng.uniform(*faixa_fator_cidade)
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(sitio.tamanho, 2)
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")

    def _distancia_faixa_dominio(self, classe):
        largura = cfg_get(self.cfg, "cidade_via_largura_m_por_classe").get(
            classe, cfg_get(self.cfg, "cidade_via_largura_m_por_classe").get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    # --- gancho 2: "fileira 0" não é "banda 0" ---------------------------------------
    def zona_de(self, quadra):
        fileira = quadra.extra.get("fileira", 0)
        k = quadra.extra.get("k_fileiras", 1)
        if fileira == 0:
            return "centro"
        if fileira >= k - 1:
            return "borda"
        return "meio"

    # --- gancho 6: cidade linear com muralha circular ficaria estranha --------------
    def precisa_muralha(self):
        return False

    # ------------------------------------------------------------------
    def construir_malha(self) -> Malha:
        theta = self.rng.uniform(0, 2 * math.pi)
        curvatura = cfg_get(self.cfg, "cidade_geo_linear_curvatura")
        comprimento = 2.0 * self.raio_m
        faixa_largura = cfg_get(self.cfg, "cidade_geo_linear_largura_quadra_m_faixa")
        comprimento_celula = self.rng.uniform(*faixa_largura)
        n_segmentos = max(5, round(comprimento / comprimento_celula))
        faixa_profundidade_k = cfg_get(self.cfg, "cidade_geo_linear_profundidade_faixas")
        k = self.rng.randint(int(faixa_profundidade_k[0]), int(faixa_profundidade_k[1]))
        profundidades = [self.rng.uniform(*faixa_largura) for _ in range(k)]
        # F6.3 (aceite): "razão comprimento/largura entre 2,5 e 6,0". Sem isto, uma
        # cidade pequena com k=3 fileiras de ~90m cada (faixa_largura reaproveitada pra
        # profundidade) fica quase quadrada — a largura (2 lados × k fileiras) cresce
        # sem relação nenhuma com o comprimento do eixo. Limita a largura total a uma
        # fração do comprimento, escalando as fileiras proporcionalmente se preciso.
        largura_total = 2.0 * sum(profundidades)
        limite = comprimento * 0.20
        if largura_total > limite:
            fator = limite / largura_total
            # Piso: abaixo de ~25 m a fileira não sobra espaço pro inset da via
            # principal (8,5 m) + da viela de fundo (6,5 m) — o quad degenera inteiro no
            # encolhimento e a fileira 0 desaparece da cidade (achado testando
            # Tormirstead: 0% dos lotes em banda 1, quando o alvo do F6.3 é > 50%).
            profundidades = [max(p * fator, 25.0) for p in profundidades]
        prof_acumulada = [0.0]
        for p in profundidades:
            prof_acumulada.append(prof_acumulada[-1] + p)

        cos_t, sin_t = math.cos(theta), math.sin(theta)
        nx, ny = -sin_t, cos_t  # normal ao eixo (aproximação: mesma normal ao longo de toda a curva)

        def ponto_eixo(t):
            desvio = curvatura * comprimento * math.sin(2 * math.pi * t)
            along = (t - 0.5) * comprimento
            return (along * cos_t + desvio * nx, along * sin_t + desvio * ny)

        eixo_pontos = [ponto_eixo(i / n_segmentos) for i in range(n_segmentos + 1)]

        ruas = [Rua(pontos=list(eixo_pontos), classe_via="principal", tipo_via="eixo", indice=0)]

        extremidade = min(2, max(0, n_segmentos // 4))

        def k_no_segmento(i):
            """F6.1.7 — afunilamento: as pontas do eixo ficam com 1 fileira só."""
            if i < extremidade or i >= n_segmentos - extremidade:
                return 1
            return k

        # Praça: substitui uma quadra da fileira 0, perto do meio do eixo.
        seg_praca = n_segmentos // 2
        lado_praca = 1  # lado positivo (a normal) — arbitrário, só precisa ser consistente

        quadras = []
        for i in range(n_segmentos):
            k_aqui = k_no_segmento(i)
            p0, p1 = eixo_pontos[i], eixo_pontos[i + 1]
            # Rua transversal no corte, atravessando as fileiras dos dois lados.
            prof_max = prof_acumulada[k_aqui]
            transversal = [(p0[0] - lado * nx * prof_max, p0[1] - lado * ny * prof_max)
                           for lado in (1, -1)]
            ruas.append(Rua(pontos=transversal, classe_via="secundaria", tipo_via="transversal", indice=i))

            for lado in (1, -1):
                for f in range(k_aqui):
                    if i == seg_praca and lado == lado_praca and f == 0:
                        continue  # vira praça, não quadra
                    d0, d1 = prof_acumulada[f], prof_acumulada[f + 1]
                    v0 = (p0[0] + lado * nx * d0, p0[1] + lado * ny * d0)
                    v1 = (p1[0] + lado * nx * d0, p1[1] + lado * ny * d0)
                    v2 = (p1[0] + lado * nx * d1, p1[1] + lado * ny * d1)
                    v3 = (p0[0] + lado * nx * d1, p0[1] + lado * ny * d1)
                    # v0->v1->v2->v3 é sempre um retângulo simples (bordo do segmento,
                    # sobe até d1, volta, desce até d0) — a orientação (horário/anti-
                    # horário) muda com o sinal de `lado`, mas _encolher_quad não exige
                    # uma orientação global, só consistência entre original e encolhido.
                    quad = [v0, v1, v2, v3]
                    classe_fundo = "anel" if f == k_aqui - 1 else "servico"
                    classes_aresta = ["principal" if f == 0 else "servico", "secundaria",
                                       classe_fundo, "secundaria"]
                    if lado < 0:
                        classes_aresta = [classes_aresta[0], classes_aresta[3],
                                           classes_aresta[2], classes_aresta[1]]
                    quadras.append(Quadra(vertices=quad, classes_aresta=classes_aresta,
                                           banda=f + 1, bairro=("Beira da Estrada" if f == 0 else "Fundos"),
                                           id=(i, lado, f), extra={"fileira": f, "k_fileiras": k_aqui}))

            # Vielas de fundo — uma por fileira interna (entre f e f+1), de cada lado.
            for lado in (1, -1):
                for f in range(k_aqui - 1):
                    d = prof_acumulada[f + 1]
                    va = (p0[0] + lado * nx * d, p0[1] + lado * ny * d)
                    vb = (p1[0] + lado * nx * d, p1[1] + lado * ny * d)
                    ruas.append(Rua(pontos=[va, vb], classe_via="anel", tipo_via="servico", indice=1000 + i))

        pc = eixo_pontos[seg_praca]
        pc1 = eixo_pontos[seg_praca + 1]
        meio_segmento = ((pc[0] + pc1[0]) / 2.0, (pc[1] + pc1[1]) / 2.0)
        prof0 = profundidades[0] if profundidades else 20.0
        centro_praca = (meio_segmento[0] + lado_praca * nx * prof0 / 2.0,
                         meio_segmento[1] + lado_praca * ny * prof0 / 2.0)
        raio_praca = max(10.0, min(comprimento_celula, prof0) / 2.0 -
                          self._distancia_faixa_dominio("secundaria"))

        portoes = [(eixo_pontos[0][0], eixo_pontos[0][1], f"Portão de {self.sitio.nome} #0"),
                   (eixo_pontos[-1][0], eixo_pontos[-1][1], f"Portão de {self.sitio.nome} #1")][:self.num_portoes]

        # Contorno: envelope das quadras mantidas (ordem ao longo do eixo, lado +1 na ida
        # e lado -1 na volta — um polígono simples sem auto-interseção).
        prof_max_geral = prof_acumulada[-1] if prof_acumulada else 20.0
        contorno = []
        for i in range(n_segmentos + 1):
            p = eixo_pontos[i]
            contorno.append((p[0] + nx * prof_max_geral, p[1] + ny * prof_max_geral))
        for i in range(n_segmentos, -1, -1):
            p = eixo_pontos[i]
            contorno.append((p[0] - nx * prof_max_geral, p[1] - ny * prof_max_geral))

        return Malha(ruas=ruas, quadras=quadras, portoes=portoes, centro_praca=centro_praca,
                     raio_praca=raio_praca, raio_nucleo=prof0, num_bandas=k + 1,
                     contorno=contorno, torres=[])
