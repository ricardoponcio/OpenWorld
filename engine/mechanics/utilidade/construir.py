from ...models import Acao
from ...config_loader import cfg_get
from ...consultas_npc import NPCUtils
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorConstruir(AvaliadorDeUtilidade):
    """Só quer construir se o NPC (ou o cônjuge) for dono de uma obra inacabada, tiver
    energia sobrando, e não estiver no expediente de trabalho formal nem na madrugada
    de sono profundo."""
    acao = Acao.CONSTRUIR

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc, hora_atual = ctx.npc, ctx.hora
        cfg = cfg_get(ctx.config, "ia_decisao")

        if not ctx.locais or npc.eh_dependente() or npc.energia < cfg_get(cfg, "energia_minima_construir"):
            return 0.0

        tem_trabalho_ativo = (npc.local_trabalho_id is not None and npc.local_trabalho_id != ""
                               and cfg_get(cfg, "hora_inicio_trabalho") <= hora_atual <= cfg_get(cfg, "hora_fim_trabalho"))
        hora_sono = (hora_atual >= cfg_get(cfg, "hora_inicio_sono_obrigatorio")
                     or hora_atual < cfg_get(cfg, "hora_fim_construir_madrugada"))

        if not tem_trabalho_ativo and not hora_sono and NPCUtils.obter_obra_do_npc(ctx.locais, npc):
            return cfg_get(cfg, "utilidade_construir")
        return 0.0
