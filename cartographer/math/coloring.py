import numpy as np
from config import cfg_get


class ColoringProcessor:
    """
    Processador de preenchimento e interpolação de paletas altitudinais e renderização marinha.

    A paleta inteira (cores de oceano e de cada bioma) vem de
    `config["cartografia"]["cores"]` — nenhuma cor fica mais hardcoded aqui. Ver
    docs/ROADMAP.md (Frente 1) e docs/AUDITORIA_HARDCODE.md.
    """

    @staticmethod
    def render_ocean(heightmap, config, nivel_mar=None):
        """
        Gera um sombreamento dinâmico de recifes/mar profundo usando uma curva de potência.
        """
        if nivel_mar is None:
            nivel_mar = cfg_get(config, "nivel_mar")
        cores = cfg_get(config, "cores")
        oceano = cfg_get(cores, "oceano")
        raso = cfg_get(oceano, "raso")
        profundo = cfg_get(oceano, "profundo")
        potencia = cfg_get(oceano, "curva_potencia")

        alt_norm = np.clip(heightmap / nivel_mar, 0.0, 1.0)
        alt_shading = np.power(alt_norm, potencia)

        r_chan = profundo[0] * (1.0 - alt_shading) + raso[0] * alt_shading
        g_chan = profundo[1] * (1.0 - alt_shading) + raso[1] * alt_shading
        b_chan = profundo[2] * (1.0 - alt_shading) + raso[2] * alt_shading

        return np.stack([r_chan, g_chan, b_chan], axis=-1).astype(np.uint8)

    @staticmethod
    def interpolate_land_biome(bioma_id, alt_terra_norm, config):
        """
        Interpolação de cor genérica por 3 pontos de controle (baixa -> media -> pico_neve),
        dirigida inteiramente por config["cartografia"]["cores"]["biomas"][id].

        Cada bioma define sua própria `transicao` (altitude normalizada onde a cor "media"
        é atingida): biomas com relevo (Deserto/Mediterrâneo/Floresta) usam ~0.65; a
        Montanha Rochosa usa `transicao=0.0`, o que degenera para um gradiente único e
        contínuo baixa->pico em toda a faixa de altitude (equivalente ao comportamento
        original antes desta migração).
        """
        cores = cfg_get(config, "cores")
        bioma_cor = cfg_get(cfg_get(cores, "biomas"), str(int(bioma_id)))
        cor_baixa = cfg_get(bioma_cor, "baixa")
        cor_media = cfg_get(bioma_cor, "media")
        cor_pico = cfg_get(cores, "pico_neve")
        transicao = cfg_get(bioma_cor, "transicao")

        if transicao > 0.0:
            t1 = alt_terra_norm / transicao
        else:
            t1 = np.ones_like(alt_terra_norm)  # segmento 1 nunca é usado (ver abaixo)
        t2 = np.clip((alt_terra_norm - transicao) / (1.0 - transicao), 0.0, 1.0)

        canais = []
        for i in range(3):
            seg1 = cor_baixa[i] * (1.0 - t1) + cor_media[i] * t1
            seg2 = cor_media[i] * (1.0 - t2) + cor_pico[i] * t2
            canal = np.where(alt_terra_norm < transicao, seg1, seg2)
            canais.append(canal.astype(np.uint8))

        return tuple(canais)
