"""
SCRIPT: bench_avanco.py
OBJETIVO: Medir quanto tempo real leva pra avançar N dias simulados — o número que
          justifica o Bloco A inteiro (docs/PLANO_POPULACAO_E_ESCALA.md, D13): 7 dias
          simulados em menos de 30 s, com 25.000 NPCs. Reporta segundos totais, ms por
          tick, decisões avaliadas por tick (A02 — tem que cair de milhares para
          algumas dezenas) e o tamanho final da fila de log (A07 — sem teto, um avanço
          rápido é vazamento de memória com outro nome).
MOMENTO DE USO: depois de qualquer tarefa do Bloco A, e na parada obrigatória nº 3 do
                plano (depois de A03).

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine. Não importe este módulo de
dentro de engine/, web/ ou cartographer/ — não faz parte do runtime.
"""
import os
import sys
import time
import argparse

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from config import get_config
from engine.loop import GameLoop
from engine.logger import WorldLogger
from engine.mundo import EstadoDoMundo
from builder.fix.bench_tick import montar_mundo_sintetico

ALVO_SEGUNDOS_POR_7_DIAS = 30.0  # D13, docs/PLANO_POPULACAO_E_ESCALA.md


def avancar_dias(loop: GameLoop, dias: int, mundo: EstadoDoMundo) -> dict:
    """Avança `dias` dias simulados (1 tick = 1 minuto) e devolve as métricas —
    função pura o bastante pra ser reusada por um teste, se um dia precisar.
    `mundo` só pra ler `data_simulada.hour` (o mesmo objeto passado a `GameLoop`
    — `loop` não expõe isso publicamente, e não devia só pra este script ler).

    H06 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): além da média, registra decisões/ms POR
    HORA do dia simulado e o MAIOR pico de decisões num único tick — os dois números
    que expõem a manada (armadilha 14). Sem eles, H03 (jitter nas fronteiras de
    relógio) é impossível de validar: uma média geral esconde um tick de 25.000
    decisões atrás de 1.439 ticks quase vazios."""
    n_ticks = dias * 24 * 60
    soma_decisoes = 0
    pico_decisoes_tick = 0
    por_hora = {h: {"decisoes": 0, "segundos": 0.0, "ticks": 0} for h in range(24)}
    inicio = time.perf_counter()
    for _ in range(n_ticks):
        hora = mundo.data_simulada.hour
        antes = time.perf_counter()
        loop.executar_tick()
        depois = time.perf_counter()
        decisoes = loop.decisoes_avaliadas_no_ultimo_tick
        soma_decisoes += decisoes
        pico_decisoes_tick = max(pico_decisoes_tick, decisoes)
        registro_hora = por_hora[hora]
        registro_hora["decisoes"] += decisoes
        registro_hora["segundos"] += depois - antes
        registro_hora["ticks"] += 1
    total_segundos = time.perf_counter() - inicio

    return {
        "n_ticks": n_ticks,
        "segundos": total_segundos,
        "ms_por_tick": 1000.0 * total_segundos / n_ticks,
        "decisoes_media_por_tick": soma_decisoes / n_ticks,
        "pico_decisoes_tick": pico_decisoes_tick,
        "por_hora": por_hora,
        "fila_de_log": WorldLogger._log_queue.qsize(),
    }


def imprimir_relatorio_por_hora(por_hora: dict):
    print(f"\n{'hora':>4}  {'decisões/tick':>14}  {'ms/tick':>8}")
    for hora in sorted(por_hora):
        r = por_hora[hora]
        if r["ticks"] == 0:
            continue
        decisoes_media = r["decisoes"] / r["ticks"]
        ms_media = 1000.0 * r["segundos"] / r["ticks"]
        print(f"{hora:>4}  {decisoes_media:>14.1f}  {ms_media:>8.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=7, help="dias simulados a avançar (padrão: 7)")
    parser.add_argument("--npcs", type=int, default=25000, help="NPCs no mundo sintético (padrão: 25000)")
    parser.add_argument("--locais", type=int, default=60000, help="locais no mundo sintético (padrão: 60000)")
    parser.add_argument("--cidades", type=int, default=40, help="cidades no mundo sintético (padrão: 40)")
    parser.add_argument("--sem-avanco-rapido", action="store_true",
                        help="não suprime info/debug do WorldLogger (A07) — só pra comparar o custo do log")
    parser.add_argument("--por-hora", action="store_true",
                        help="imprime decisões/ms médios POR HORA do dia simulado (H06) — expõe a manada")
    args = parser.parse_args()

    if not args.sem_avanco_rapido:
        WorldLogger.ativar_modo_avanco_rapido()

    config = get_config()
    mundo = montar_mundo_sintetico(args.npcs, args.locais, args.cidades)
    loop = GameLoop(mundo, config)

    print(f"Avançando {args.dias} dia(s) simulado(s) — {args.npcs} NPCs, {args.locais} locais, "
          f"{args.cidades} cidades. Alvo (D13): {ALVO_SEGUNDOS_POR_7_DIAS:.0f} s para 7 dias com 25.000 NPCs.")
    metricas = avancar_dias(loop, args.dias, mundo)

    print(f"{'ticks':>8}  {'segundos':>9}  {'ms/tick':>8}  {'decisões/tick (média)':>22}  {'pico/tick':>9}  {'fila de log':>11}")
    print(f"{metricas['n_ticks']:>8}  {metricas['segundos']:>9.1f}  {metricas['ms_por_tick']:>8.2f}  "
          f"{metricas['decisoes_media_por_tick']:>22.1f}  {metricas['pico_decisoes_tick']:>9}  {metricas['fila_de_log']:>11}")

    if args.por_hora:
        imprimir_relatorio_por_hora(metricas["por_hora"])

    if args.dias == 7 and args.npcs == 25000:
        veredito = "OK" if metricas["segundos"] <= ALVO_SEGUNDOS_POR_7_DIAS else "ESTOURA"
        print(f"\nD13 (7 dias / 25.000 NPCs / {ALVO_SEGUNDOS_POR_7_DIAS:.0f} s): {veredito} "
              f"({metricas['segundos']:.1f} s)")


if __name__ == "__main__":
    main()
