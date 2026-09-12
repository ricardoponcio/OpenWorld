"""
MODULE: agenda.py
FUNÇÃO: Agenda de decisões — quando um NPC precisa ser reavaliado (A02, docs/
PLANO_POPULACAO_E_ESCALA.md).

DESCRIÇÃO:
    Hoje o tick processa os 25.000 NPCs todo minuto simulado; medido, 99,83% deles
    decidem exatamente o mesmo que no minuto anterior. Este módulo calcula, para um
    NPC que acabou de ser processado, o PRÓXIMO instante em que vale a pena reavaliá-lo
    — o menor entre o cruzamento de limiar de decisão mais próximo (fome/energia), o de
    consequência mais próximo (nunca pulado — inanição), e um teto de segurança.

    Funções puras: recebem o NPC e a config, devolvem um instante ou um booleano.
    `GameLoop` é quem decide o que fazer com a resposta (R-F01: nenhum estado do
    mundo é lido ou escrito aqui).

ARMADILHA 11 (docs/PLANO_POPULACAO_E_ESCALA.md): um acumulador linear (fome, energia)
pode ser saltado com segurança contanto que o salto pare ANTES de qualquer limiar que
mude o que o NPC quer ou que tenha efeito de consequência. Por isso `_minutos_ate_cruzar`
arredonda pra BAIXO (nunca pra cima): errar pra menos custa uma reavaliação a mais;
errar pra mais pula o cruzamento.

Só as ações "estáveis" (`ACOES_LOTEAVEIS`) recebem salto grande. `Acao.COMER` (paga em
parcelas, `parcelas_refeicao` ticks), `Acao.CONSTRUIR` (termina ao cruzar 100% de
integridade) e `Acao.CUIDAR_PROLE` têm estado interno próprio de curta duração — ficam
de fora de propósito e são sempre reavaliadas no próximo minuto. Isso é uma escolha
consciente de escopo (ver Registro de execução, tarefa A02): generalizar o salto para
essas três exigiria calcular o instante de cada uma das suas próprias transições
internas, e nenhuma delas dura o bastante (algumas dezenas de ticks, no máximo) para o
ganho compensar o risco.
"""
import math
import random
from datetime import timedelta
from ..models import Acao, Genero
from ..config_loader import cfg_get

ACOES_LOTEAVEIS = frozenset((Acao.DORMIR, Acao.TRABALHAR, Acao.OCIOSO))

_INFINITO = float("inf")


def npc_esta_em_dia(npc, agora, cfg_bio) -> bool:
    """Estado de CONSEQUÊNCIA (fome acima do limiar de inanição) nunca pula — é
    reavaliado todo tick até sair dele, mesmo que `proximo_instante_decisao` aponte
    pro futuro (armadilha 11, classe 2)."""
    if npc.fome > cfg_get(cfg_bio, "inaniacao_fome_limiar"):
        return True
    if npc.proximo_instante_decisao is None:
        return True
    return npc.proximo_instante_decisao <= agora


def minutos_desde_ultima_avaliacao(npc, agora) -> int:
    if npc.ultima_avaliacao is None:
        return 1
    delta = agora - npc.ultima_avaliacao
    minutos = int(delta.total_seconds() // 60)
    return max(1, minutos)


def _minutos_ate_cruzar(valor_atual: float, taxa_por_minuto: float, limiar: float) -> float:
    """Quantos minutos, no MÁXIMO, até `valor_atual` cruzar `limiar` andando à
    `taxa_por_minuto` — arredondado pra baixo de propósito. `_INFINITO` se a taxa não
    aproxima o valor do limiar nessa direção (ex.: taxa positiva com limiar já
    ultrapassado, ou taxa zero)."""
    if taxa_por_minuto > 0 and limiar > valor_atual:
        return math.floor((limiar - valor_atual) / taxa_por_minuto)
    if taxa_por_minuto < 0 and limiar < valor_atual:
        return math.floor((valor_atual - limiar) / -taxa_por_minuto)
    return _INFINITO


def _minutos_ate_fim_do_sono_obrigatorio(agora, cfg_dec) -> float:
    """Só relevante enquanto dormindo dentro da janela de sono obrigatório — o
    instante em que a janela termina é uma rotina agendada (classe 3), não um
    cruzamento de necessidade."""
    inicio = cfg_get(cfg_dec, "hora_inicio_sono_obrigatorio")
    fim = cfg_get(cfg_dec, "hora_fim_sono_obrigatorio")
    hora, minuto = agora.hour, agora.minute
    dentro_da_janela = hora >= inicio or hora < fim
    if not dentro_da_janela:
        return _INFINITO
    horas_ate_fim = (fim - hora) % 24
    return max(0, horas_ate_fim * 60 - minuto)


def calcular_proximo_instante(npc, agora, config):
    """O coração de A02: devolve o próximo `datetime` em que este NPC precisa ser
    reavaliado. NUNCA além do teto de segurança
    (`simulacao_intervalo_maximo_decisao_min`) — a rede que transforma um `acordar`
    esquecido (A03) em atraso de algumas horas, não em NPC congelado pra sempre."""
    # Jitter no teto (80-100% do configurado): sem isto, uma população inteira
    # nascida no mesmo estado (ex.: todos ociosos, energia/fome no default) agenda
    # o MESMO instante futuro pra todo mundo — e volta a processar os 25.000 de uma
    # vez só a cada ciclo do teto, em vez de espalhado (medido: picos de ~860 ms a
    # cada 240 ticks num mundo sintético homogêneo, contra ~86 ms de média). O jitter
    # nunca ultrapassa o teto configurado, só o antecipa — mais seguro, nunca menos.
    teto = max(1, int(cfg_get(config, "simulacao_intervalo_maximo_decisao_min")
                       * random.uniform(0.8, 1.0)))

    if npc.acao_atual not in ACOES_LOTEAVEIS:
        return agora + timedelta(minutes=1)

    cfg_bio = cfg_get(config, "biologia_e_sociedade")
    cfg_dec = cfg_get(config, "ia_decisao")
    meta = cfg_get(config, "metabolismo")
    cfg_acoes = cfg_get(config, "acoes")

    dormindo = npc.acao_atual == Acao.DORMIR
    gravida = npc.genero == Genero.FEMININO.value and npc.gravidez_ticks > 0

    # Fome: só cresce (não há recuperação passiva). Pior caso = maior sorteio
    # possível da faixa — nunca subestime a velocidade de subida.
    taxa_fome = cfg_get(meta, "fome_base_ganho_max")
    if dormindo:
        taxa_fome *= cfg_get(meta, "multiplicador_fome_dormindo")
    if gravida:
        taxa_fome *= cfg_get(cfg_bio, "gravidez_multiplicador_ganho_fome")

    limiar_fome_decisao = (cfg_get(cfg_dec, "gatilho_fome_dormindo") if dormindo
                           else cfg_get(cfg_dec, "gatilho_fome_normal"))

    candidatos = [
        teto,
        _minutos_ate_cruzar(npc.fome, taxa_fome, limiar_fome_decisao),
        _minutos_ate_cruzar(npc.fome, taxa_fome, cfg_get(cfg_dec, "fome_urgente_limiar")),
        # Classe 2 (consequência) — o mesmo cruzamento que `_minutos_ate_cruzar`
        # calcula pras outras classes, só que este NUNCA pode ser pulado por cima
        # (é por isso que `npc_esta_em_dia` também o confere, todo tick, à parte).
        _minutos_ate_cruzar(npc.fome, taxa_fome, cfg_get(cfg_bio, "inaniacao_fome_limiar")),
    ]

    # Energia: determinística (nenhum termo aleatório), então o cruzamento é exato,
    # não um pior caso.
    if dormindo:
        taxa_energia = cfg_get(cfg_get(cfg_acoes, "dormir"), "energia_ganho")  # cresce
        limiar_energia = cfg_get(cfg_dec, "energia_quase_descansado")
        candidatos.append(_minutos_ate_fim_do_sono_obrigatorio(agora, cfg_dec))
    else:
        taxa_energia = -cfg_get(meta, "energia_base_perda")
        if gravida:
            taxa_energia *= cfg_get(cfg_bio, "gravidez_multiplicador_perda_energia")
        if npc.acao_atual == Acao.TRABALHAR:
            taxa_energia -= cfg_get(cfg_get(cfg_acoes, "trabalhar"), "energia_perda")
        limiar_energia = cfg_get(cfg_dec, "energia_limiar_desmaio")

    candidatos.append(_minutos_ate_cruzar(npc.energia, taxa_energia, limiar_energia))

    minutos = max(1, min(candidatos))
    return agora + timedelta(minutes=minutos)
