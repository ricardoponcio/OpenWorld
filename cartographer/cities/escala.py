"""
Escala da geometria de cidade: metros, px de mundo e zoom do mapa.

A cidade é gerada num sistema local em METROS, o mundo é indexado em PIXELS e o Leaflet
desenha em PIXELS DE TELA. Toda conversão entre esses três vive aqui, num lugar só, porque
cada vez que uma delas foi feita à mão em outro arquivo saiu errada: o D1 confundiu área com
comprimento, e a largura de rua nasceu em px de tela, o que a deixava mais estreita quanto
mais perto você chegava.

A cidade é sub-pixel na escala do mundo (Seção 2.1/2.3 do docs/DIAGNOSTICO_V3.md: 1 px de
mundo = 15,81 km, então a cidade "grande" tem 0,114 px de mundo de diâmetro). Sem um
`zoom_min` por camada, ruas e edifícios apareceriam amontoados num ponto em qualquer zoom
baixo.

A regra é uma só: a camada acende quando a CIDADE INTEIRA atinge um tamanho alvo na tela.

    zoom_min = ceil(log2(alvo_px_de_tela / diametro_px_de_mundo))

(no L.CRS.Simple do Leaflet, 1 px de mundo ocupa 2^zoom px de tela, daí o log2.)

Este módulo é o único lugar onde essa conta existe. O gerador de geometria grava o
resultado em cada feature, e /api/continentes devolve a mesma tabela pro frontend saber a
que zoom levar o usuário — os dois precisam concordar. Mantido leve de propósito (só
stdlib) pra poder ser importado do web sem arrastar numpy/render junto.
"""

import math

from config.resolver import cfg_get


def metros_por_pixel_mundo(config):
    """Lado do pixel de mundo, em metros.

    `escala_pixel_area_km2` é ÁREA (km² por pixel), então o lado é a RAIZ dela. Confundir
    as duas coisas foi o D1: dava um erro de sqrt(250) = 15,81x no tamanho das cidades.
    """
    return math.sqrt(cfg_get(config, "escala_pixel_area_km2")) * 1000.0


def faixa_raio_m(config, tamanho):
    """Faixa de raio da cidade, em metros, JÁ multiplicada pela escala global
    (`cidade_geo_escala`). É o único lugar que lê `cidade_geo_raio_m_faixa_por_tamanho`
    — tanto `SitioCidade` (que dimensiona a janela de terreno) quanto os modelos (que
    sorteiam o raio) passam por aqui; se um dos dois lesse a chave crua e o outro
    passasse pela escala, a janela deixaria de cobrir a cidade e o terreno seria lido
    errado, silenciosamente, por causa do `np.clip` que G06 removeu (Q04, docs/
    PLANO_CIDADE_VIVA.md).

    R01 (docs/PLANO_POPULACAO_E_ESCALA.md, Bloco R): desde que o raio passou a ser
    DERIVADO do número de domicílios (`raio_para_lotes`), esta faixa deixou de ser a
    FONTE do raio e virou só o piso/teto de sanidade que grampeia o resultado — ela
    continua sendo o que `SitioCidade` usa pra dimensionar a janela de terreno (o teto
    é sempre >= qualquer raio derivado, por construção do grampo)."""
    faixa = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(tamanho, [500.0, 500.0])
    escala = cfg_get(config, "cidade_geo_escala")
    return [faixa[0] * escala, faixa[1] * escala]


def domicilios_alvo(config, tamanho, rng):
    """R01: quantos domicílios (lotes residenciais que nascem OCUPADOS) a cidade deve
    ter — o sorteio PRIMÁRIO da cidade agora; o raio passa a ser DERIVADO disso
    (`raio_para_lotes`), não mais sorteado direto. Único lugar que lê
    `cidade_geo_domicilios_alvo_faixa_por_tamanho`.

    `cidade_geo_escala` (D5, docs/PLANO_CIDADE_VIVA.md) multiplica AQUI — domicílios,
    não mais raio. O float continua sendo "o tamanho das cidades do mundo", só que
    numa unidade que corresponde a gente de verdade (`builder/populador.py` conta os
    domicílios que nasceram ocupados pra decidir quantas famílias povoar, R03)."""
    faixa = cfg_get(config, "cidade_geo_domicilios_alvo_faixa_por_tamanho").get(tamanho, [50.0, 50.0])
    escala = cfg_get(config, "cidade_geo_escala")
    return rng.uniform(*faixa) * escala


def lotes_alvo(config, tamanho, domicilios: float) -> float:
    """R01: quantos lotes (residenciais + comerciais + institucionais) a cidade
    precisa pra comportar `domicilios` residências, dada a fração de lotes ocupados
    no nascimento (`cidade_geo_ocupacao_inicial_por_tamanho`, D2) e o piso de área
    residencial (`cidade_geo_fracao_residencial_min`) — os dois já existem, D01/D02
    de PLANO_CIDADE_VIVA.md, e não são recalculados aqui, só lidos."""
    ocupacao = cfg_get(config, "cidade_geo_ocupacao_inicial_por_tamanho").get(tamanho, 1.0)
    fracao_residencial_min = cfg_get(config, "cidade_geo_fracao_residencial_min")
    return domicilios / (ocupacao * fracao_residencial_min)


def raio_para_lotes(config, modelo_nome: str, lotes_alvo_valor: float, tamanho: str):
    """R02: converte "quero N lotes" em "então o raio é R", usando a densidade de
    lote por raio MEDIDA por modelo (`cidade_geo_densidade_lote_por_modelo`,
    `builder/fix/calibrar_densidade.py`) — nunca deduzida (a relação varia por
    modelo: `grade` cresce com raio², `linear` quase linear com raio).

    `lotes = k * raio^e  =>  raio = (lotes/k)^(1/e)`. Grampeado em `faixa_raio_m`
    (agora piso/teto de sanidade, não mais fonte) — devolve `(raio_m, grampeado)`
    pro chamador decidir se registra o estouro; grampear e engolir em silêncio
    esconderia a faixa de domicílios saindo de calibragem (R01, Ação 4)."""
    k, e = cfg_get(config, "cidade_geo_densidade_lote_por_modelo")[modelo_nome]
    raio_bruto = (lotes_alvo_valor / k) ** (1.0 / e)
    piso, teto = faixa_raio_m(config, tamanho)
    raio_final = max(piso, min(teto, raio_bruto))
    return raio_final, raio_final != raio_bruto


def diametro_px_de_mundo(config, raio_m):
    """Diâmetro da cidade em px de MUNDO, a partir do raio REAL da cidade em metros.

    ESPEC_TECIDO_URBANO.md Seção 6/E6 (2026-09-11): recebia `tamanho` e buscava o raio
    NOMINAL da tabela (`cidade_geo_raio_m_por_tamanho`). Desde que o raio passou a ser
    sorteado por cidade dentro de uma faixa (Seção 5.6), isso teria feito toda cidade
    'media' acender rua/edifício no mesmo zoom, apagando a variedade que a E6 introduz.
    Quem quer a aproximação por tamanho nominal (o popup do frontend) usa `tabela_zoom_min`
    abaixo, que documenta a aproximação explicitamente.
    """
    return 2.0 * raio_m / metros_por_pixel_mundo(config)


def zoom_min_por_camada(config, raio_m):
    """`{camada: zoom_min}` para uma cidade com este raio REAL, em metros."""
    diametro = diametro_px_de_mundo(config, raio_m)
    alvos = cfg_get(config, "cidade_geo_zoom_min_alvo_px_por_camada")
    return {
        camada: int(math.ceil(math.log2(alvo / diametro)))
        for camada, alvo in alvos.items()
    }


def tabela_zoom_min(config):
    """`{tamanho: {camada: zoom_min}}` usando o RAIO NOMINAL de cada tamanho
    (`cidade_geo_raio_m_por_tamanho`) — é uma APROXIMAÇÃO: desde a E6 cada cidade sorteia
    seu próprio raio dentro de uma faixa (`cidade_geo_raio_m_faixa_por_tamanho`), então o
    zoom_min real gravado nas features de uma cidade específica pode diferir um pouco do
    que esta tabela diz. Ela alimenta só o texto do popup e o alvo do duplo-clique no
    frontend (`/api/continentes`), onde essa aproximação é aceitável — documentado aqui
    para não repetir a divergência silenciosa corrigida no D9."""
    return {
        tamanho: zoom_min_por_camada(config, raio_m)
        for tamanho, raio_m in cfg_get(config, "cidade_geo_raio_m_por_tamanho").items()
    }
