from ...models import Acao, ESCALA_MAXIMA
from ...config_loader import cfg_get
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorDormir(AvaliadorDeUtilidade):
    """Durante o expediente: só quer dormir se estiver exausto (energia abaixo do
    limiar de desmaio) ou já estiver no meio de um descanso forçado — e mesmo assim,
    fome urgente no happy hour derruba a vontade. Fora do expediente: madrugada é sono
    absoluto (ninguém vaga pelas ruas de noite); no resto, dorme leve se a energia
    estiver baixa."""
    acao = Acao.DORMIR

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc, hora_atual = ctx.npc, ctx.hora
        cfg = cfg_get(ctx.config, "ia_decisao")
        energia_quase_descansado = cfg_get(cfg, "energia_quase_descansado")
        utilidade_dormir_maxima = cfg_get(cfg, "utilidade_dormir_maxima")

        if cfg_get(cfg, "hora_inicio_trabalho") <= hora_atual < cfg_get(cfg, "hora_inicio_sono_obrigatorio"):
            esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < energia_quase_descansado)
            exausto_ou_descansando = npc.energia < cfg_get(cfg, "energia_limiar_desmaio") or esta_descansando

            valor = utilidade_dormir_maxima if exausto_ou_descansando else 0.0
            if (npc.fome > cfg_get(cfg, "fome_urgente_limiar")
                    and npc.acao_atual != Acao.DORMIR
                    and not exausto_ou_descansando):
                valor = 0.0
            return valor

        hora_fim_sono = cfg_get(cfg, "hora_fim_sono_obrigatorio")
        if hora_atual >= cfg_get(cfg, "hora_inicio_sono_obrigatorio") or hora_atual < hora_fim_sono:
            return utilidade_dormir_maxima
        if npc.energia < cfg_get(cfg, "energia_satisfacao_sono") or npc.acao_atual == Acao.DORMIR:
            return (ESCALA_MAXIMA - npc.energia) * cfg_get(cfg, "multiplicador_dormir_leve")
        return 0.0
