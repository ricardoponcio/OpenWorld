from ...models import Acao
from ...config_loader import cfg_get
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorOcioso(AvaliadorDeUtilidade):
    """Piso de utilidade — sempre um pouco disponível, pra nunca faltar uma ação
    quando nada mais se aplica."""
    acao = Acao.OCIOSO

    def avaliar(self, ctx: ContextoDecisao) -> float:
        cfg = cfg_get(ctx.config, "ia_decisao")
        return cfg_get(cfg, "utilidade_ociosa_base")
