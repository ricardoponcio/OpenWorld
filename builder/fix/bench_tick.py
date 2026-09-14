"""
SCRIPT: bench_tick.py
OBJETIVO: Medir o custo de `GameLoop.executar_tick()` contra o orçamento de performance
          do docs/12_PLANO_CIDADE_VIVA.md — D4 (1000 ms/tick, pra sustentar velocidade 60x)
          — variando NPCs, locais e cidades. É a ferramenta que P01-P07 usam para provar
          (ou refutar) que o índice por cidade/papel elimina a varredura O(NPCs × locais)
          medida na Seção 1.6 do plano (53,8 ms com 20 NPCs / 24 mil locais).
MOMENTO DE USO: depois de qualquer tarefa do Bloco P, e para decidir P06 (a ordem de
                investigação de performance — nunca paralelizar antes de medir).

⚠️ FERRAMENTA MANUAL DE DIAGNÓSTICO. Roda fora da engine. Não importe este módulo de
dentro de engine/, web/ ou cartographer/ — não faz parte do runtime.
"""
import os
import sys
import time
import argparse
import random
import tempfile
import shutil
from datetime import datetime

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from config import get_config
from engine.models import EstagioVida, TipoLocal, CategoriaLocal
from engine.mundo import EstadoDoMundo
from engine.loop import GameLoop
from engine.database import DatabaseManager
from tests.mundo_sintetico import BancoFalso, adulto, casa

ORCAMENTO_MS = 1000.0  # D4 do docs/12_PLANO_CIDADE_VIVA.md — velocidade 60x

_CATEGORIAS_NAO_RESIDENCIAIS = [
    (CategoriaLocal.TAVERNA, TipoLocal.SOCIAL),
    (CategoriaLocal.MERCADO, TipoLocal.LOJA),
    (CategoriaLocal.FORJA, TipoLocal.OFICINA),
    (CategoriaLocal.FAZENDA, TipoLocal.CAMPO),
    (CategoriaLocal.QUARTEL, TipoLocal.DEFESA),
]


def _construir_locais(n_locais: int, n_cidades: int) -> list:
    """~90% residência (mesma proporção medida no banco real, Seção 1.5 do plano),
    distribuídos uniformemente pelas `n_cidades` — cada NPC precisa achar casa e
    comércio na PRÓPRIA cidade (P04)."""
    locais = []
    for i in range(n_locais):
        cidade_id = 1 + (i % n_cidades)
        if i % 10 == 0:
            categoria, tipo = _CATEGORIAS_NAO_RESIDENCIAIS[i % len(_CATEGORIAS_NAO_RESIDENCIAIS)]
            locais.append(casa(
                local_id=f"local_{cidade_id:02d}_{i:05d}", nome=f"Estabelecimento {i}",
                tipo=tipo.value, categoria=categoria.value, cidade_id=cidade_id, capacidade=20,
            ))
        else:
            locais.append(casa(local_id=f"local_{cidade_id:02d}_{i:05d}",
                               cidade_id=cidade_id, capacidade=4))
    return locais


def _construir_npcs(n_npcs: int, locais: list, n_cidades: int) -> list:
    casas_por_cidade = {}
    for local in locais:
        if local.categoria == CategoriaLocal.RESIDENCIA.value:
            casas_por_cidade.setdefault(local.cidade_id, []).append(local.id)

    npcs = []
    rng = random.Random(42)
    for i in range(n_npcs):
        cidade_id = 1 + (i % n_cidades)
        casas = casas_por_cidade.get(cidade_id) or [locais[0].id]
        casa_id = rng.choice(casas)
        npcs.append(adulto(
            npc_id=f"npc_{cidade_id:02d}_{i:05d}", nome=f"NPC {i}",
            cidade_id=cidade_id, casa_id=casa_id, localizacao_atual_id=casa_id,
            genero=("masculino" if i % 2 == 0 else "feminino"),
            estagio_vida=EstagioVida.ADULTO.value,
        ))
    return npcs


def montar_mundo_sintetico(n_npcs: int, n_locais: int, n_cidades: int) -> EstadoDoMundo:
    locais = _construir_locais(n_locais, n_cidades)
    npcs = _construir_npcs(n_npcs, locais, n_cidades)
    return EstadoDoMundo(
        npcs=npcs, locais={l.id: l for l in locais}, cidades={},
        data_simulada=datetime(2026, 9, 12, 8, 0), db=BancoFalso(), tick_count=0,
    )


def medir_ms_por_tick(mundo: EstadoDoMundo, config: dict, n_ticks: int) -> float:
    loop = GameLoop(mundo, config)
    inicio = time.perf_counter()
    for _ in range(n_ticks):
        loop.executar_tick()
    total = time.perf_counter() - inicio
    return 1000.0 * total / n_ticks


def montar_mundo_com_banco_real(n_npcs: int, n_locais: int, n_cidades: int, db_path: str) -> EstadoDoMundo:
    """W02 (docs/13_PLANO_POPULACAO_E_ESCALA.md, armadilha 9): mesmo mundo sintético de
    `montar_mundo_sintetico`, mas com um `DatabaseManager` de VERDADE (SQLite num
    arquivo `tempfile`, WAL + `synchronous=NORMAL` — o `DatabaseManager` real já
    configura isso sozinho, não precisa repetir aqui) em vez de `BancoFalso`.

    Os NPCs/locais são gravados ANTES de medir (`salvar_completo`/`salvar_em_lote`) —
    sem isto, o `UPDATE ... WHERE id = ?` de `salvar_muitos` (N02) não bateria em
    nenhuma linha, e o benchmark mediria o custo de um `UPDATE` que não acha nada, não
    o de gravar de verdade (`BancoFalso` não tem essa distinção, por isso não mede
    disco: é exatamente o problema que esta tarefa existe pra corrigir)."""
    locais = _construir_locais(n_locais, n_cidades)
    npcs = _construir_npcs(n_npcs, locais, n_cidades)
    db = DatabaseManager(db_path)
    db.locais.salvar_em_lote(locais)
    db.npcs.salvar_completo(npcs)
    return EstadoDoMundo(
        npcs=npcs, locais={l.id: l for l in locais}, cidades={},
        data_simulada=datetime(2026, 9, 12, 8, 0), db=db, tick_count=0,
    )


def _veredito(ms_por_tick: float) -> str:
    if ms_por_tick <= 0:
        return "OK"
    folga = ORCAMENTO_MS / ms_por_tick
    return f"OK ({folga:.1f}x de folga)" if ms_por_tick <= ORCAMENTO_MS else f"ESTOURA ({folga:.2f}x)"


def rodar_matriz_sintetica(n_ticks: int):
    config = get_config()
    matriz = [
        (20, 1000, 1),
        (20, 24000, 1),
        (200, 24000, 1),
        (500, 24000, 1),
        (750, 10000, 15),
        (1500, 10000, 15),
        (1500, 15000, 15),
        (3000, 15000, 15),
        # N05 (docs/13_PLANO_POPULACAO_E_ESCALA.md): cenários de escala grande, rumo ao
        # alvo de 25.000 NPCs (D7) — os menores acima já cabiam de sobra antes do
        # Bloco N; estes são os que de fato testam o teto.
        (6000, 30000, 15),
        (12000, 40000, 15),
        (25000, 60000, 15),
        (25000, 60000, 40),
    ]
    print(f"ORÇAMENTO: {ORCAMENTO_MS:.0f} ms/tick (velocidade 60x, D4 do docs/12_PLANO_CIDADE_VIVA.md)")
    print(f"{'npcs':>6}  {'locais':>6}  {'cidades':>7}   {'ms/tick':>8}   veredito")
    for n_npcs, n_locais, n_cidades in matriz:
        mundo = montar_mundo_sintetico(n_npcs, n_locais, n_cidades)
        ms = medir_ms_por_tick(mundo, config, n_ticks)
        print(f"{n_npcs:>6}  {n_locais:>6}  {n_cidades:>7}   {ms:>8.1f}   {_veredito(ms)}")


def rodar_comparacao_cpu_vs_disco(n_ticks: int):
    """W02 (docs/13_PLANO_POPULACAO_E_ESCALA.md, armadilha 9): `rodar_matriz_sintetica`
    mede zero de custo de disco (`BancoFalso` não escreve nada) — e a persistência é
    o maior item do orçamento com 25.000 NPCs (944 ms antes de N02). Roda o MESMO
    cenário duas vezes, uma com `BancoFalso` (CPU) e outra com SQLite de verdade num
    `tempfile` (CPU+disco) — a diferença entre as duas colunas é o número que N02
    existia pra derrubar."""
    config = get_config()
    matriz = [
        (750, 10000, 15),
        (3000, 15000, 15),
        (25000, 60000, 40),
    ]
    print(f"ORÇAMENTO: {ORCAMENTO_MS:.0f} ms/tick (velocidade 60x, D4 do docs/12_PLANO_CIDADE_VIVA.md)")
    print(f"{'npcs':>6}  {'locais':>6}  {'cidades':>7}   {'cpu (ms)':>9}   {'cpu+disco (ms)':>15}   {'delta':>8}")
    for n_npcs, n_locais, n_cidades in matriz:
        mundo_falso = montar_mundo_sintetico(n_npcs, n_locais, n_cidades)
        ms_cpu = medir_ms_por_tick(mundo_falso, config, n_ticks)

        tmp_dir = tempfile.mkdtemp(prefix="openworld_bench_")
        try:
            db_path = os.path.join(tmp_dir, "bench.db")
            mundo_real = montar_mundo_com_banco_real(n_npcs, n_locais, n_cidades, db_path)
            ms_disco = medir_ms_por_tick(mundo_real, config, n_ticks)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        print(f"{n_npcs:>6}  {n_locais:>6}  {n_cidades:>7}   {ms_cpu:>9.1f}   {ms_disco:>15.1f}   "
              f"{ms_disco - ms_cpu:>+8.1f}")


def rodar_contra_banco_real(n_ticks: int):
    from engine.core import SimulationEngine
    engine = SimulationEngine()
    n_npcs, n_locais = len(engine.mundo.npcs), len(engine.mundo.locais)
    n_cidades = len({n.cidade_id for n in engine.mundo.npcs}) or 1
    print(f"ORÇAMENTO: {ORCAMENTO_MS:.0f} ms/tick (velocidade 60x, D4 do docs/12_PLANO_CIDADE_VIVA.md)")
    print(f"Banco real: {n_npcs} NPCs, {n_locais} locais, {n_cidades} cidade(s) com NPC")
    loop = GameLoop(engine.mundo, engine.config)
    inicio = time.perf_counter()
    for _ in range(n_ticks):
        loop.executar_tick()
    total = time.perf_counter() - inicio
    ms = 1000.0 * total / n_ticks
    print(f"{n_npcs:>6}  {n_locais:>6}  {n_cidades:>7}   {ms:>8.1f}   {_veredito(ms)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true", help="roda contra database/openworld.db em vez do sintético")
    parser.add_argument("--com-banco", action="store_true",
                        help="W02: compara CPU (BancoFalso) contra CPU+disco (SQLite real em tempfile), mesmo cenário")
    parser.add_argument("--ticks", type=int, default=3, help="ticks por cenário (padrão: 3)")
    args = parser.parse_args()

    if args.real:
        rodar_contra_banco_real(args.ticks)
    elif args.com_banco:
        rodar_comparacao_cpu_vs_disco(args.ticks)
    else:
        rodar_matriz_sintetica(args.ticks)


if __name__ == "__main__":
    main()
