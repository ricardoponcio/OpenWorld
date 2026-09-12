from web.rotas.mapa import mapa_bp
from web.rotas.regiao import regiao_bp
from web.rotas.tiles import tiles_bp
from web.rotas.features import features_bp
from web.rotas.cidade import cidade_bp


def registrar_blueprints(app):
    """Ponto único de registro dos blueprints de mapa (R-D07) — antes um único
    `composed_bp` de 633 linhas misturava rotas de mundo, região, tiles e camadas
    vetoriais; agora cada assunto vive no seu próprio arquivo."""
    app.register_blueprint(mapa_bp)
    app.register_blueprint(regiao_bp)
    app.register_blueprint(tiles_bp)
    app.register_blueprint(features_bp)
    app.register_blueprint(cidade_bp)
