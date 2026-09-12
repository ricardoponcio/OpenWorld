"""
OrganicaModelo — radial degradado de propósito (F7, ESPEC_DESENHO_CIDADE.md). Herda de
`RadialModelo` (permitido e esperado, Seção 5.5/F7.1) e aplica degradações sobre a GRADE
de vértices (G04, docs/PLANO_CIDADE_VIVA.md Seção 1.2) — nunca sobre a lista de ruas
depois de pronta: rua e quadra são duas leituras da mesma grade, e só perturbando a
grade elas continuam coincidindo.
"""
import math

from config import cfg_get
from .base import Rua
from .radial import RadialModelo, FRACAO_VAO_MAXIMA_SEGURA

# G04/F7.1.4: o deslocamento angular tangencial tem que ser menor que metade do passo
# angular entre setores, senão dois setores se cruzam (mesmo raciocínio de G01, só que
# em ângulo em vez de raio).
PASSO_ANGULAR_FRACAO_MAXIMA = 0.35


class OrganicaModelo(RadialModelo):
    nome = "organica"

    def __init__(self, sitio, config, rng):
        super().__init__(sitio, config, rng)
        # F7.1.1/G04: irregularidade maior — depois de G01 o raio do anel não lê mais
        # `self.irreg` (só a silhueta de grade/muralha lê), então "organica é mais torta
        # que radial" passa a ser a mesma fração do vão, só que amplificada — sempre
        # saturada no limite estrutural, nunca no valor bruto do config
        # (Anexo 2 do docs/PLANO_CIDADE_VIVA.md).
        fator = cfg_get(config, "cidade_geo_organica_fator_irregularidade")
        self.anel_fracao_vao = min(self.anel_fracao_vao * fator, FRACAO_VAO_MAXIMA_SEGURA)

    def _grade_de_vertices(self):
        vertices = super()._grade_de_vertices()
        return self._torcer_grade(vertices)

    def _torcer_grade(self, vertices):
        """F7.1.4 — radial torta. Desloca o vértice TANGENCIALMENTE (perpendicular ao
        raio, ou seja, girando em torno do centro por um ângulo pequeno), por banda,
        com fase própria por setor. Girar preserva o raio — não pode reintroduzir o
        cruzamento de anéis que G01 acabou de eliminar (deslocar em linha reta poderia).
        Como rua e quadra leem esta mesma grade (retornada por `_grade_de_vertices`), as
        duas tortam juntas e continuam coincidindo (Seção 1.2).

        S03 (docs/PLANO_POPULACAO_E_ESCALA.md): o passo angular É POR BANDA agora —
        depois de S01, a banda externa pode ter várias vezes mais setores que a
        interna, e um passo global (o de antes) deixaria de ser uma fração pequena do
        passo de verdade daquela banda: dois setores vizinhos trocariam de lugar, e o
        `organica` voltaria a produzir o cruzamento que G01/G04 eliminaram. Este é o
        tipo de bug que NÃO estoura — a geometria sai torta e só o mapa denuncia."""
        fase_por_anel = self.np_rng.uniform(0, 2 * math.pi, size=len(vertices))
        torcidos = []
        for j, linha in enumerate(vertices):
            passo_j = 2 * math.pi / len(linha)
            delta_max_j = passo_j * PASSO_ANGULAR_FRACAO_MAXIMA
            nova_linha = []
            for i, (x, y) in enumerate(linha):
                raio = math.hypot(x, y)
                angulo = math.atan2(y, x)
                delta = delta_max_j * math.sin(fase_por_anel[j] + i * 1.3)
                nova_linha.append(self._polar(raio, angulo + delta))
            torcidos.append(nova_linha)
        return torcidos

    def construir_malha(self):
        malha = super().construir_malha()

        # F7.1.2: anéis que não fecham — cada `rua` tipo_via="anel" perde um arco
        # contíguo de 1 a 3 setores; a rua vira polilinha aberta, não um loop. G04: isso
        # muda SÓ A RUA — a quadra adjacente ao arco aberto passa a não ter frente
        # naquela aresta, então a `classes_aresta` dela troca de "anel" pra "sem_via"
        # (L02, docs/PLANO_POPULACAO_E_ESCALA.md: não existe via nenhuma ali — recuo
        # zero, nenhum lote pode ter frente).
        novas_ruas = []
        aneis_abertos = {}  # indice do anel -> conjunto de setores no vão aberto (na resolução DAQUELE anel)
        for r in malha.ruas:
            if r.tipo_via != "anel":
                novas_ruas.append(r)
                continue
            nova_rua, setores_do_vao = self._abrir_anel(r)
            novas_ruas.append(nova_rua)
            if setores_do_vao:
                aneis_abertos[r.indice] = setores_do_vao
        malha.ruas = novas_ruas

        if aneis_abertos:
            for quadra in malha.quadras:
                j, i = quadra.id
                s_j = self.setores_por_banda[j]
                i2 = (i + 1) % s_j
                # O gap remove o SEGMENTO da rua entre dois setores consecutivos — se
                # QUALQUER um dos dois extremos da aresta (i ou i2) cai no vão, o
                # segmento de rua daquele trecho não existe mais, não só quando os dois
                # caem (achado ao auditar: quadra (1,4) tinha só o setor 5 no vão, não o
                # 4, e ainda assim ficava sem rua na aresta 4->5).
                gap_externo = aneis_abertos.get(j, ())
                if i in gap_externo or i2 in gap_externo:
                    quadra.classes_aresta[1] = "servico"  # aresta externa (vertices[j])

                # S02: a aresta interna vem de vertices[j-1] DENSIFICADO pra resolução
                # `s_j` — mas o vão aberto de `aneis_abertos[j-1]` foi calculado na
                # resolução ORIGINAL (menor) da banda j-1. Um ponto denso em `i` é uma
                # interpolação entre os pontos originais `i//fator` e `i//fator + 1`
                # (`densificar_anel`) — os DOIS contam como "toca o vão", não só o
                # primeiro, senão um ponto interpolado bem próximo do vão ainda seria
                # tratado como se tivesse rua. Fator 1 (banda não dobrou) é a
                # identidade: `i//1` e `i//1 + 1` colapsam no caso simples de antes.
                if j > 0:
                    s_anterior = self.setores_por_banda[j - 1]
                    fator = s_j // s_anterior
                    gap_interno = aneis_abertos.get(j - 1, ())

                    def _toca_o_vao(idx_denso):
                        origem = idx_denso // fator
                        return origem in gap_interno or (origem + 1) % s_anterior in gap_interno

                    if _toca_o_vao(i) or _toca_o_vao(i2):
                        quadra.classes_aresta[3] = "servico"  # aresta interna (vertices[j-1])

        return malha

    def _abrir_anel(self, rua):
        """Devolve (rua_com_vão, setores_do_vão) — `setores_do_vão` é o conjunto de
        índices de setor removidos, NA RESOLUÇÃO PRÓPRIA desta rua (`len(rua.pontos)`,
        que já é `self.setores_por_banda[j]` pra cada anel `j` desde S01/S02) — pra
        quem chama saber quais quadras perderam a frente naquela aresta (ver docstring
        de `construir_malha`)."""
        linha = rua.pontos[:-1]  # tira o ponto de fechamento duplicado (radial.py fecha o loop)
        n = len(linha)
        if n < 4:
            return rua, set()  # anel pequeno demais pra abrir sem sumir
        gap_len = self.rng.randint(1, min(3, n - 2))
        gap_start = self.rng.randrange(n)
        setores_do_vao = {(gap_start + k) % n for k in range(gap_len)}
        mantidos = [linha[(gap_start + gap_len + i) % n] for i in range(n - gap_len)]
        nova_rua = Rua(pontos=mantidos, classe_via=rua.classe_via, tipo_via=rua.tipo_via, indice=rua.indice)
        return nova_rua, setores_do_vao
