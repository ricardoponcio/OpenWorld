from dataclasses import dataclass

import numpy as np
from cartographer.math import NoiseGenerator, TectonicsProcessor, ClimateProcessor
from config import cfg_get


@dataclass
class _CamposDeRuido:
    """Os 3 campos de ruído cru que `gerar_janela` monta antes de acumular
    continentes — extraídos pra um dataclass pra não virar 3 parâmetros soltos
    passados entre as etapas privadas (R-D04)."""
    ruido_macro: np.ndarray
    relevo_base: np.ndarray
    ruido_costa: np.ndarray


@dataclass
class _MassaContinental:
    """Resultado de acumular todos os continentes na janela: a máscara de "quanto é
    terra" em cada pixel, o relevo continental, os modificadores climáticos ponderados,
    e (se pedido) quem é dono de cada pixel."""
    mask_continente: np.ndarray
    relevo_continentes: np.ndarray
    mod_calor_total: np.ndarray
    mod_umidade_total: np.ndarray
    donos: 'np.ndarray | None'


class TileCartographer:
    """
    Cartógrafo procedural responsável por gerar os dados geográficos e climáticos
    de tiles individuais de forma perfeitamente contínua e determinística.
    """
    # R-D04: offsets de ruído nomeados — mudar qualquer um dos dois MUDA O MUNDO
    # GERADO (são parte da semente efetiva de cada campo). Documentados aqui em vez de
    # literais soltos no meio do método.
    OFFSET_RUIDO_COSTA = 12345
    OFFSET_RUIDO_MAR = 9999
    PERFIL_GEOLOGICO_PADRAO = "Alpino"
    def __init__(self, size=256, seed=0, config=None, layout_continentes=None, tamanho_global=None):
        self.size = size
        self.seed = seed
        self.config = config
        self.layout_continentes = layout_continentes or {"continentes": []}
        # Dimensão real do mundo composto (ex.: 3 tiles x 256px = 768). Antes esse
        # valor era um literal 768.0 fixo dentro da vinheta e do gradiente de
        # temperatura — agora é calculado pelo chamador (WorldManager) e passado
        # explicitamente, então mudar o grid de tiles não quebra silenciosamente
        # essas duas contas (achado #3 de docs/02_AUDITORIA_HARDCODE.md).
        self.tamanho_global = tamanho_global if tamanho_global is not None else self.size * 3

    def generate_tile(self, offset_x, offset_y):
        """
        Gera um pedaço do mundo baseado na sua posição global (tile de `self.size` px,
        sem oitavas extras). Wrapper fino sobre `gerar_janela` — mantido para os
        chamadores existentes (`WorldManager.get_tile`, `generate_world.py`).
        offset_x/y são as coordenadas do tile (ex: 0, 1, 2...)
        """
        s = self.size
        return self.gerar_janela(offset_x * s, offset_y * s, (offset_x + 1) * s, (offset_y + 1) * s, s, s)

    @staticmethod
    def calcular_raio_efetivo(cont, cfg):
        """
        Raio de influência final de um continente — extraído de `gerar_janela` pra ser
        reutilizável fora da renderização (ex.: `WorldManager` usa pra atribuir pixel de
        terra ao continente certo por proximidade NORMALIZADA pelo raio, não distância
        bruta — Fase 1.1). Mantém as duas em sincronia: se este cálculo mudar, os dois
        lugares mudam juntos automaticamente.
        """
        raio_min_px = cfg_get(cfg, "continente_raio_min_px")
        raio_max_px = cfg_get(cfg, "continente_raio_max_px")
        escala_pixel_area_km2 = cfg_get(cfg, "escala_pixel_area_km2")
        fator_visual = cfg_get(cfg, "continente_area_para_raio_fator_visual")
        raio_visual_padrao = cfg_get(cfg, "continente_raio_visual_padrao", default=200.0)
        nivel_mar = cfg_get(cfg, "nivel_mar")

        irreg = cont["irregularidade"]
        fator_min = cfg_get(cfg, "tectonica_raio_fator_min")
        fator_variacao = cfg_get(cfg, "tectonica_raio_fator_variacao")
        fator_distorcao = cfg_get(cfg, "tectonica_costa_distorcao_fator")

        # Conversão de escala: um continente circular de área `area_km2`, desenhado
        # numa escala onde 1 pixel de terra = `escala_pixel_area_km2` km², tem raio
        # R = sqrt(area_km2 / (pi * escala)). `fator_visual` existe só para ajuste
        # fino visual posterior sem abandonar essa relação física.
        area = cont.get("area_km2", 0)
        if area > 0:
            R = np.sqrt(area / (np.pi * escala_pixel_area_km2)) * fator_visual
        else:
            R = cont.get("raio_visual", cont.get("raio", raio_visual_padrao))

        # Compensação de irregularidade (Fase 1.1 — achado na calibração, P1.2):
        # `apply_coastal_distortion` soma `ruido_costa(médio≈0.5) * irreg * R *
        # fator_distorcao` à distância antes de comparar com `raio_dinamico`. Isso faz
        # a área real efetiva encolher com `irreg`, mesmo mantendo a MESMA área
        # planejada — medido: dois continentes com a mesma `area_km2` mas
        # irregularidade 0.25 vs 0.70 saíram com área real 3,5x diferente. Sem isso,
        # nenhum `fator_visual` único serve pra todos os continentes ao mesmo tempo
        # (um valor que acerta o de baixa irregularidade sempre encolhe demais o de
        # alta). Deriva-se a compensação da própria fórmula do raio efetivo (fração de
        # terra = 1 - nivel_mar; raio dinâmico médio assume ruido_macro médio ≈ 0.5):
        raio_dinamico_fator_medio = fator_min + fator_variacao * 0.5
        fracao_terra = 1.0 - nivel_mar
        k_irreg = (0.5 * fator_distorcao) / max(1e-6, raio_dinamico_fator_medio * fracao_terra)
        compensacao_irreg = 1.0 / max(0.05, 1.0 - k_irreg * irreg)
        R = R * compensacao_irreg

        # Calibração adaptativa por continente (Fase 1.1, `WorldManager._calibrar_continentes`):
        # a compensação de irregularidade acima corrige o viés sistemático médio, mas o
        # valor REAL de `ruido_macro` na posição exata deste continente (que também
        # modula `raio_dinamico`) só é conhecido depois de renderizar — variação que
        # nenhuma fórmula fechada prevê. `compensacao_calibrada` é achada por bisseção
        # (renderiza, mede área real, ajusta) e persistida no manifesto — 1.0 se ainda
        # não foi calibrada (compatível com layout antigo/`_cartografo_de_teste`).
        R = R * cont.get("compensacao_calibrada", 1.0)

        # Guarda-corpo de segurança contra resposta absurda da IA/fallback — não é
        # mais a fonte principal da variação de tamanho.
        return float(np.clip(R, raio_min_px, raio_max_px))

    def gerar_janela(self, x0, y0, x1, y1, largura, altura, oitavas_extra=0,
                      _desabilitar_culling=False, retornar_donos=False):
        """
        Gera os 4 canais (altitude, temperatura, umidade, bioma) para a janela em
        coordenada de MUNDO [x0,x1) x [y0,y1), amostrada em `largura`x`altura` pontos.

        Esta é a primitiva única de qualquer zoom (Fase 0, Seção 2.2 — F1/F2/F3): o
        terreno é uma função de `(x_mundo, y_mundo)`, nunca de índice de array. Pedir a
        mesma janela em resoluções diferentes refina o resultado (mais oitavas via
        `oitavas_extra`); nunca o contradiz, porque a normalização do ruído (Fase 0.2)
        não depende da contagem de oitavas.

        `_desabilitar_culling`: só para o teste T5 (Seção 8) — força a avaliação de todos
        os continentes mesmo fora do alcance, pra provar que o culling (otimização) não
        muda o resultado. Não é parâmetro de uso normal.

        `retornar_donos` (Fase 1.1, P1.2): quando True, devolve `(data, donos)` em vez de
        só `data` — `donos` é `(altura,largura)` int32 com o ÍNDICE do continente cujo
        `fator_radial` venceu o `np.maximum` naquele pixel (-1 = oceano/nenhum). É a
        atribuição EXATA de "que máscara pintou esta terra", usada por
        `WorldManager.save_world_manifest` pra medir área real por continente sem o erro
        de aproximar por distância ao centro (achado na calibração: um continente grande
        "rouba" pixels de um vizinho menor na fronteira, mesmo quando distância normalizada
        pelo raio — só a atribuição exata elimina isso).

        `linspace(a, a+N, N, endpoint=False)` é exatamente `arange(a, a+N)` — em z0
        (`largura=altura=self.size`, `oitavas_extra=0`) o resultado é bit a bit igual ao
        `generate_tile` antigo (T4 garante isso).

        Refatorado em 6 etapas privadas (R-D04) — a matemática de cada uma é idêntica à
        versão anterior, só movida; nenhuma reordenada. `tests/test_cartografia.py`
        trava isso bit a bit (determinismo, invariância a subdivisão, coerência entre
        zooms, culling).
        """
        grid_x, grid_y = self._montar_grade(x0, y0, x1, y1, largura, altura)
        ruidos = self._gerar_campos_de_ruido(grid_x, grid_y, oitavas_extra)
        massa = self._acumular_continentes(grid_x, grid_y, ruidos, x0, y0, x1, y1,
                                            oitavas_extra, _desabilitar_culling, retornar_donos)
        altitude_regional = self._mesclar_terra_e_mar(massa, grid_x, grid_y, oitavas_extra)
        altitude_final = self._aplicar_detalhe_local(altitude_regional, grid_x, grid_y, largura, x0, x1)
        return self._classificar_clima_e_bioma(altitude_regional, altitude_final, massa,
                                                grid_x, grid_y, retornar_donos)

    def _montar_grade(self, x0, y0, x1, y1, largura, altura):
        x_range = np.linspace(x0, x1, largura, endpoint=False, dtype=np.float32)
        y_range = np.linspace(y0, y1, altura, endpoint=False, dtype=np.float32)
        return np.meshgrid(x_range, y_range)

    def _gerar_campos_de_ruido(self, grid_x, grid_y, oitavas_extra) -> _CamposDeRuido:
        """Base geológica contínua (Perlin) + costa de alta frequência pra distorções
        locais. Nunca reusa buffer entre chamadas: janela não-quadrada quebraria um
        array de tamanho fixo, e chamadas concorrentes (servidor de tiles) se
        corromperiam compartilhando o mesmo array."""
        cfg = self.config
        scale_macro = cfg_get(cfg, "ruido_macro_escala")
        oct_macro = cfg_get(cfg, "ruido_macro_oitavas")
        ruido_macro = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale_macro, octaves=oct_macro + oitavas_extra, seed=self.seed)
        relevo_base = NoiseGenerator.generate_tectonic_base(grid_x, grid_y, seed=self.seed, config=cfg, oitavas_extra=oitavas_extra)

        scale_costa = cfg_get(cfg, "ruido_costa_escala")
        oct_costa = cfg_get(cfg, "ruido_costa_oitavas")
        ruido_costa = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale_costa, octaves=oct_costa + oitavas_extra, seed=self.seed, offset=self.OFFSET_RUIDO_COSTA)

        return _CamposDeRuido(ruido_macro=ruido_macro, relevo_base=relevo_base, ruido_costa=ruido_costa)

    def _acumular_continentes(self, grid_x, grid_y, ruidos: _CamposDeRuido, x0, y0, x1, y1,
                               oitavas_extra, _desabilitar_culling, retornar_donos) -> _MassaContinental:
        """Itera cada continente do layout, acumulando a máscara de terra (o maior
        `fator_radial` entre todos, pixel a pixel), o relevo continental, e os
        modificadores climáticos ponderados pela proximidade. Culling (Fase 0.3,
        2-4x mais rápido em zoom alto): pula o continente cujo raio de influência
        máximo não alcança a janela pedida — `test_culling_nao_altera_resultado`
        garante que ligar/desligar isto não muda o resultado, bit a bit."""
        cfg = self.config
        altura, largura = grid_x.shape
        mask_continente = np.zeros((altura, largura), dtype=np.float32)
        relevo_continentes = np.zeros((altura, largura), dtype=np.float32)
        mod_calor_total = np.zeros((altura, largura), dtype=np.float32)
        mod_umidade_total = np.zeros((altura, largura), dtype=np.float32)
        donos = np.full((altura, largura), -1, dtype=np.int32) if retornar_donos else None

        nivel_mar = cfg_get(cfg, "nivel_mar")
        elevacao_maxima_padrao = cfg_get(cfg, "continente_elevacao_maxima_padrao", default=0.8)

        for idx_cont, cont in enumerate(self.layout_continentes.get("continentes", [])):
            cx = cont["centro_x"]
            cy = cont["centro_y"]

            irreg = cont["irregularidade"]
            elev_max = cont.get("elevacao_maxima", elevacao_maxima_padrao)
            perfil = cont.get("perfil_geologico", self.PERFIL_GEOLOGICO_PADRAO)

            fator_min = cfg_get(cfg, "tectonica_raio_fator_min")
            fator_variacao = cfg_get(cfg, "tectonica_raio_fator_variacao")
            fator_distorcao = cfg_get(cfg, "tectonica_costa_distorcao_fator")
            warp_amplitude = cfg_get(cfg, "tectonica_warp_amplitude")

            R = self.calcular_raio_efetivo(cont, cfg)

            alcance = R * (fator_min + fator_variacao) + irreg * R * fator_distorcao + warp_amplitude
            dist_x = max(x0 - cx, 0.0, cx - x1)
            dist_y = max(y0 - cy, 0.0, cy - y1)
            distancia_janela = (dist_x ** 2 + dist_y ** 2) ** 0.5
            if not _desabilitar_culling and distancia_janela > alcance:
                continue

            # Distância euclidiana e raio modulado dinamicamente pelas correntes tectônicas
            distancia = TectonicsProcessor.calculate_distance_grid(grid_x, grid_y, cx, cy, config=cfg, seed=self.seed, oitavas_extra=oitavas_extra)
            raio_dinamico = TectonicsProcessor.calculate_tectonic_radius(R, ruidos.ruido_macro, config=cfg)

            # Distorção costeira
            dist_perturbada = TectonicsProcessor.apply_coastal_distortion(distancia, ruidos.ruido_costa, irreg, R, config=cfg)

            # Fator de gradiente radial perturbado
            fator_radial = np.clip(1.0 - (dist_perturbada / raio_dinamico), 0.0, 1.0)

            # Acumula a máscara continental (e, se pedido, quem venceu em cada pixel —
            # tem que ser calculado ANTES do np.maximum sobrescrever o estado "antes").
            if retornar_donos:
                donos[fator_radial > mask_continente] = idx_cont
            mask_continente = np.maximum(mask_continente, fator_radial)

            # Modelagem do perfil geológico do continente
            relevo_perfil = TectonicsProcessor.calculate_geological_profile(perfil, ruidos.relevo_base, grid_x, grid_y, self.seed, config=cfg, oitavas_extra=oitavas_extra)

            # Altitude continental garantida acima da costa
            f_terra = np.clip((fator_radial - nivel_mar) / (1.0 - nivel_mar), 0.0, 1.0)
            altura_terra = nivel_mar + (elev_max - nivel_mar) * relevo_perfil * f_terra
            altura_terra = np.where(fator_radial >= nivel_mar, altura_terra, 0.0)

            # Acumula relevo continental
            relevo_continentes = np.maximum(relevo_continentes, altura_terra)

            # Climatologia regional baseada nos modificadores da IA
            modificadores = cont.get("modificadores", {})
            mod_calor = modificadores.get("calor", cont.get("modificador_calor", 0.0))
            mod_umidade = modificadores.get("umidade", cont.get("modificador_umidade", 0.0))

            mod_calor_total += fator_radial * mod_calor
            mod_umidade_total += fator_radial * mod_umidade

        # Máscara de Vignette de Cosseno global para as bordas do mundo
        fator_borda = TectonicsProcessor.apply_cosine_vignette(grid_x, grid_y, map_size=self.tamanho_global, config=cfg)
        mask_continente = mask_continente * fator_borda
        relevo_continentes = relevo_continentes * fator_borda

        if retornar_donos:
            # A vinheta pode empurrar um pixel de volta pra baixo de `nivel_mar` mesmo que
            # algum continente tenha "vencido" ali antes dela — sincroniza `donos` com a
            # MESMA condição de terra usada na mesclagem final.
            donos[mask_continente < nivel_mar] = -1

        return _MassaContinental(mask_continente=mask_continente, relevo_continentes=relevo_continentes,
                                  mod_calor_total=mod_calor_total, mod_umidade_total=mod_umidade_total,
                                  donos=donos)

    def _mesclar_terra_e_mar(self, massa: _MassaContinental, grid_x, grid_y, oitavas_extra):
        """Canal 0 (Altitude): ruído marinho suave (fossas/bancos de areia) onde não é
        terra, relevo continental onde é. Retorna a altitude REGIONAL (sem o campo de
        detalhe local) — é o que alimenta clima e bioma."""
        cfg = self.config
        nivel_mar = cfg_get(cfg, "nivel_mar")

        f_mar = cfg_get(cfg, "ruido_mar_escala")
        oct_mar = cfg_get(cfg, "ruido_mar_oitavas")
        amp_mar = cfg_get(cfg, "ruido_mar_amplitude")
        piso_mar = cfg_get(cfg, "ruido_mar_piso")
        teto_fracao = cfg_get(cfg, "ruido_mar_teto_fracao_nivel_mar")

        ruido_mar = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=f_mar, octaves=oct_mar + oitavas_extra, seed=self.seed, offset=self.OFFSET_RUIDO_MAR)
        max_ruido_mar = min(nivel_mar * teto_fracao, piso_mar + amp_mar)
        ruido_mar_suave = piso_mar + (ruido_mar * (max_ruido_mar - piso_mar))

        return np.where(
            massa.mask_continente >= nivel_mar,
            massa.relevo_continentes,
            (1.0 - (massa.mask_continente / nivel_mar)) * ruido_mar_suave + (massa.mask_continente / nivel_mar) * nivel_mar
        )

    def _aplicar_detalhe_local(self, altitude_regional, grid_x, grid_y, largura, x0, x1):
        """Campo de detalhe local (D2/Caminho B do DIAGNOSTICO_V3) — textura
        sub-regional somada por cima da altitude regional, só pra exibição em zoom
        alto. NÃO entra no cálculo de clima/bioma (esses usam `altitude_regional`,
        preservada pelo chamador) — a classificação de bioma foi calibrada contra o
        campo regional, e deixar o detalhe entrar reabriria essa calibração sem
        necessidade."""
        cfg = self.config
        nivel_mar = cfg_get(cfg, "nivel_mar")
        altitude = altitude_regional

        amp_detalhe = cfg_get(cfg, "relevo_detalhe_amplitude")
        if amp_detalhe <= 0.0:
            return altitude

        passo_mundo_px = (x1 - x0) / largura
        margem_costa = cfg_get(cfg, "relevo_detalhe_margem_costa")
        # Envelope: o detalhe nasce em zero na linha d'água e cresce terra adentro. É
        # o que garante T6 (a costa não pode mudar entre zooms) por construção.
        envelope = np.clip((altitude - nivel_mar) / max(1e-6, margem_costa), 0.0, 1.0)
        detalhe = NoiseGenerator.generate_detail_field(
            grid_x, grid_y,
            scale=cfg_get(cfg, "relevo_detalhe_escala_px"),
            octaves=cfg_get(cfg, "relevo_detalhe_oitavas"),
            seed=self.seed,
            passo_mundo_px=passo_mundo_px,
            offset=cfg_get(cfg, "relevo_detalhe_offset_ruido"),
        )
        # Piso de segurança: um pixel que é terra nunca pode virar água por causa do
        # detalhe, nem com envelope. Redundante com o envelope, mantido como rede.
        piso = np.where(altitude > nivel_mar, nivel_mar + 1e-6, altitude)
        return np.maximum(altitude + amp_detalhe * detalhe * envelope, piso)

    def _classificar_clima_e_bioma(self, altitude_regional, altitude_final, massa: _MassaContinental,
                                    grid_x, grid_y, retornar_donos):
        """Canais 1-3 (temperatura/umidade/bioma), a partir da altitude REGIONAL (sem
        detalhe — ver `_aplicar_detalhe_local`). `map_height`/`map_size` recebem
        `self.tamanho_global`, NÃO a largura/altura da janela — passar o tamanho da
        janela faria a latitude e a vinheta mudarem com o zoom."""
        cfg = self.config
        nivel_mar = cfg_get(cfg, "nivel_mar")
        nivel_montanha = cfg_get(cfg, "nivel_montanha")
        altura, largura = grid_x.shape

        data = np.zeros((altura, largura, 4), dtype=np.float32)
        data[:, :, 0] = altitude_final
        data[:, :, 1] = ClimateProcessor.calculate_temperature(
            grid_y, altitude_regional, massa.mod_calor_total, map_height=self.tamanho_global, config=cfg
        )
        data[:, :, 2] = ClimateProcessor.calculate_humidity(
            altitude_regional, massa.mod_umidade_total, config=cfg, nivel_mar=nivel_mar,
            grid_x=grid_x, grid_y=grid_y, seed=self.seed
        )
        # `classify_biomes` usa `octaves=1` fixo internamente para o dithering de
        # fronteira (macro-onda lisa e intencional) — não recebe `oitavas_extra`.
        data[:, :, 3] = ClimateProcessor.classify_biomes(
            altitude_regional, data[:, :, 1], data[:, :, 2], config=cfg,
            nivel_mar=nivel_mar, nivel_montanha=nivel_montanha,
            grid_x=grid_x, grid_y=grid_y, seed=self.seed
        )

        if retornar_donos:
            return data, massa.donos
        return data
