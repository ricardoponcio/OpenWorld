from flask import Blueprint, send_file, abort
import io
from cartographer.tiles.render import renderizar_tile_png

tiles_bp = Blueprint('tiles', __name__)
# Sem errorhandler genérico aqui (diferente dos outros blueprints): esta rota já usava
# `abort(404)` sem try/except no original, e um `@errorhandler(Exception)` intercepta
# HTTPException também — trocaria o 404 padrão do Flask/Leaflet por um JSON 500.


@tiles_bp.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def get_tile(z, x, y):
    """
    Serve o tile (z,x,y) do Mapa Live. Fase 0 (docs/06_PLANO_EVOLUCAO_V2.md): não é mais um
    recorte de mosaico pré-renderizado — é `TileCartographer.gerar_janela()` avaliada na
    bbox de mundo daquele tile, gerada na primeira vista e servida do cache em disco depois
    (chave = config_hash do manifesto, ver cartographer/tiles/render.py). Tile fora do
    mundo (manifesto ausente/incompleto) = 404; o Leaflet trata isso mostrando aquele
    quadrado em branco, sem quebrar o resto do mapa.
    """
    png_bytes = renderizar_tile_png(z, x, y)
    if png_bytes is None:
        abort(404)
    return send_file(io.BytesIO(png_bytes), mimetype='image/png')
