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
mude o que o NPC quer ou que tenha efeito de consequência. Por isso `minutos_ate_cruzar`
arredonda pra BAIXO (nunca pra cima): errar pra menos custa uma reavaliação a mais;
errar pra mais pula o cruzamento.

Só as ações "estáveis" (`ACOES_LOTEAVEIS`) recebem salto grande. Isso era, em A02,
`Acao.DORMIR`/`TRABALHAR`/`OCIOSO` só — `Acao.COMER`, `Acao.CONSTRUIR` e
`Acao.CUIDAR_PROLE` ficavam de fora por terem estado interno próprio (ver Registro de
execução, tarefa A02).

H04 (docs/PLANO_AVANCO_E_CALIBRAGEM.md) generalizou as três, porque cada uma termina
exatamente num CRUZAMENTO calculável, igual fome/energia — só que dois deles moram
fora do NPC, e agenda.py continua sem ler `mundo` (R-F01: "Funções puras" acima).
Pra esses dois, `calcular_proximo_instante` aceita `candidatos_extra`: números já
calculados por quem TEM acesso ao mundo (`GameLoop`), com a MESMA `minutos_ate_cruzar`
que fome/energia usam — nunca uma segunda fórmula.
  - `CUIDAR_PROLE` termina quando a energia do cuidador cruza
    `energia_minima_cuidar_prole` — isso já está no NPC, vira candidato comum.
  - `CONSTRUIR` termina quando `obra.integridade` cruza 100 — mora em `mundo.locais`,
    então entra via `candidatos_extra`.
  - `COMER` termina quando a fome cruza `esta_comendo_fome_minima` (comum) OU
    (`candidatos_extra`) quando o saldo do PAGADOR não sustenta mais preço cheio —
    o menor dos dois. Isso é DELIBERADAMENTE conservador: a refeição cai em três
    ramos (preço cheio, parcial, sopão) dependendo do saldo no minuto exato, e pular
    ticks em bloco arriscaria pular por cima do minuto em que o dinheiro acaba,
    mudando quem recebeu sopão e quem não. `NPCActionManager.
    minutos_seguros_para_pular_comer` nunca deixa o bloco ultrapassar o saldo
    disponível, e o efeito em lote (`GameLoop._aplicar_efeito_continuo`) só aplica o
    ramo de preço cheio — o parcial e o sopão continuam exigindo o minuto real.
"""
import math
import random
import zlib
from datetime import timedelta
from ..models import Acao, Genero
from ..config_loader import cfg_get

ACOES_LOTEAVEIS = frozenset((Acao.DORMIR, Acao.TRABALHAR, Acao.OCIOSO,
                              Acao.CUIDAR_PROLE, Acao.CONSTRUIR, Acao.COMER))

INFINITO = float("inf")


def em_consequencia(npc, cfg_bio) -> bool:
    """Estado de CONSEQUÊNCIA (fome acima do limiar de inanição) nunca pula — é
    reavaliado todo tick até sair dele, mesmo que `proximo_instante_decisao` aponte
    pro futuro (armadilha 11, classe 2).

    H01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 13): usada como regra de
    ENTRADA/SAÍDA do conjunto `EstadoDoMundo.npcs_em_consequencia`
    (`mundo.marcar_consequencia`) — chamada só pra quem já está sendo processado
    neste tick, nunca mais varrida sobre os NPCs do mundo inteiro."""
    return npc.fome > cfg_get(cfg_bio, "inaniacao_fome_limiar")


def npc_esta_em_dia(npc, agora, cfg_bio) -> bool:
    """Predicado puro equivalente ao que a agenda de baldes (H01) mantém — usado nos
    testes deste módulo e como referência de comportamento; `GameLoop` não chama mais
    isto pra cada NPC do mundo a cada tick (era exatamente o custo O(NPCs) que H01
    eliminou)."""
    if em_consequencia(npc, cfg_bio):
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


def minutos_ate_cruzar(valor_atual: float, taxa_por_minuto: float, limiar: float) -> float:
    """Quantos minutos, no MÁXIMO, até `valor_atual` cruzar `limiar` andando à
    `taxa_por_minuto` — arredondado pra baixo de propósito. `INFINITO` se a taxa não
    aproxima o valor do limiar nessa direção (ex.: taxa positiva com limiar já
    ultrapassado, ou taxa zero)."""
    if taxa_por_minuto > 0 and limiar > valor_atual:
        return math.floor((limiar - valor_atual) / taxa_por_minuto)
    if taxa_por_minuto < 0 and limiar < valor_atual:
        return math.floor((valor_atual - limiar) / -taxa_por_minuto)
    return INFINITO


def _desvio_jitter_fronteira_min(npc, config) -> int:
    """H03 (docs/PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 14): deslocamento
    determinístico por NPC — `zlib.crc32`, NUNCA `hash()` (varia por processo,
    `PYTHONHASHSEED`) nem `random` puro (tornaria o mundo irreproduzível com a mesma
    seed). Sempre o MESMO valor pro mesmo `npc.id`, em qualquer chamada, em qualquer
    processo. Usado só pra ATRASAR fronteiras de relógio (fim do sono obrigatório,
    início/fim de expediente) que, sem isto, seriam o MESMO instante pra todo NPC —
    nunca antecipa, só posterga dentro da janela configurada."""
    janela = cfg_get(config, "simulacao_jitter_fronteira_min")
    if janela <= 0:
        return 0
    return zlib.crc32(npc.id.encode("utf-8")) % janela


def _desvio_relativo_npc(npc, amplitude: float) -> float:
    """H03: multiplicador PERMANENTE e determinístico por NPC, entre
    `1-amplitude` e `1+amplitude` — mesma técnica de `_desvio_jitter_fronteira_min`,
    aplicada a um limiar de DECISÃO (não a um instante de relógio). Dessincroniza
    quem come antes/depois e dá personalidade (uns aguentam mais fome que outros)."""
    if amplitude <= 0:
        return 1.0
    fracao = (zlib.crc32(npc.id.encode("utf-8")) % 10_000) / 10_000.0  # [0, 1)
    return 1.0 + amplitude * (2.0 * fracao - 1.0)


def _minutos_ate_fim_do_sono_obrigatorio(agora, cfg_dec, desvio_min: int) -> float:
    """Só relevante enquanto dormindo dentro da janela de sono obrigatório — o
    instante em que a janela termina é uma rotina agendada (classe 3), não um
    cruzamento de necessidade. `desvio_min` (H03) atrasa o despertar deste NPC em
    particular — sem isto, todo mundo dormindo cruza a mesma fronteira no mesmo
    minuto (dez dos dez maiores picos medidos eram exatamente isto: 25.000 decisões
    num tick só, entre 06:29 e 06:37)."""
    inicio = cfg_get(cfg_dec, "hora_inicio_sono_obrigatorio")
    fim = cfg_get(cfg_dec, "hora_fim_sono_obrigatorio")
    hora, minuto = agora.hour, agora.minute
    dentro_da_janela = hora >= inicio or hora < fim
    if not dentro_da_janela:
        return INFINITO
    horas_ate_fim = (fim - hora) % 24
    return max(0, horas_ate_fim * 60 - minuto) + desvio_min


def _minutos_ate_fronteira_de_expediente(agora, hora_alvo: int, desvio_min: int) -> int:
    """H03: minutos até a PRÓXIMA vez que o relógio cruza `hora_alvo:00` (início ou
    fim de expediente), atrasado por `desvio_min` — mesmo raciocínio de
    `_minutos_ate_fim_do_sono_obrigatorio`, mas pra uma fronteira que não depende de
    estar "dentro de uma janela" (expediente é um único cruzamento por dia, não uma
    janela que pode não ter começado ainda)."""
    agora_total = agora.hour * 60 + agora.minute
    alvo_total = hora_alvo * 60
    diff = (alvo_total - agora_total) % (24 * 60)
    minutos = diff if diff > 0 else 24 * 60
    return minutos + desvio_min


def calcular_proximo_instante(npc, agora, config, candidatos_extra=None):
    """O coração de A02: devolve o próximo `datetime` em que este NPC precisa ser
    reavaliado. NUNCA além do teto de segurança
    (`simulacao_intervalo_maximo_decisao_min`) — a rede que transforma um `acordar`
    esquecido (A03) em atraso de algumas horas, não em NPC congelado pra sempre.

    `candidatos_extra` (H04, docs/PLANO_AVANCO_E_CALIBRAGEM.md): minutos adicionais
    calculados por quem TEM acesso a `mundo` (`GameLoop`/`NPCActionManager`) — pra
    CONSTRUIR (`obra.integridade` mora em `mundo.locais`) e COMER (quanto o saldo do
    PAGADOR sustenta). Continuam usando `minutos_ate_cruzar`, nunca uma fórmula
    própria; `calcular_proximo_instante` só os inclui na mesma conta de `min()`."""
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

    # H03 (docs/PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 14): os dois desvios
    # determinísticos deste NPC, calculados uma vez e reusados nos candidatos
    # abaixo — nunca em cima do limiar de CONSEQUÊNCIA (inaniação), que não é lugar
    # pra variação nenhuma.
    desvio_fronteira_min = _desvio_jitter_fronteira_min(npc, config)
    desvio_fome = _desvio_relativo_npc(npc, cfg_get(cfg_dec, "gatilho_fome_variacao_pct"))

    # Fome: só cresce (não há recuperação passiva). Pior caso = maior sorteio
    # possível da faixa — nunca subestime a velocidade de subida.
    taxa_fome = cfg_get(meta, "fome_base_ganho_max")
    if dormindo:
        taxa_fome *= cfg_get(meta, "multiplicador_fome_dormindo")
    if gravida:
        taxa_fome *= cfg_get(cfg_bio, "gravidez_multiplicador_ganho_fome")

    limiar_fome_decisao = (cfg_get(cfg_dec, "gatilho_fome_dormindo") if dormindo
                           else cfg_get(cfg_dec, "gatilho_fome_normal")) * desvio_fome
    limiar_fome_urgente = cfg_get(cfg_dec, "fome_urgente_limiar") * desvio_fome

    candidatos = [
        teto,
        minutos_ate_cruzar(npc.fome, taxa_fome, limiar_fome_decisao),
        minutos_ate_cruzar(npc.fome, taxa_fome, limiar_fome_urgente),
        # Classe 2 (consequência) — o mesmo cruzamento que `minutos_ate_cruzar`
        # calcula pras outras classes, só que este NUNCA pode ser pulado por cima
        # (é por isso que `npc_esta_em_dia` também o confere, todo tick, à parte).
        # NUNCA multiplicado por `desvio_fome` — limiar de consequência não varia.
        minutos_ate_cruzar(npc.fome, taxa_fome, cfg_get(cfg_bio, "inaniacao_fome_limiar")),
    ]

    # Energia: determinística (nenhum termo aleatório), então o cruzamento é exato,
    # não um pior caso.
    if dormindo:
        taxa_energia = cfg_get(cfg_get(cfg_acoes, "dormir"), "energia_ganho")  # cresce
        limiar_energia = cfg_get(cfg_dec, "energia_quase_descansado")
        candidatos.append(_minutos_ate_fim_do_sono_obrigatorio(agora, cfg_dec, desvio_fronteira_min))
    else:
        taxa_energia = -cfg_get(meta, "energia_base_perda")
        if gravida:
            taxa_energia *= cfg_get(cfg_bio, "gravidez_multiplicador_perda_energia")
        if npc.acao_atual == Acao.TRABALHAR:
            taxa_energia -= cfg_get(cfg_get(cfg_acoes, "trabalhar"), "energia_perda")
            candidatos.append(_minutos_ate_fronteira_de_expediente(
                agora, cfg_get(cfg_dec, "hora_fim_trabalho"), desvio_fronteira_min))
        elif npc.acao_atual == Acao.OCIOSO and npc.local_trabalho_id:
            candidatos.append(_minutos_ate_fronteira_de_expediente(
                agora, cfg_get(cfg_dec, "hora_inicio_trabalho"), desvio_fronteira_min))
        elif npc.acao_atual == Acao.CUIDAR_PROLE:
            # H04: cuidar da prole drena energia além do metabolismo base — o
            # cuidador larga a tarefa quando cruza `energia_minima_cuidar_prole`
            # (mais alto que o limiar de desmaio, então normalmente é o que vence
            # o min() abaixo).
            taxa_energia -= cfg_get(cfg_bio, "cuidar_prole_consumo_energia")
            candidatos.append(minutos_ate_cruzar(
                npc.energia, taxa_energia, cfg_get(cfg_dec, "energia_minima_cuidar_prole")))
        limiar_energia = cfg_get(cfg_dec, "energia_limiar_desmaio")

    candidatos.append(minutos_ate_cruzar(npc.energia, taxa_energia, limiar_energia))

    if candidatos_extra:
        candidatos.extend(candidatos_extra)

    minutos = max(1, min(candidatos))
    return agora + timedelta(minutes=minutos)
