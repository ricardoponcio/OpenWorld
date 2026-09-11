from ...models import Acao
from ...config_loader import cfg_get
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorTrabalhar(AvaliadorDeUtilidade):
    """Quer trabalhar durante o expediente, se tiver emprego e não estiver exausto ou
    em descanso forçado."""
    acao = Acao.TRABALHAR

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc, hora_atual = ctx.npc, ctx.hora
        cfg = cfg_get(ctx.config, "ia_decisao")

        if not (npc.local_trabalho_id and cfg_get(cfg, "hora_inicio_trabalho") <= hora_atual <= cfg_get(cfg, "hora_fim_trabalho")):
            return 0.0

        energia_quase_descansado = cfg_get(cfg, "energia_quase_descansado")
        esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < energia_quase_descansado)
        if npc.energia < cfg_get(cfg, "energia_limiar_desmaio") or esta_descansando:
            return 0.0
        return cfg_get(cfg, "utilidade_trabalhar")
