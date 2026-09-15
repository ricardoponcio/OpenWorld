from flask import Blueprint, jsonify, send_file
import io
from web.helpers import render_npz_map_to_bytes, render_npz_array, obter_manifesto
from web.cache_mapa import MAPA_COMPOSTO_PATH, obter_mapa_do_cache
from web.janelas import janela_continente, gerar_janela_com_cache
from web.rotas._erros import registrar_erro_handler
from web.banco import obter_db
from cartographer.config import CARTOGRAPHER_CONFIG
from cartographer.math.climate import Bioma
from cartographer.cities.escala import metros_por_pixel_mundo, tabela_zoom_min
from config import cfg_get, get_config
from PIL import Image

mapa_bp = Blueprint('mapa', __name__)
registrar_erro_handler(mapa_bp)


@mapa_bp.route('/api/mapa_composto/imagem')
def api_mapa_composto_imagem():
    img_io, mimetype = render_npz_map_to_bytes(MAPA_COMPOSTO_PATH)
    return send_file(img_io, mimetype=mimetype)


@mapa_bp.route('/api/mapa_composto/info/<int:x>/<int:y>')
def api_mapa_composto_info(x, y):
    mapa = obter_mapa_do_cache(MAPA_COMPOSTO_PATH)
    if mapa is None:
        return jsonify({"error": "Mapa Composto não encontrado"}), 404
    height, width, _ = mapa.shape

    if x < 0 or x >= width or y < 0 or y >= height:
        return jsonify({"error": "Coordenada fora dos limites"}), 400

    altitude = float(mapa[y, x, 0])
    temperatura = float(mapa[y, x, 1])
    umidade = float(mapa[y, x, 2])
    id_bioma = int(mapa[y, x, 3])

    bioma = Bioma.por_id(id_bioma)
    nome_bioma = bioma.rotulo if bioma else "Desconhecido"

    # Calcula a qual tile (tx, ty) de 256x256 pertence
    tile_x = x // 256
    tile_y = y // 256

    return jsonify({
        "x": x,
        "y": y,
        "altitude": altitude,
        "temperatura": temperatura,
        "umidade": umidade,
        "bioma_id": id_bioma,
        "bioma_nome": nome_bioma,
        "tile_x": tile_x,
        "tile_y": tile_y
    })


@mapa_bp.route('/api/continentes')
def api_continentes():
    """
    Retorna a lista de continentes do world_manifest.json. Fase 0: a imagem de zoom do
    continente é gerada sob demanda por `gerar_janela()` (não mais um `.npz` pré-gerado),
    então todo continente listado já está "pronto" — a geração acontece na primeira
    requisição de `/api/continente/<uuid>/imagem` e é rápida (~250ms sem cache).
    """
    manifest = obter_manifesto()
    continentes = []
    if manifest:
        # T05 (docs/12_PLANO_CIDADE_VIVA.md): o manifesto não guarda o id numérico da
        # cidade (é atribuído só na importação, RepositorioMundo.salvar_cidade) — o
        # frontend precisa dele pra pedir /api/cidade/<id>/lotes_alterados da cidade
        # que está olhando. Uma consulta só (não uma por cidade) monta o mapa nome->id.
        id_por_nome = {cid.nome: db_id for db_id, cid in obter_db().mundo.carregar_cidades_por_id().items()}
        for c in manifest.get("continentes", []):
            cidades = []
            for cid in c.get("cidades", []):
                cidades.append({**cid, "cidade_id": id_por_nome.get(cid["nome"])})
            continentes.append({
                "uuid": c["uuid"],
                "nome": c["nome"],
                "area_real_km2": c.get("area_real_km2", 0),
                "biomas_predominantes": c.get("biomas_predominantes", []),
                "bounding_box": c.get("bounding_box", {}),
                "cidades": cidades,
                "gerado": True
            })

    dimensao_global_padrao = cfg_get(CARTOGRAPHER_CONFIG, "mundo_tiles_por_lado") * cfg_get(CARTOGRAPHER_CONFIG, "tile_size_px")
    return jsonify({
        "continentes": continentes,
        # Tamanho real do mapa mundi (lado do quadrado, em pixels) — vem do manifesto
        # quando existe, senão é derivado do config (nunca um `768` escrito à mão — mesma
        # lição da Frente 1: ver docs/05_ROADMAP.md).
        "dimensao_global": (manifest or {}).get("dimensao_global") or dimensao_global_padrao,
        # A imagem de zoom do continente cobre bounding_box + essa margem de cada lado
        # (Fase 0: `janela_continente` usa o mesmo padding) — o frontend precisa saber
        # disso pra posicionar o overlay nos limites certos (Frente 6, achado de bug).
        "janela_padding_px": cfg_get(CARTOGRAPHER_CONFIG, "janela_padding_px"),
        # Zoom máximo do Leaflet (Fase 0.6): decisão de custo/UI, não limite técnico —
        # o raster pode ser gerado em qualquer zoom (`gerar_janela` é resolução-livre).
        "tile_zoom_maximo_ui": cfg_get(CARTOGRAPHER_CONFIG, "tile_zoom_maximo_ui"),
        # D5/D2 do DIAGNOSTICO_V3: acima deste zoom o raster não tem detalhe NOVO — o
        # Leaflet estica em vez de pedir tile novo ao servidor (ver maxNativeZoom).
        "tile_max_native_zoom": cfg_get(CARTOGRAPHER_CONFIG, "tile_max_native_zoom"),
        # Fase 3: acima deste zoom, o nome da cidade fica permanentemente visível
        # (sem precisar de hover) — antes um número solto no JS.
        "mapa_features_tooltip_zoom_min": cfg_get(CARTOGRAPHER_CONFIG, "mapa_features_tooltip_zoom_min"),
        # `{tamanho: {camada: zoom_min}}`, a MESMA tabela que o gerador grava em cada
        # feature de cidade (cartographer/cities/escala.py) — evita 2 números escritos à
        # mão no popup do frontend, que já estavam errados em relação ao config.
        "cidade_zoom_min_por_tamanho": tabela_zoom_min(CARTOGRAPHER_CONFIG),
        # Lado do pixel de mundo em metros. É o que deixa o frontend desenhar em unidade
        # real: largura de rua, recuo, footprint. Derivado da ÁREA do pixel (D1), nunca
        # escrito à mão.
        "metros_por_pixel_mundo": metros_por_pixel_mundo(CARTOGRAPHER_CONFIG),
        # Largura das vias em metros por classe, e o piso em px de tela pra via não sumir
        # no zoom em que a camada acende. Servido (não gravado na feature) pra calibrar
        # sem regerar as cidades.
        "cidade_via_largura_m_por_classe": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_m_por_classe"),
        "cidade_via_largura_min_px": cfg_get(CARTOGRAPHER_CONFIG, "cidade_via_largura_min_px"),
        # M03 (docs/16_PLANO_PAINEL_E_IA.md): TTL do cache de lotes_alterados por
        # cidade no Mapa Live — servido, não copiado no JS (ARQUITETURA §10 regra 6).
        "mapa_lotes_alterados_cache_ms": cfg_get(get_config(), "painel", "mapa_lotes_alterados_cache_ms"),
        # M04: zoom mínimo e intervalo de polling da camada de NPCs — o front lê
        # daqui; teto de pontos e raio de espalhamento são parâmetros só do
        # servidor (aplicados em /api/mapa/npcs), servidos aqui pra inspeção/
        # transparência, sem duplicação em nenhum dos dois lados.
        "mapa_npcs_zoom_min": cfg_get(get_config(), "painel", "mapa_npcs_zoom_min"),
        "mapa_npcs_max_pontos": cfg_get(get_config(), "painel", "mapa_npcs_max_pontos"),
        "mapa_npcs_espalhamento_m": cfg_get(get_config(), "painel", "mapa_npcs_espalhamento_m"),
        "mapa_npcs_polling_ms": cfg_get(get_config(), "painel", "mapa_npcs_polling_ms"),
        # Tabela de biomas (id -> rótulo/emoji) — o frontend consome daqui em vez de
        # manter uma cópia própria (R-B06: já divergiu uma vez, com um bioma "Zona Urbana"
        # inventado no JS que não existe no classificador).
        "biomas": {b.id_numerico: {"rotulo": b.rotulo, "emoji": b.emoji} for b in Bioma},
    })


@mapa_bp.route('/api/continente/<uuid>/imagem')
def api_continente_imagem(uuid):
    """
    Retorna a imagem renderizada do continente: janela de mundo (bbox + padding) avaliada
    por `TileCartographer.gerar_janela()` sob demanda — Fase 0, não é mais um recorte de
    `.npz` pré-gerado (a fonte antiga usava índice local, P0.4).
    """
    manifest = obter_manifesto()
    if not manifest:
        return jsonify({"error": "Mundo não gerado"}), 404
    continente = next((c for c in manifest.get("continentes", []) if c["uuid"] == uuid), None)
    if not continente:
        return jsonify({"error": "Continente não encontrado"}), 404

    x0, y0, x1, y1, largura_img, altura_img = janela_continente(continente, manifest)
    dados, mundo_px_por_img_px = gerar_janela_com_cache(
        f"continente:{uuid}", x0, y0, x1, y1, largura_img, altura_img)
    if dados is None:
        return jsonify({"error": "Mundo não gerado"}), 404

    rgb = render_npz_array(dados, mundo_px_por_img_px=mundo_px_por_img_px)
    img_io = io.BytesIO()
    Image.fromarray(rgb).save(img_io, format='PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@mapa_bp.route('/api/continente/<uuid>/info/<int:x>/<int:y>')
def api_continente_info(uuid, x, y):
    """
    Retorna detalhes de bioma, altitude, temperatura e umidade da coordenada (x,y) da
    imagem retornada por `/api/continente/<uuid>/imagem` — mesma janela, reaproveitada do
    cache em memória do processo (`gerar_janela_com_cache`) para não regerar a cada hover.
    """
    manifest = obter_manifesto()
    if not manifest:
        return jsonify({"error": "Mundo não gerado"}), 404
    continente = next((c for c in manifest.get("continentes", []) if c["uuid"] == uuid), None)
    if not continente:
        return jsonify({"error": "Continente não encontrado"}), 404

    wx0, wy0, wx1, wy1, largura_img, altura_img = janela_continente(continente, manifest)
    mapa, _ = gerar_janela_com_cache(f"continente:{uuid}", wx0, wy0, wx1, wy1, largura_img, altura_img)
    if mapa is None:
        return jsonify({"error": "Zoom do continente não gerado"}), 404
    height, width, _ = mapa.shape

    if x < 0 or x >= width or y < 0 or y >= height:
        return jsonify({"error": "Coordenada fora dos limites"}), 400

    altitude = float(mapa[y, x, 0])
    temperatura = float(mapa[y, x, 1])
    umidade = float(mapa[y, x, 2])
    id_bioma = int(mapa[y, x, 3])

    bioma = Bioma.por_id(id_bioma)
    nome_bioma = bioma.rotulo if bioma else "Desconhecido"

    return jsonify({
        "x": x,
        "y": y,
        "altitude": altitude,
        "temperatura": temperatura,
        "umidade": umidade,
        "bioma_id": id_bioma,
        "bioma_nome": nome_bioma,
        "map_width": width,
        "map_height": height
    })
