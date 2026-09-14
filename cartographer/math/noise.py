import numpy as np

def perlin_noise_2d_vectorized(x, y, seed=0):
    """
    Vetorização pura em NumPy do algoritmo Perlin Noise 2D clássico com interpolação quíntica.
    Extremamente rápida, Thread-Safe, livre de Segmentation Faults e totalmente portátil.
    """
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    
    # Coordenadas inteiras dos cantos da célula do grid
    x0 = np.floor(x).astype(np.int32)
    x1 = x0 + 1
    y0 = np.floor(y).astype(np.int32)
    y1 = y0 + 1
    
    # Distâncias relativas na célula [0, 1]
    sx = x - x0
    sy = y - y0
    
    # Interpolação quíntica (fade de Ken Perlin): 6t^5 - 15t^4 + 10t^3
    u = sx * sx * sx * (sx * (sx * 6.0 - 15.0) + 10.0)
    v = sy * sy * sy * (sy * (sy * 6.0 - 15.0) + 10.0)
    
    # Função hash determinística de alta performance para grade inteira 2D vetorizada
    def hash_2d(xi, yi):
        with np.errstate(over='ignore'):
            h = xi.astype(np.uint32) * np.uint32(7324447) + yi.astype(np.uint32) * np.uint32(9125369) + np.uint32(seed) * np.uint32(1378233)
            h = np.bitwise_xor(h, h >> 16)
            h = h * np.uint32(2246822519)
            h = np.bitwise_xor(h, h >> 13)
            h = h * np.uint32(3266489917)
            h = np.bitwise_xor(h, h >> 16)
        return h
    
    # Hashes determinísticos de cada um dos 4 cantos
    h00 = hash_2d(x0, y0)
    h10 = hash_2d(x1, y0)
    h01 = hash_2d(x0, y1)
    h11 = hash_2d(x1, y1)
    
    # Conversão dos hashes em ângulos determinísticos de [0, 2pi]
    scale_angle = 2.0 * np.pi / 4294967295.0
    theta00 = h00.astype(np.float32) * scale_angle
    theta10 = h10.astype(np.float32) * scale_angle
    theta01 = h01.astype(np.float32) * scale_angle
    theta11 = h11.astype(np.float32) * scale_angle
    
    # Produtos escalares entre os vetores gradientes unitários de cada canto e as distâncias
    g00 = np.cos(theta00) * sx + np.sin(theta00) * sy
    g10 = np.cos(theta10) * (sx - 1.0) + np.sin(theta10) * sy
    g01 = np.cos(theta01) * sx + np.sin(theta01) * (sy - 1.0)
    g11 = np.cos(theta11) * (sx - 1.0) + np.sin(theta11) * (sy - 1.0)
    
    # Interpolação bilinear suave das contribuições de cada canto
    val0 = g00 + u * (g10 - g00)
    val1 = g01 + u * (g11 - g01)
    
    return val0 + v * (val1 - val0)

class NoiseGenerator:
    """
    Gerador e manipulador de campos de ruído Perlin multi-frequência (fBm) puramente vetorizado.
    """

    @staticmethod
    def generate_noise_field(grid_x, grid_y, scale, octaves=4, seed=0, offset=0,
                              persistencia=0.5, lacunaridade=2.0):
        """
        Gera uma grade 2D de ruído fractal Perlin (fBm) contínuo normalizado na faixa [0, 1].

        `persistencia` controla quanto a amplitude cai a cada oitava sucessiva e
        `lacunaridade` controla quanto a frequência sobe. Os defaults (0.5/2.0)
        preservam o comportamento histórico do projeto para os chamadores que
        ainda não foram migrados para passar esses valores explicitamente a
        partir de config["cartografia"] (ver docs/02_AUDITORIA_HARDCODE.md).
        """
        grid_x = np.asarray(grid_x, dtype=np.float32)
        grid_y = np.asarray(grid_y, dtype=np.float32)
        scale = max(0.001, scale)
        
        total = np.zeros_like(grid_x, dtype=np.float32)
        amplitude = 1.0
        frequency = 1.0
        max_val = 0.0
        
        for i in range(octaves):
            val = perlin_noise_2d_vectorized(
                (grid_x / scale) * frequency,
                (grid_y / scale) * frequency,
                seed=seed + offset + i * 100
            )
            total += val * amplitude
            max_val += amplitude
            amplitude *= persistencia
            frequency *= lacunaridade

        # F3 (Seção 2.2): normalizar pela soma TRUNCADA das amplitudes (`max_val`, que
        # depende de `octaves`) fazia adicionar oitava reescalar o campo inteiro em ~6,5%
        # — o zoom contradizia o zoom anterior em vez de só refinar (P1.7). A soma da
        # série geométrica infinita não depende de `octaves`, então o divisor passa a ser
        # estável: mais oitavas convergem para o mesmo campo, nunca o reescalam.
        soma_infinita = 1.0 / (1.0 - persistencia) if persistencia < 1.0 else max_val
        limite = soma_infinita * 0.707
        total_normalizado = np.clip(total / (limite if limite > 0 else 1.0), -1.0, 1.0)
        return (total_normalizado + 1.0) / 2.0

    @staticmethod
    def generate_detail_field(grid_x, grid_y, scale, octaves, seed, passo_mundo_px,
                              offset=0, persistencia=0.5, lacunaridade=2.0):
        """
        Campo de detalhe fino com LIMITE DE BANDA (D2/Caminho B do DIAGNOSTICO_V3).

        Diferença para `generate_noise_field`: cada oitava cujo comprimento de onda é menor
        que o dobro do passo de amostragem da janela (`passo_mundo_px`, em px de MUNDO por
        amostra) é apagada suavemente antes de entrar na soma. Sem isso, um campo de escala
        sub-pixel vira ruído de amostragem ("sal e pimenta") no mapa-múndi.

        Isto NÃO viola F1 (pureza). O campo é sempre o mesmo em todo ponto do mundo; o que o
        passo controla é quanto dele a janela consegue representar — é antialiasing, o mesmo
        papel de um mipmap. T2 (subdivisão) continua exata porque subdividir uma janela em
        quadrantes na mesma resolução preserva o passo.

        Normaliza pela soma da série INFINITA, como `generate_noise_field` (correção F3 da
        Fase 0.2): apagar oitavas nunca reescala o que sobrou.

        Retorna a faixa [-1, 1] (centrada em zero), não [0, 1] — este campo é uma PERTURBAÇÃO
        somada a uma altitude que já existe, não uma altitude por si.
        """
        grid_x = np.asarray(grid_x, dtype=np.float32)
        grid_y = np.asarray(grid_y, dtype=np.float32)
        scale = max(1e-6, float(scale))
        passo = max(1e-12, float(passo_mundo_px))

        total = np.zeros_like(grid_x, dtype=np.float32)
        amplitude = 1.0
        frequency = 1.0

        for i in range(octaves):
            comprimento_onda = scale / frequency
            # Nyquist: >1 significa que a janela tem amostras de sobra para esta oitava.
            razao = comprimento_onda / (2.0 * passo)
            t = float(np.clip(razao - 1.0, 0.0, 1.0))
            fade = t * t * (3.0 - 2.0 * t)          # smoothstep: sem degrau entre zooms
            if fade > 0.0:
                total += perlin_noise_2d_vectorized(
                    (grid_x / scale) * frequency,
                    (grid_y / scale) * frequency,
                    seed=seed + offset + i * 100,
                ) * amplitude * fade
            amplitude *= persistencia
            frequency *= lacunaridade

        soma_infinita = 1.0 / (1.0 - persistencia) if persistencia < 1.0 else 1.0
        limite = soma_infinita * 0.707
        return np.clip(total / limite, -1.0, 1.0)

    @staticmethod
    def generate_tectonic_base(grid_x, grid_y, seed, config, oitavas_extra=0):
        """
        Gera a base geológica unindo macro-formas tectônicas e micro-detalhes de alta frequência.

        `config` é o bloco config["cartografia"] (via `cfg_get`) — antes esta função
        tinha suas próprias constantes de classe (DEFAULT_TECTONIC_*) que duplicavam
        (e podiam divergir) as chaves de config equivalentes, e ignorava por completo
        `persistencia`/`lacunariedade`. Ver docs/02_AUDITORIA_HARDCODE.md.

        `oitavas_extra` (Fase 0.3, F3): acrescenta oitavas de alta frequência sem alterar
        a forma grossa — é o mecanismo de LOD por zoom. Some às contagens de oitava base,
        nunca as substitui.
        """
        from config import cfg_get

        persistencia = cfg_get(config, "persistencia")
        lacunaridade = cfg_get(config, "lacunariedade")

        ruido_macro = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=cfg_get(config, "ruido_macro_escala"),
            octaves=cfg_get(config, "ruido_macro_oitavas") + oitavas_extra,
            seed=seed,
            persistencia=persistencia, lacunaridade=lacunaridade
        )
        ruido_detalhe = NoiseGenerator.generate_noise_field(
            grid_x, grid_y,
            scale=cfg_get(config, "ruido_costa_escala"),
            octaves=cfg_get(config, "ruido_costa_oitavas") + oitavas_extra,
            seed=seed,
            offset=500,
            persistencia=persistencia, lacunaridade=lacunaridade
        )
        peso_macro = cfg_get(config, "tectonica_base_peso_macro")
        peso_detalhe = cfg_get(config, "tectonica_base_peso_detalhe")
        return ruido_macro * peso_macro + ruido_detalhe * peso_detalhe
