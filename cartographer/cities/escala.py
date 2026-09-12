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
    PLANO_CIDADE_VIVA.md)."""
    faixa = cfg_get(config, "cidade_geo_raio_m_faixa_por_tamanho").get(tamanho, [500.0, 500.0])
    escala = cfg_get(config, "cidade_geo_escala")
    return [faixa[0] * escala, faixa[1] * escala]


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
