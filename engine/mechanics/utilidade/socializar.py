from ...models import Acao, ESCALA_MAXIMA, TipoLocal
from ...config_loader import cfg_get
from ...consultas_local import LocationUtils
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorSocializar(AvaliadorDeUtilidade):
    """Bônus grande no happy hour (fim do expediente até o sono); fora dele, quer
    socializar proporcionalmente à solidão. Sem dinheiro e sem local público/gratuito
    por perto, a vontade cai a zero (não há onde ir de graça); com dependentes em
    casa, a vontade também é reduzida."""
    acao = Acao.SOCIALIZAR

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc, hora_atual = ctx.npc, ctx.hora
        cfg = cfg_get(ctx.config, "ia_decisao")

        valor = 0.0
        if cfg_get(cfg, "hora_fim_trabalho") < hora_atual < cfg_get(cfg, "hora_inicio_sono_obrigatorio"):
            valor = cfg_get(cfg, "bonus_happy_hour") + (ESCALA_MAXIMA - npc.social)
        elif hora_atual >= cfg_get(cfg, "hora_inicio_sono_obrigatorio") or hora_atual < cfg_get(cfg, "hora_inicio_trabalho"):
            valor = (ESCALA_MAXIMA - npc.social) * cfg_get(cfg, "multiplicador_socializar_fora_happy_hour")

        limiar_pobreza = cfg_get(cfg, "limiar_pobreza_pc")
        if npc.dinheiro_total_pc < limiar_pobreza:
            tem_local_gratis = False
            if ctx.locais:
                for l in ctx.locais.values():
                    if l.tipo == TipoLocal.SOCIAL.value and l.status == 1 and LocationUtils.is_local_publico(l):
                        tem_local_gratis = True
                        break
            if not tem_local_gratis:
                valor = 0.0
            else:
                valor *= cfg_get(cfg, "fator_socializar_com_local_publico_pobre")

        if npc.num_dependentes > 0:
            valor *= cfg_get(cfg, "fator_socializar_com_dependentes")
        return valor
