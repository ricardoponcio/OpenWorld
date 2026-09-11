"""
MODULE: utilidade/modificadores.py
FUNÇÃO: Modificadores transversais de utilidade — aplicados depois dos avaliadores.

DESCRIÇÃO:
    Diferente de um avaliador (que calcula a utilidade de UMA ação), um modificador lê
    e ajusta o dicionário de utilidades inteiro — humor, eventos globais, a trava de
    dependente, e o bônus de persistência (R-D01).
"""
import json
from ...models import Acao, HumorNPC
from ...config_loader import cfg_get
from ...logger import WorldLogger


def aplicar_humor(utilidades: dict, ctx) -> dict:
    """NPC em pânico/medo/angústia prefere se esconder em casa a socializar."""
    npc = ctx.npc
    if npc.humor in (HumorNPC.PANICO.value, HumorNPC.MEDO.value, HumorNPC.ANGUSTIADO.value):
        cfg = cfg_get(ctx.config, "ia_decisao")
        utilidades[Acao.DORMIR] += cfg_get(cfg, "bonus_dormir_medo")
        utilidades[Acao.SOCIALIZAR] -= cfg_get(cfg, "penalidade_socializar_medo")
    return utilidades


def aplicar_eventos_globais(utilidades: dict, ctx) -> dict:
    """Eventos globais ativos (clima, economia, ...) empurram utilidades por ação."""
    for ev in ctx.eventos_globais:
        try:
            mods = json.loads(ev['modificadores'])
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            WorldLogger.warning(f"[IA] Evento global com modificadores inválidos, ignorado: {e}")
            continue
        for acao_str, peso in mods.items():
            if acao_str in Acao.__members__:
                utilidades[Acao[acao_str]] += peso
    return utilidades


def aplicar_trava_dependente(utilidades: dict, ctx) -> dict:
    """Bebê, criança ou adulto marcado como dependente não trabalha, não socializa
    fora de casa e não cuida de ninguém."""
    if ctx.npc.eh_dependente():
        utilidades[Acao.TRABALHAR] = 0.0
        utilidades[Acao.SOCIALIZAR] = 0.0
        utilidades[Acao.CUIDAR_PROLE] = 0.0
    return utilidades


def aplicar_persistencia(utilidades: dict, ctx) -> dict:
    """Pequeno bônus pra ação atual, pra evitar NPCs trocando de ideia a cada tick."""
    cfg = cfg_get(ctx.config, "ia_decisao")
    if ctx.npc.acao_atual in utilidades and utilidades[ctx.npc.acao_atual] > 0.0:
        utilidades[ctx.npc.acao_atual] += cfg_get(cfg, "bonus_persistencia")
    return utilidades
