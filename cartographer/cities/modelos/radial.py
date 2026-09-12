"""
RadialModelo — o traçado de hoje (burgo medieval em anéis + radiais ao redor de um
mercado), movido pra cá pela refatoração do F4.

S01/S02 (docs/PLANO_POPULACAO_E_ESCALA.md, 2026-09-12): o número de setores deixou de
ser único pra cidade inteira — ele DOBRA a cada banda em que o arco ultrapassaria a
largura alvo (`self.setores_por_banda`, monotônico não-decrescente). Isso muda a saída
de toda cidade radial (armadilha 1 do PLANO_CIDADE_VIVA.md: determinístico não quer
dizer igual ao de antes) e é o motivo de a "grade" deixar de ser um array 2D regular
`(banda, setor)` e virar uma lista de linhas de tamanho variável.
"""
import math

from config import cfg_get
from cartographer.cities.escala import faixa_raio_m
from .base import ModeloCidade, Rua, Quadra, Malha, envolver_poligono, pontos_ao_longo_do_poligono, densificar_anel

# Dois anéis vizinhos podem se mover um na direção do outro, então a soma das duas
# amplitudes tem que caber no vão: cada uma < metade. 0.45 dá 10% de margem de
# segurança contra a soma chegar a 1.0 (que é o anel invertido — Seção 1.1 do
# docs/PLANO_CIDADE_VIVA.md).
FRACAO_VAO_MAXIMA_SEGURA = 0.45

# S01: o arco de uma quadra pode ficar até 1.5x a largura alvo antes de a banda seguinte
# dobrar os setores — dá uma faixa de 0.75x a 1.5x em vez de saturar sempre no teto.
FATOR_TOLERANCIA_LARGURA = 1.5


class RadialModelo(ModeloCidade):
    nome = "radial"

    def __init__(self, sitio, config, rng):
        super().__init__(sitio, config, rng)
        # ⚠️ Ordem de consumo do self.rng idêntica à do GeradorCidade de antes do F4
        # (raio -> anéis -> fator de lote -> setores) — mudar a ordem muda todas as
        # cidades do mundo, silenciosamente (Seção 10 item 1).
        self.raio_m = self.rng.uniform(*faixa_raio_m(config, sitio.tamanho))
        self.num_portoes = cfg_get(config, "cidade_geo_num_portoes_por_tamanho").get(sitio.tamanho, 2)
        # G05: num_aneis deixa de ser sorteado independente do raio — o vão entre anéis
        # (raio_m / (num_aneis+1)) É a profundidade da quadra (Anexo 3 do
        # docs/PLANO_CIDADE_VIVA.md), e sorteá-los à parte fazia o vão variar de 82 a
        # 169 m entre cidades do mesmo tamanho, produzindo até 209 lotes numa quadra só.
        # A faixa por tamanho vira LIMITE (piso/teto), não mais fonte do sorteio.
        # ⚠️ Isto remove um `self.rng.randint` da sequência — todas as cidades mudam
        # (esperado, armadilha 1; nenhum sorteio-fantasma pra compensar).
        faixa_aneis = cfg_get(config, "cidade_geo_num_aneis_faixa_por_tamanho").get(
            sitio.tamanho, [2, 2])
        vao_alvo = cfg_get(config, "cidade_geo_vao_anel_alvo_m")
        aneis_ideais = round(self.raio_m / vao_alvo) - 1
        self.num_aneis = max(int(faixa_aneis[0]), min(int(faixa_aneis[1]), aneis_ideais))
        self.irreg = cfg_get(config, "cidade_geo_irregularidade_via")
        # G01: fração do vão entre anéis que a perturbação pode ocupar, saturada no
        # limite estrutural — nunca no valor bruto do config (que um game designer
        # poderia, por engano, subir acima do que a geometria aguenta).
        fracao = cfg_get(config, "cidade_geo_anel_perturbacao_fracao_vao")
        self.anel_fracao_vao = min(fracao, FRACAO_VAO_MAXIMA_SEGURA)
        faixa_fator_cidade = cfg_get(config, "cidade_geo_lote_fator_cidade_faixa")
        self.lote_fator_cidade = self.rng.uniform(*faixa_fator_cidade)
        faixa_setores_por_portao = cfg_get(config, "cidade_geo_setores_por_portao_faixa")
        sorteio_setores = self.rng.uniform(*faixa_setores_por_portao)
        self.num_setores = max(self.num_portoes * 2, round(self.num_portoes * sorteio_setores))

        # S01: raios_base é pura aritmética (sem rng) — calculado aqui, não mais dentro
        # de construir_malha, porque setores_por_banda precisa dele antes de a grade
        # de vértices existir.
        self.raios_base = [self.raio_m * (j + 1) / (self.num_aneis + 1) for j in range(self.num_aneis)]
        self.setores_por_banda = self._calcular_setores_por_banda(config)

        self.praca_fracao_nucleo = cfg_get(config, "cidade_geo_praca_fracao_nucleo")
        self.praca_raio_min = cfg_get(config, "cidade_geo_praca_raio_min_m")
        self.praca_raio_max = cfg_get(config, "cidade_geo_praca_raio_max_m")
        raio_banda0 = self.raio_m / (self.num_aneis + 1)
        self.praca_raio = min(self.praca_raio_max,
                               max(self.praca_raio_min, self.praca_fracao_nucleo * raio_banda0))
        self.recuo_rua = cfg_get(config, "cidade_geo_recuo_rua_m")
        self.via_largura_por_classe = cfg_get(config, "cidade_via_largura_m_por_classe")

    def _calcular_setores_por_banda(self, config):
        """S01: `s` só CRESCE (nunca diminui) — é o que garante que
        `setores_por_banda[j]` seja sempre múltiplo de `setores_por_banda[j-1]`, a
        propriedade de que as radiais (que nascem numa banda e continuam pra fora,
        nunca somem) e a densificação do anel interno (S02) dependem."""
        largura_alvo = cfg_get(config, "cidade_geo_quadra_largura_alvo_m")
        setores_max = cfg_get(config, "cidade_geo_setores_max")
        s = self.num_setores
        setores_por_banda = []
        for j in range(self.num_aneis + 1):
            raio_j = self.raios_base[j] if j < self.num_aneis else self.raio_m
            while (2 * math.pi * raio_j / s) > largura_alvo * FATOR_TOLERANCIA_LARGURA and s * 2 <= setores_max:
                s *= 2
            setores_por_banda.append(s)
        return setores_por_banda

    # ------------------------------------------------------------------
    # Leitura de terreno local — G06: delega a `SitioCidade`, o único dono da grade
    # (ARQUITETURA.md P1). Usada aqui só em heurística de posicionamento (praça,
    # portão) dentro do raio original, nunca perto da borda da janela — `None` (ponto
    # fora da janela) cai pra 0.0, "sem preferência", o que é seguro nestes dois usos.
    # ------------------------------------------------------------------
    def _declividade_local(self, x_m, y_m):
        declividade = self.sitio.declividade_em(x_m, y_m)
        return 0.0 if declividade is None else declividade

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

    def _amplitude_anel_m(self):
        """G01: o VÃO entre anéis vizinhos (constante) é o espaço disponível pra
        perturbar o raio de um vértice — nunca o raio em si (que cresce com a banda).
        Ver docs/PLANO_CIDADE_VIVA.md Seção 1.1."""
        vao = self.raio_m / (self.num_aneis + 1)
        return vao * self.anel_fracao_vao

    # ------------------------------------------------------------------
    def _grade_de_vertices(self):
        """S01/S02: devolve `vertices[j]` — uma LISTA de linhas de tamanho variável
        (`len(vertices[j]) == self.setores_por_banda[j]`), não mais um array 2D
        regular. Ponto de extensão pra modelos que deformam a malha (G04, `organica`):
        deforme AQUI, nunca a lista de ruas depois de pronta (Seção 1.2 do
        docs/PLANO_CIDADE_VIVA.md) — senão rua e quadra deixam de coincidir.

        A asserção de anéis cruzados compara o vértice da banda `j` com o ponto
        CORRESPONDENTE do anel `j-1` já densificado (S02) pra resolução de `j` — bandas
        vizinhas podem ter contagens de setor diferentes, então "mesmo índice de
        setor" deixou de fazer sentido; "mesmo ângulo" (via densificação) é o que
        substitui."""
        amplitude_m = self._amplitude_anel_m()

        vertices = []
        for j in range(self.num_aneis + 1):
            s_j = self.setores_por_banda[j]
            raio_base_j = self.raios_base[j] if j < self.num_aneis else self.raio_m
            perturb_j = self.np_rng.uniform(-1.0, 1.0, size=s_j)
            linha = [self._polar(raio_base_j + amplitude_m * perturb_j[i], 2 * math.pi * i / s_j)
                     for i in range(s_j)]
            vertices.append(linha)

        # Invariante, não preferência (ver docstring da classe/G01): com a amplitude
        # saturada em FRACAO_VAO_MAXIMA_SEGURA isto nunca deveria disparar.
        for j in range(1, len(vertices)):
            s_j = self.setores_por_banda[j]
            interno_denso = densificar_anel(vertices[j - 1], s_j)
            for i in range(s_j):
                r_interno = math.hypot(*interno_denso[i])
                r_externo = math.hypot(*vertices[j][i])
                assert r_externo > r_interno, (
                    f"{self.sitio.nome}: anéis cruzados na banda {j}, setor {i} — "
                    f"cidade_geo_anel_perturbacao_fracao_vao alto demais")
        return vertices

    def construir_malha(self) -> Malha:
        vertices = self._grade_de_vertices()
        borda = vertices[-1]
        s_final = self.setores_por_banda[-1]
        amplitude_m = self._amplitude_anel_m()

        passo = max(1, s_final // self.num_portoes)

        def _rotacao_uniforme(deslocamento):
            return [(deslocamento + k * passo) % s_final for k in range(self.num_portoes)]

        if self.sitio.terreno is not None:
            declividades = [self._declividade_local(*borda[i]) for i in range(s_final)]
            ordem = sorted(range(s_final), key=lambda i: declividades[i])
            espacamento_min = passo
            indices_portao = []
            for i in ordem:
                if all(min((i - j) % s_final, (j - i) % s_final) >= espacamento_min
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
        centro_praca = self._melhor_centro_praca(self.raios_base[0])
        raio_banda0 = self.raios_base[0]
        raio_nucleo_candidato = (math.hypot(*centro_praca) + self.praca_raio +
                                  self._distancia_faixa_dominio("anel"))
        # G01: o anel do núcleo usa a MESMA amplitude_m que os demais (perturbação
        # absoluta), então o vão real até raios_base[0] precisa caber as duas
        # amplitudes somadas — mesmo raciocínio de FRACAO_VAO_MAXIMA_SEGURA, só que
        # aqui o vão não é `vao` (o núcleo não fica a uma distância nominal fixa de
        # raios_base[0]): é `raio_banda0 - raio_nucleo_candidato`, que pode ser bem
        # menor que `vao` se a praça quase toma o núcleo inteiro (Seção 1.1).
        nucleo_urbanizavel = raio_nucleo_candidato < raio_banda0 - 2 * amplitude_m
        nucleo = None
        raio_nucleo = 0.0
        ruas = []
        s_nucleo = self.setores_por_banda[0]
        if nucleo_urbanizavel:
            raio_nucleo = raio_nucleo_candidato
            perturb_nucleo = self.np_rng.uniform(-1.0, 1.0, size=s_nucleo)
            # G01: mesma amplitude absoluta dos demais anéis — o anel do núcleo é vizinho
            # de raios_base[0] e precisa respeitar o mesmo vão, não o raio (bem menor) do
            # próprio núcleo. Mesma resolução de setores da banda 0 (S01/S02).
            nucleo = [self._polar(raio_nucleo + amplitude_m * perturb_nucleo[i], 2 * math.pi * i / s_nucleo)
                      for i in range(s_nucleo)]
            for i in range(s_nucleo):
                assert math.hypot(*nucleo[i]) < math.hypot(*vertices[0][i]), (
                    f"{self.sitio.nome}: anel do núcleo cruza raios_base[0] no setor {i}")
            ruas.append(Rua(pontos=nucleo + [nucleo[0]], classe_via="anel", tipo_via="anel", indice=-1))

        for j, linha in enumerate(vertices):
            ruas.append(Rua(pontos=linha + [linha[0]], classe_via="anel", tipo_via="anel", indice=j))

        # S02: o anel INTERNO de cada banda, densificado pra resolução da banda ATUAL —
        # calculado uma vez, reusado pela radial (ponto de nascimento) e pela quadra
        # (aresta interna), pra uma nova radial nascer exatamente sobre o ponto que a
        # quadra também usa (senão rua e quadra deixam de coincidir — o mesmo bug que
        # G04/Seção 1.2 já existia pra evitar, só que agora entre bandas vizinhas).
        interno_denso_por_banda = {}
        for j in range(1, self.num_aneis + 1):
            interno_denso_por_banda[j] = densificar_anel(vertices[j - 1], self.setores_por_banda[j])
        if nucleo is not None:
            interno_denso_por_banda[0] = densificar_anel(nucleo, self.setores_por_banda[0])

        # S01: cada radial nasce na banda em que `setores_por_banda` primeiro alcança
        # sua resolução, e continua até a borda — nunca some no meio (setores_por_banda
        # só cresce, então `passo_j` só diminui e divide `passo_{j-1}`). Uma radial que
        # nasce na banda 0 começa no núcleo/centro; uma que nasce numa banda j > 0
        # começa no ponto (denso) do anel j-1 onde ela foi inserida — é o mesmo ponto
        # que a quadra usa como aresta interna, então rua e quadra continuam
        # coincidindo (validado por `test_rua_coincide_com_aresta_de_quadra`).
        for k in range(s_final):
            pontos = []
            banda_nascimento = None
            for j in range(self.num_aneis + 1):
                s_j = self.setores_por_banda[j]
                passo_j = s_final // s_j
                if k % passo_j == 0:
                    if banda_nascimento is None:
                        banda_nascimento = j
                    pontos.append(vertices[j][k // passo_j])
            if banda_nascimento == 0:
                passo_nucleo = s_final // s_nucleo
                origem = nucleo[k // passo_nucleo] if nucleo is not None else (0.0, 0.0)
                pontos = [origem] + pontos
            elif banda_nascimento in interno_denso_por_banda:
                passo_nascimento = s_final // self.setores_por_banda[banda_nascimento]
                origem = interno_denso_por_banda[banda_nascimento][k // passo_nascimento]
                pontos = [origem] + pontos
            classe = "principal" if k in setores_portao else "secundaria"
            ruas.append(Rua(pontos=pontos, classe_via=classe, tipo_via="radial", indice=k))

        portoes = [(borda[i][0], borda[i][1], f"Portão de {self.sitio.nome} #{i}") for i in indices_portao]

        # Quadras — banda 0 (núcleo, se urbanizável) até num_aneis (borda). Vertices e
        # classes_aresta crus, SEM inset — GeradorCidade._gerar_quarteiroes_e_lotes é
        # quem encolhe pela faixa de domínio (F4.4: "o que não é gancho mora na base").
        quadras = []
        banda_inicial = 0 if nucleo_urbanizavel else 1
        for j in range(banda_inicial, self.num_aneis + 1):
            s_j = self.setores_por_banda[j]
            raio_externo = vertices[j]
            raio_interno = interno_denso_por_banda[j]
            if j == 0:
                bairro = "Núcleo"
            elif j == 1:
                bairro = "Centro"
            elif j < self.num_aneis:
                bairro = "Bairro Médio"
            else:
                bairro = "Bairro Externo"
            passo_j = s_final // s_j
            for i in range(s_j):
                i2 = (i + 1) % s_j
                quad = [raio_interno[i], raio_externo[i], raio_externo[i2], raio_interno[i2]]
                # As arestas 0/2 (radiais) desta banda correspondem ao índice GLOBAL
                # (resolução da borda) i*passo_j/i2*passo_j — é nessa resolução que
                # `setores_portao` foi calculado.
                classes_aresta = [
                    self._classe_via_radial(i * passo_j, setores_portao),
                    "anel",
                    self._classe_via_radial(i2 * passo_j, setores_portao),
                    "anel",
                ]
                quadras.append(Quadra(vertices=quad, classes_aresta=classes_aresta,
                                       banda=j, bairro=bairro, id=(j, i)))

        # Muralha + torres — sempre computadas (custam pouco: um np_rng.uniform), mesmo
        # quando `precisa_muralha()` vai acabar não usando; GeradorCidade decide se
        # emite. Isso preserva a ordem de consumo do np_rng de forma estável dentro
        # desta versão (perturb por banda -> perturb_nucleo -> perturb_muralha), sem
        # precisar saber aqui se a cidade vai ter muralha ou não (essa pergunta é o
        # gancho `precisa_muralha`).
        #
        # G03 (Seção 1.3): a muralha é derivada da BORDA real que as quadras usam, não
        # de um raio+array de aleatórios paralelo e descorrelacionado — antes disso a
        # folga configurada (40 m) não bastava e quadra ficava até 103 m fora do muro.
        # `envolver_poligono` garante por construção que todo vértice da borda fica
        # DENTRO do contorno; a variação orgânica só pode somar folga (nunca subtrair),
        # daí o `abs`.
        folga_base = cfg_get(self.cfg, "cidade_geo_muralha_folga_m")
        espacamento_torres = cfg_get(self.cfg, "cidade_geo_muralha_torres_espacamento_m")
        perturb_muralha = self.np_rng.uniform(-1.0, 1.0, size=s_final)
        folgas = [folga_base * (1.0 + self.irreg * 0.3 * abs(perturb_muralha[i]))
                  for i in range(s_final)]
        contorno = envolver_poligono(borda, folgas)
        torres = pontos_ao_longo_do_poligono(contorno, espacamento_torres)

        return Malha(ruas=ruas, quadras=quadras, portoes=portoes, centro_praca=centro_praca,
                     raio_praca=self.praca_raio, raio_nucleo=raio_nucleo,
                     num_bandas=self.num_aneis + 1, contorno=contorno, torres=torres)
