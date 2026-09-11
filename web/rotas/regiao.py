from flask import Blueprint, jsonify, send_file
import io
import os
import json
from PIL import Image
from web.helpers import render_npz_array, obter_manifesto
from web.janelas import janela_regiao, gerar_janela_com_cache
from web.rotas._erros import registrar_erro_handler
from engine.database import DatabaseManager

regiao_bp = Blueprint('regiao', __name__)
registrar_erro_handler(regiao_bp)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'openworld.db'))


def _encontrar_cidade(manifest, nome):
    needle = nome.strip().lower()
    for cont in manifest.get("continentes", []):
        for cid in cont.get("cidades", []):
            if cid["nome"].lower() == needle:
                return cid
    return None


@regiao_bp.route('/api/regiao/<nome>/imagem')
def api_regiao_imagem(nome):
    """
    D7 do DIAGNOSTICO_V3 (2026-09-11): renomeado de `/api/cidade/<nome>/imagem` — o nome
    antigo prometia "a cidade" e entregava 380km de terreno regional (Seção 9), o que o
    usuário reportou como "ainda é 1px na cidade". Esta rota é explicitamente a vista
    REGIONAL: onde a cidade fica no continente, não o que tem dentro dela (isso é a camada
    vetorial de detalhe de cidade, D3, visível no Mapa Live).

    Retorna a imagem renderizada da região ao redor da cidade: janela de mundo centrada em
    `(x_global, y_global)` com raio `regiao_janela_raio_px`, avaliada por
    `TileCartographer.gerar_janela()` sob demanda — Fase 0, não é mais um recorte de
    `.npz` pré-gerado (a fonte antiga usava índice local, P0.4).

    ⚠️ A cidade é sub-pixel nesta escala de mundo (1 px = 15,81 km, Seção 2.2/2.4) — esta
    imagem mostra o TERRENO ao redor da cidade, não a cidade em si (ruas/muralha/edifícios).
    """
    manifest = obter_manifesto()
    if not manifest:
        return jsonify({"error": "Mundo não gerado"}), 404
    cidade = _encontrar_cidade(manifest, nome)
    if not cidade:
        return jsonify({"error": "Cidade não encontrada"}), 404

    x0, y0, x1, y1, largura_img, altura_img = janela_regiao(cidade, manifest)

    dados, mundo_px_por_img_px = gerar_janela_com_cache(
        f"cidade:{nome.lower()}", x0, y0, x1, y1, largura_img, altura_img)
    if dados is None:
        return jsonify({"error": "Mundo não gerado"}), 404

    rgb = render_npz_array(dados, mundo_px_por_img_px=mundo_px_por_img_px)
    img_io = io.BytesIO()
    Image.fromarray(rgb).save(img_io, format='PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@regiao_bp.route('/api/regiao/<nome>/entities')
def api_regiao_entities(nome):
    """
    D7 do DIAGNOSTICO_V3: renomeado de `/api/cidade/<nome>/entities`, mesma razão da rota
    de imagem acima — isto é a vista REGIONAL.

    Retorna locais e NPCs para serem renderizados sobre o mapa da região na UI.

    Fase 2.1 (P0.3): `locais.coordenadas` agora é pixel de MUNDO (Seção 2.3), não mais
    um par 5-35 numa grade local sem relação com o mapa real. O frontend precisa saber
    a janela (bbox em mundo) e a resolução em que `/api/regiao/<nome>/imagem` foi
    renderizada pra poder converter mundo -> pixel de imagem (mesma fórmula da Seção
    2.3: `ix = (x-mnx)/(mxx-mnx)*w`) — por isso a bbox e a resolução vêm aqui, e não
    são mais um número solto no JS.
    """
    manifest = obter_manifesto()
    if not manifest:
        return jsonify({"locais": [], "npcs": [], "bbox": None})
    cidade_manifesto = _encontrar_cidade(manifest, nome)

    if not os.path.exists(DB_PATH):
        return jsonify({"locais": [], "npcs": [], "bbox": None})

    db = DatabaseManager(DB_PATH)
    with db.connection() as conn:
        cursor = conn.cursor()
        cidade_row = cursor.execute('SELECT id FROM cidades WHERE nome = ?', (nome,)).fetchone()
        if not cidade_row:
            return jsonify({"locais": [], "npcs": [], "bbox": None})

        cidade_id = cidade_row['id']

        locais = []
        for r in cursor.execute('SELECT id, nome, tipo, categoria, coordenadas FROM locais WHERE cidade_id = ?', (cidade_id,)).fetchall():
            d = dict(r)
            d['coordenadas'] = json.loads(d['coordenadas']) if d['coordenadas'] else [0, 0]
            locais.append(d)

        npcs = []
        for r in cursor.execute('SELECT id, nome, profissao, genero, localizacao_atual_id, acao_atual FROM npcs WHERE cidade_id = ?', (cidade_id,)).fetchall():
            npcs.append(dict(r))

    bbox = None
    if cidade_manifesto:
        x0, y0, x1, y1, largura_img, altura_img = janela_regiao(cidade_manifesto, manifest)
        bbox = {"min_x": x0, "min_y": y0, "max_x": x1, "max_y": y1,
                "largura_img": largura_img, "altura_img": altura_img}

    return jsonify({"locais": locais, "npcs": npcs, "bbox": bbox})
