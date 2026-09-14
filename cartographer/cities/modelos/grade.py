"""
GradeModelo — colônia romana / cidade planejada (F5, 09_ESPEC_DESENHO_CIDADE.md). Ruas retas
cruzando em ângulo reto, quadras retangulares, cardo+decumanus (as duas avenidas centrais)
cruzando na praça. É o contraste mais forte contra o `radial` — por isso o primeiro modelo
novo a entrar.
"""
import math

from config import cfg_get
from .base import ModeloCidade, Rua, Quadra, Malha, pontos_ao_longo_do_poligono, derivar_ou_forcar_raio


class GradeModelo(ModeloCidade):
    nome = "grade"

    def __init__(self, sitio, config, rng, raio_m_forcado=None):
        super().__init__(sitio, config, rng)  # roda ajustar_por_sitio (calibra self.lado_faixa)
        # R01 (docs/13_PLANO_POPULACAO_E_ESCALA.md, Bloco R): raio derivado de
        # domicílios, não mais sorteado direto — mesmo raciocínio de radial.py.
        self.raio_m, self.lotes_alvo = derivar_ou_forcar_raio(
            sitio, config, self.rng, raio_m_forcado, self.nome)
        faixa_fator_cidade = cfg_get(config, "cidade_geo_lote_fator_cidade_faixa")
        self.lote_fator_cidade = self.rng.uniform(*faixa_fator_cidade)
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(sitio.tamanho, 2)
        self.irreg = cfg_get(config, "cidade_geo_irregularidade_via")
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")

    # --- gancho 0: F5.2, o primeiro uso real do clima -------------------------------
    def ajustar_por_sitio(self):
        """Cidade de clima seco (umidade abaixo do limiar) tem quadra maior — pátio
        interno grande e rua na sombra, como se constrói em clima seco de verdade.
        ⚠️ Não sorteia nada (Seção 10 item 10) — só lê o sítio e ajusta a faixa."""
        faixa = list(cfg_get(self.cfg, "cidade_geo_grade_lado_quadra_m_faixa"))
        seco = self.sitio.umidade_media < cfg_get(self.cfg, "cidade_geo_umidade_limiar_seco")
        if seco:
            fator = cfg_get(self.cfg, "cidade_geo_grade_fator_lado_seco")
            faixa = [v * fator for v in faixa]
        self.lado_faixa = faixa

    def _distancia_faixa_dominio(self, classe):
        largura = cfg_get(self.cfg, "cidade_via_largura_m_por_classe").get(
            classe, cfg_get(self.cfg, "cidade_via_largura_m_por_classe").get("secundaria", 5.0))
        return largura / 2.0 + self.recuo_rua

    # ------------------------------------------------------------------
    def construir_malha(self) -> Malha:
        theta = self.rng.uniform(0, math.pi / 2)
        lado = self.rng.uniform(*self.lado_faixa)
        n = 2 * math.ceil(self.raio_m / lado)
        if n % 2 == 0:
            n += 1  # força ímpar — existe célula central exata
        centro_idx = (n - 1) // 2
        jitter = cfg_get(self.cfg, "cidade_geo_grade_jitter_m")
        avenida_a_cada_n = cfg_get(self.cfg, "cidade_geo_grade_avenida_a_cada_n")

        jitter_arr = self.np_rng.uniform(-1.0, 1.0, size=(n + 1, n + 1, 2))
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        meio = n / 2.0

        def vertice(row, col):
            x = (col - meio) * lado
            y = (row - meio) * lado
            na_borda = row in (0, n) or col in (0, n)
            fator_jitter = jitter * (1.8 if na_borda else 1.0)
            jx, jy = jitter_arr[row, col]
            x += jx * fator_jitter
            y += jy * fator_jitter
            return (x * cos_t - y * sin_t, x * sin_t + y * cos_t)

        pontos = [[vertice(r, c) for c in range(n + 1)] for r in range(n + 1)]

        # Silhueta orgânica: o mesmo "raio perturbado" do radial, mas como função
        # contínua do ângulo (a grade não tem setor discreto) — algumas âncoras
        # sorteadas com np_rng, interpoladas pelo vizinho mais próximo.
        n_ancoras = 24
        perturb_raio = self.np_rng.uniform(-1.0, 1.0, size=n_ancoras)

        def raio_silhueta(ang):
            idx = int((ang % (2 * math.pi)) / (2 * math.pi) * n_ancoras) % n_ancoras
            return self.raio_m * (1.0 + self.irreg * 0.5 * perturb_raio[idx])

        linhas_centrais = {centro_idx, centro_idx + 1}

        def classe_da_linha(idx):
            if idx in linhas_centrais:
                return "principal"
            if idx % avenida_a_cada_n == 0:
                return "anel"
            return "secundaria"

        def tipo_via_da_linha(idx):
            return "eixo" if idx in linhas_centrais else "transversal"

        ruas = []
        for row in range(n + 1):
            ruas.append(Rua(pontos=[pontos[row][c] for c in range(n + 1)],
                             classe_via=classe_da_linha(row), tipo_via=tipo_via_da_linha(row), indice=row))
        for col in range(n + 1):
            ruas.append(Rua(pontos=[pontos[r][col] for r in range(n + 1)],
                             classe_via=classe_da_linha(col), tipo_via=tipo_via_da_linha(col),
                             indice=n + 1 + col))

        portoes = [
            (pontos[centro_idx][0][0], pontos[centro_idx][0][1], f"Portão de {self.sitio.nome} #0"),
            (pontos[centro_idx][n][0], pontos[centro_idx][n][1], f"Portão de {self.sitio.nome} #1"),
            (pontos[0][centro_idx][0], pontos[0][centro_idx][1], f"Portão de {self.sitio.nome} #2"),
            (pontos[n][centro_idx][0], pontos[n][centro_idx][1], f"Portão de {self.sitio.nome} #3"),
        ][:self.num_portoes]

        # Quadras: recorta pelo raio da silhueta; a célula central vira praça, não quadra.
        # F5.1.8: distância de Chebyshev até a célula central pode chegar a 10+ numa
        # cidade grande (n cresce com raio_m/lado) — bem além do num_aneis do radial
        # (tipicamente 2-6). Sem reescalar, `_area_alvo_lote` (que cresce
        # exponencialmente com a banda) explode e a cidade vira uma quadra por lote. Duas
        # passadas: a primeira só descobre quais células sobrevivem e o max_d real; a
        # segunda reescala pra 1..banda_max antes de criar a Quadra.
        candidatas = []
        max_d = 1
        for row in range(n):
            for col in range(n):
                if row == centro_idx and col == centro_idx:
                    continue  # praça
                cantos = [pontos[row][col], pontos[row][col + 1],
                          pontos[row + 1][col + 1], pontos[row + 1][col]]
                cx = sum(p[0] for p in cantos) / 4.0
                cy = sum(p[1] for p in cantos) / 4.0
                ang = math.atan2(cy, cx)
                dist = math.hypot(cx, cy)
                if dist > raio_silhueta(ang):
                    continue
                d = max(abs(row - centro_idx), abs(col - centro_idx))
                max_d = max(max_d, d)
                candidatas.append((row, col, cantos, d))

        banda_max = max(cfg_get(self.cfg, "cidade_geo_num_aneis_faixa_por_tamanho").get(
            self.sitio.tamanho, [2, 4]))
        quadras = []
        vertices_retidos = []
        for row, col, cantos, d in candidatas:
            banda = 1 + round((d - 1) / max(1, max_d - 1) * (banda_max - 1)) if max_d > 1 else 1
            classes_aresta = [classe_da_linha(row), classe_da_linha(col + 1),
                               classe_da_linha(row + 1), classe_da_linha(col)]
            if banda == 1:
                bairro = "Centro"
            elif banda < banda_max:
                bairro = "Bairro Médio"
            else:
                bairro = "Bairro Externo"
            quadras.append(Quadra(vertices=cantos, classes_aresta=classes_aresta,
                                   banda=banda, bairro=bairro, id=(row, col)))
            vertices_retidos.extend(cantos)

        centro_praca = (pontos[centro_idx][centro_idx][0] + lado / 2.0 * cos_t - lado / 2.0 * sin_t,
                         pontos[centro_idx][centro_idx][1] + lado / 2.0 * sin_t + lado / 2.0 * cos_t)
        # raio inscrito da praça: metade do lado da célula central, com folga pra rua.
        raio_praca = max(10.0, lado / 2.0 - self._distancia_faixa_dominio("principal"))

        # Contorno: retângulo envolvente das quadras retidas, inflado pela folga da
        # muralha — sai um retângulo (rotacionado por theta) sem caso especial nenhum
        # (Seção 4.4: é exatamente o que o F4 foi feito pra permitir).
        folga = cfg_get(self.cfg, "cidade_geo_muralha_folga_m")
        if vertices_retidos:
            # bounding box no referencial NÃO rotacionado (antes de aplicar theta), pra
            # o retângulo sair alinhado à grade, não ao mundo.
            def desrotacionar(p):
                x, y = p
                return (x * cos_t + y * sin_t, -x * sin_t + y * cos_t)

            locais = [desrotacionar(p) for p in vertices_retidos]
            min_x = min(p[0] for p in locais) - folga
            max_x = max(p[0] for p in locais) + folga
            min_y = min(p[1] for p in locais) - folga
            max_y = max(p[1] for p in locais) + folga
            cantos_locais = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
            contorno = [(x * cos_t - y * sin_t, x * sin_t + y * cos_t) for x, y in cantos_locais]
        else:
            contorno = [(-self.raio_m, -self.raio_m), (self.raio_m, -self.raio_m),
                        (self.raio_m, self.raio_m), (-self.raio_m, self.raio_m)]
        espacamento_torres = cfg_get(self.cfg, "cidade_geo_muralha_torres_espacamento_m")
        torres = pontos_ao_longo_do_poligono(contorno, espacamento_torres)

        return Malha(ruas=ruas, quadras=quadras, portoes=portoes, centro_praca=centro_praca,
                     raio_praca=raio_praca, raio_nucleo=lado / 2.0, num_bandas=banda_max + 1,
                     contorno=contorno, torres=torres)
