import numpy as np
from cartographer.math.noise import NoiseGenerator
from config import cfg_get


class TectonicsProcessor:
    """
    Processador geográfico responsável pelas placas tectônicas, perfis geológicos e
    modulações de relevo continental.

    Todas as funções recebem `config` (o bloco config["cartografia"]) e leem seus
    parâmetros via `cfg_get` — nenhum valor de balanceamento fica mais hardcoded
    aqui. Ver docs/ROADMAP.md (Frente 1) e docs/AUDITORIA_HARDCODE.md.
    """

    @staticmethod
    def calculate_distance_grid(grid_x, grid_y, cx, cy, config, seed=0, oitavas_extra=0):
        """
        Calcula a distância euclidiana de cada ponto da grade ao centro (cx, cy)
        aplicando Domain Warping de alta intensidade para distorcer a forma circular.

        `oitavas_extra` (Fase 0.3, F3): LOD por zoom — soma às 3 oitavas base do warp.
        """
        scale = cfg_get(config, "tectonica_warp_escala")
        amplitude = cfg_get(config, "tectonica_warp_amplitude")

        # Geramos ruído Perlin vetorizado normalizado na faixa [0, 1]
        noise_x = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale, octaves=3 + oitavas_extra, seed=seed, offset=7777)
        noise_y = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=scale, octaves=3 + oitavas_extra, seed=seed, offset=9999)

        # Trazemos o ruído para a faixa [-1, 1] para aplicar distorção bidirecional (Domain Warping)
        warp_x = (noise_x * 2.0 - 1.0) * amplitude
        warp_y = (noise_y * 2.0 - 1.0) * amplitude

        dx = grid_x + warp_x - cx
        dy = grid_y + warp_y - cy
        return np.sqrt(dx**2 + dy**2)

    @staticmethod
    def calculate_tectonic_radius(base_radius, ruido_macro, config):
        """
        Modula o raio de influência continental dinamicamente com base nas correntes tectônicas:
        raio_dinamico = base_radius * (fator_min + fator_variacao * ruido_macro)
        """
        fator_min = cfg_get(config, "tectonica_raio_fator_min")
        fator_variacao = cfg_get(config, "tectonica_raio_fator_variacao")
        return base_radius * (fator_min + fator_variacao * ruido_macro)

    @staticmethod
    def apply_coastal_distortion(distancia, ruido_costa, irregularidade, base_radius, config):
        """
        Aplica perturbação de alta frequência à distância euclidiana para simular costões rochosos.
        """
        fator = cfg_get(config, "tectonica_costa_distorcao_fator")
        return distancia + (ruido_costa * irregularidade * base_radius * fator)

    @staticmethod
    def normalize_profile(relevo_perfil):
        """
        Normaliza dinamicamente o perfil geológico para ocupar a amplitude vertical total [0, 1].
        """
        p_min = np.min(relevo_perfil)
        p_max = np.max(relevo_perfil)
        if p_max > p_min:
            return (relevo_perfil - p_min) / (p_max - p_min)
        return relevo_perfil

    @staticmethod
    def calculate_geological_profile(perfil_nome, relevo_base, grid_x, grid_y, seed, config, oitavas_extra=0):
        """
        Aplica o modelo matemático do perfil geológico especificado.

        `oitavas_extra` (Fase 0.3, F3): LOD por zoom — soma às 3 oitavas base do ruído
        usado no perfil "Arquipélago". Os demais perfis (Alpino/Platô/Erosivo) derivam
        de `relevo_base`, que já recebeu `oitavas_extra` em `generate_tectonic_base`.
        """
        if perfil_nome == "Alpino":
            relevo_perfil = np.power(relevo_base, 1.5)
        elif perfil_nome == "Platô":
            limiar_plato = cfg_get(config, "perfil_plato_limiar")
            achatamento = cfg_get(config, "perfil_plato_achatamento")
            relevo_perfil = np.where(
                relevo_base > limiar_plato,
                limiar_plato + (relevo_base - limiar_plato) * achatamento,
                relevo_base
            )
        elif perfil_nome == "Arquipélago":
            escala = cfg_get(config, "perfil_arquipelago_escala")
            inclinacao = cfg_get(config, "perfil_arquipelago_inclinacao_sigmoide")
            centro = cfg_get(config, "perfil_arquipelago_centro")
            ruido_arqui = NoiseGenerator.generate_noise_field(grid_x, grid_y, scale=escala, octaves=3 + oitavas_extra, seed=seed, offset=8888)
            # Função sigmoide contínua e suave (em vez de degrau booleano descontínuo).
            # Isso cria encostas e praias realistas e remove os "aquedutos de concreto" de quina seca no zoom.
            fator_arqui = 0.1 + 0.9 / (1.0 + np.exp(-inclinacao * (ruido_arqui - centro)))
            relevo_perfil = relevo_base * fator_arqui
        elif perfil_nome == "Erosivo":
            relevo_perfil = np.sqrt(relevo_base)
        else:
            relevo_perfil = relevo_base

        return relevo_perfil

    @staticmethod
    def apply_cosine_vignette(grid_x, grid_y, map_size, config):
        """
        Gera uma máscara de atenuação de borda ultra-suave baseada na curva de cosseno.

        `map_size` é a dimensão real do mundo composto (ex.: tile_size * tiles_por_lado),
        calculada pelo chamador — não é um parâmetro de balanceamento de cartografia, por
        isso não vem de `config` (antes era um literal 768.0 fixo, quebrando silenciosamente
        se o grid de tiles do mundo mudasse de tamanho; ver achado #3 de AUDITORIA_HARDCODE.md).
        """
        margem_segura = cfg_get(config, "vinheta_margem_segura")
        largura_fade = cfg_get(config, "vinheta_largura_fade")

        dist_x = np.minimum(grid_x, map_size - grid_x)
        dist_y = np.minimum(grid_y, map_size - grid_y)
        menor_dist = np.minimum(dist_x, dist_y)

        fator_borda = np.clip((menor_dist - margem_segura) / largura_fade, 0.0, 1.0)
        return 0.5 * (1.0 - np.cos(fator_borda * np.pi))
