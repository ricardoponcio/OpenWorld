import math
from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.tiles.render import obter_cartografo, config_hash_atual, oitavas_extra_por_zoom
from config import cfg_get

# Cache em memória das janelas de continente/cidade geradas sob demanda (Fase 0.5):
# substitui os .npz de database/continentes|cidades. Chave inclui config_hash — muda a
# config, o cache velho vira lixo automaticamente (armadilha nº 16 do plano).
_JANELA_CACHE = {}


def gerar_janela_com_cache(cache_key, x0, y0, x1, y1, largura, altura):
    """Gera (ou reaproveita do cache em memória do processo) a janela de mundo pedida.
    Retorna (dados, mundo_px_por_img_px) ou (None, None) se o mundo ainda não existe."""
    cartografo = obter_cartografo()
    if cartografo is None:
        return None, None

    chave = (cache_key, config_hash_atual())
    if chave in _JANELA_CACHE:
        return _JANELA_CACHE[chave]

    mundo_px_por_img_px = (x1 - x0) / largura
    # Escolhe oitavas extras pela densidade efetiva da janela (px de imagem por px de
    # mundo), reaproveitando a mesma curva de LOD por zoom do servidor de tiles — quanto
    # mais ampliado, mais oitavas, nunca reescalando o que já foi decidido (F3).
    densidade = largura / max(1e-6, (x1 - x0))
    z_equivalente = max(0, round(math.log2(max(densidade, 1e-6))))
    oitavas_extra = oitavas_extra_por_zoom(z_equivalente)

    dados = cartografo.gerar_janela(x0, y0, x1, y1, largura, altura, oitavas_extra=oitavas_extra)
    resultado = (dados, mundo_px_por_img_px)
    teto = cfg_get(CARTOGRAPHER_CONFIG, "janela_cache_teto")
    if len(_JANELA_CACHE) >= teto:  # teto simples — é só pra evitar hover recalcular a cada pixel
        _JANELA_CACHE.pop(next(iter(_JANELA_CACHE)))
    _JANELA_CACHE[chave] = resultado
    return resultado


def resolucao_de_imagem(largura_mundo, altura_mundo, alvo_maior_lado_px):
    """Resolução proporcional ao aspecto real da janela — nunca força quadrado,
    então a isotropia sai de graça (Fase 0.5)."""
    fator = alvo_maior_lado_px / max(largura_mundo, altura_mundo)
    return (max(1, round(largura_mundo * fator)), max(1, round(altura_mundo * fator)))


def _dimensao_global_padrao():
    return cfg_get(CARTOGRAPHER_CONFIG, "mundo_tiles_por_lado") * cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px")


def janela_continente(continente, manifest):
    """Bbox do continente + padding, em coordenada de MUNDO, e a resolução de imagem
    proporcional ao aspecto real (Fase 0.5 — isotropia sai de graça: nunca força quadrado)."""
    bbox = continente["bounding_box"]
    padding = cfg_get(CARTOGRAPHER_CONFIG, "janela_padding_px")
    dimensao_global = manifest.get("dimensao_global") or _dimensao_global_padrao()
    x0 = max(0, bbox["min_x"] - padding)
    y0 = max(0, bbox["min_y"] - padding)
    x1 = min(dimensao_global, bbox["max_x"] + padding)
    y1 = min(dimensao_global, bbox["max_y"] + padding)

    alvo_maior_lado_px = cfg_get(CARTOGRAPHER_CONFIG, "imagem_janela_resolucao_alvo_px")
    largura_mundo, altura_mundo = max(1.0, x1 - x0), max(1.0, y1 - y0)
    largura_img, altura_img = resolucao_de_imagem(largura_mundo, altura_mundo, alvo_maior_lado_px)
    return x0, y0, x1, y1, largura_img, altura_img


def janela_regiao(cidade, manifest):
    """Bbox de mundo (raio fixo ao redor do pixel-âncora) + resolução de imagem alvo
    para a vista REGIONAL da cidade — mesma janela usada por `/imagem` e `/entities`, pra
    bbox e imagem nunca divergirem (Fase 2.1). D7 do DIAGNOSTICO_V3 (2026-09-11): esta é a
    janela de 'onde a cidade fica no continente' (raio regional, ~190km) — não confundir
    com a cidade em si, que é sub-pixel nessa escala (Seção 2.4) e só existe como geometria
    vetorial (ver /api/mapa/features, camada de detalhe de cidade, D3)."""
    raio = cfg_get(CARTOGRAPHER_CONFIG, "regiao_janela_raio_px")
    cx, cy = cidade["x_global"], cidade["y_global"]
    dimensao_global = manifest.get("dimensao_global") or _dimensao_global_padrao()
    x0, y0 = max(0, cx - raio), max(0, cy - raio)
    x1, y1 = min(dimensao_global, cx + raio), min(dimensao_global, cy + raio)

    alvo = cfg_get(CARTOGRAPHER_CONFIG, "imagem_janela_resolucao_alvo_px")
    largura_mundo, altura_mundo = max(1.0, x1 - x0), max(1.0, y1 - y0)
    largura_img, altura_img = resolucao_de_imagem(largura_mundo, altura_mundo, alvo)
    return x0, y0, x1, y1, largura_img, altura_img
