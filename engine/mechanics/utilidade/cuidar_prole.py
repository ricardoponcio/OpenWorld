from ...models import Acao, ESCALA_MAXIMA
from ...config_loader import cfg_get
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorCuidarProle(AvaliadorDeUtilidade):
    """Só quer cuidar da prole se tiver dependentes na mesma casa — proporcional à
    solidão, com preferência por fazer isso fora do horário de trabalho. Sem energia
    mínima, a vontade cai a zero (não adianta empurrar um NPC exausto pra cuidar de
    ninguém)."""
    acao = Acao.CUIDAR_PROLE

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc, hora_atual = ctx.npc, ctx.hora
        cfg = cfg_get(ctx.config, "ia_decisao")

        if npc.num_dependentes <= 0:
            return 0.0

        vontade_cuidar = (ESCALA_MAXIMA - npc.social) * cfg_get(cfg, "multiplicador_vontade_cuidar_prole")
        if not (cfg_get(cfg, "hora_inicio_trabalho") <= hora_atual <= cfg_get(cfg, "hora_fim_trabalho")):
            vontade_cuidar += cfg_get(cfg, "bonus_cuidar_prole_fora_expediente")
        if npc.energia < cfg_get(cfg, "energia_minima_cuidar_prole"):
            vontade_cuidar = 0.0
        return vontade_cuidar
