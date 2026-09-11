from ...models import Acao
from ...config_loader import cfg_get
from .base import AvaliadorDeUtilidade, ContextoDecisao


class AvaliadorComer(AvaliadorDeUtilidade):
    """Quer comer se a fome já passou do gatilho (mais alto se estiver dormindo — não
    acorda por pouca fome) ou se já está no meio de uma refeição (não larga pela
    metade). Sem dinheiro pra pagar (e não sendo dependente/idoso, que têm sopão), o
    apetite esfria — prioriza trabalho ou sono."""
    acao = Acao.COMER

    def avaliar(self, ctx: ContextoDecisao) -> float:
        npc = ctx.npc
        cfg = cfg_get(ctx.config, "ia_decisao")

        esta_comendo = (npc.acao_atual == Acao.COMER
                         and npc.fome > cfg_get(cfg, "esta_comendo_fome_minima"))
        gatilho_fome = (cfg_get(cfg, "gatilho_fome_dormindo") if npc.acao_atual == Acao.DORMIR
                        else cfg_get(cfg, "gatilho_fome_normal"))
        if not (npc.fome > gatilho_fome or esta_comendo):
            return 0.0

        valor_fome = npc.fome * cfg_get(cfg, "multiplicador_valor_fome")
        if esta_comendo:
            valor_fome += cfg_get(cfg, "bonus_nao_interromper_refeicao")

        custo_refeicao = cfg_get(ctx.config, "acoes", "comer", "custo_pc")
        if not npc.eh_dependente() and not npc.is_idoso() and npc.dinheiro_total_pc < custo_refeicao:
            valor_fome *= cfg_get(cfg, "fator_fome_sem_dinheiro")
        return valor_fome
