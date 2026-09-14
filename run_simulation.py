import collections
import json
import time
from engine.config_loader import cfg_get
from engine.core import SimulationEngine
from engine.logger import WorldLogger
from engine.mechanics import JobMarket
from engine.mechanics.estatisticas import ColetorDeEstatisticas, formatar_resumo_console
from engine.mechanics.mestre import MestreManager
from engine.models import MetaChave


class RitmoDoLaco:
    """D03 (docs/16_PLANO_PAINEL_E_IA.md): mede a duração REAL de cada ciclo do
    laço (tick + espera) numa janela deslizante — sem isto, o laço dormia
    `max(0.005, 60/velocidade)` DEPOIS do tick sem descontar quanto ele já tinha
    levado (5 ms inúteis por tick em velocidade alta), e ninguém media a
    velocidade de fato entregue (Armadilha 22: pedida != efetiva).

    Vive aqui, não em `engine/` — é função de TEMPO REAL do processo (perf_counter,
    sleep), não de domínio da simulação."""

    def __init__(self, janela_ticks: int):
        self._duracoes_s = collections.deque(maxlen=janela_ticks)

    def registrar_tick(self, duracao_s: float) -> None:
        self._duracoes_s.append(duracao_s)

    @staticmethod
    def espera_s(velocidade_pedida: float, duracao_ultimo_tick_s: float) -> float:
        """Quanto dormir pra que este ciclo, no total, dure `60/velocidade_pedida`
        segundos reais — descontando o que o tick JÁ levou. Nunca negativo: em
        velocidade alta o tick sozinho já estoura o orçamento, e não dá pra
        "dormir menos que zero" pra compensar."""
        return max(0.0, 60.0 / velocidade_pedida - duracao_ultimo_tick_s)

    def velocidade_efetiva(self) -> float:
        """Minutos simulados por segundo real × 60 — a partir da duração REAL de
        cada ciclo (tick + espera), não da velocidade pedida (Armadilha 22)."""
        media_s = self._media_s()
        return 60.0 / media_s if media_s > 0 else 0.0

    def ms_por_tick_medio(self) -> float:
        return self._media_s() * 1000.0

    def ms_por_tick_p95(self) -> float:
        if not self._duracoes_s:
            return 0.0
        ordenado = sorted(self._duracoes_s)
        indice = min(len(ordenado) - 1, int(len(ordenado) * 0.95))
        return ordenado[indice] * 1000.0

    def _media_s(self) -> float:
        if not self._duracoes_s:
            return 0.0
        return sum(self._duracoes_s) / len(self._duracoes_s)


def sincronizar_locais_se_mudou(engine, ultima_versao_vista: str) -> str:
    """M01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): resolve o caminho "alguém escreveu
    Local direto no banco, fora deste processo" — hoje isso não acontece mais pelo
    Modo Mestre (F01, docs/14_PLANO_AVANCO_E_CALIBRAGEM.md: as ações dele aplicam
    DENTRO deste processo, via `drenar_acoes_do_mestre`, com o mundo já atualizado
    na hora), mas o mecanismo continua existindo — é o que o dashboard usaria se um
    dia escrever Local por fora também. Um `SELECT` de uma linha por tick é ruído (o
    mesmo caminho já lê SIMULACAO_PAUSADA/VELOCIDADE todo tick); recarregar 24 mil
    locais por tick não seria. Só recarrega quando o contador de fato mudou desde a
    última checagem."""
    versao_atual = engine.mundo.db.meta.carregar(MetaChave.LOCAIS_VERSAO)
    if versao_atual != ultima_versao_vista:
        engine.recarregar_locais()
        return versao_atual
    return ultima_versao_vista


def drenar_acoes_do_mestre(engine, mestre: MestreManager) -> None:
    """F01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): drena a fila de ações de mundo do
    Modo Mestre a cada volta do laço — INCLUSIVE pausado (mesmo padrão de
    `sincronizar_locais_se_mudou`/`AVANCAR_MINUTOS`: o Mestre prepara cena com a
    simulação parada). Aplica com o `EstadoDoMundo` vivo deste processo — nunca por
    fora dele, que é exatamente o que esta tarefa existe pra corrigir."""
    for resultado in mestre.drenar_e_aplicar(engine.mundo):
        WorldLogger.evento_mundo(f"🎭 [MESTRE] {resultado}")


def atualizar_estatisticas(engine, coletor: ColetorDeEstatisticas, config: dict,
                            velocidade: float, ritmo: "RitmoDoLaco", estado_console: dict) -> None:
    """O03/D03 (docs/16_PLANO_PAINEL_E_IA.md): monta o retrato do mundo a cada
    `estatisticas_a_cada_ticks` e grava em `MetaChave.ESTATISTICAS` — o painel só lê
    essa chave (Armadilha 24). O console imprime o último retrato a cada
    `console_resumo_a_cada_s_reais` REAIS, não simulados (senão em velocidade alta
    seria uma linha por tick de novo)."""
    cfg_obs = cfg_get(config, "observabilidade")
    if engine.mundo.tick_count % cfg_get(cfg_obs, "estatisticas_a_cada_ticks") == 0:
        stats = coletor.montar()
        stats["desempenho"] = {
            "velocidade_pedida": velocidade,
            "velocidade_efetiva": ritmo.velocidade_efetiva(),
            "ms_por_tick_medio": ritmo.ms_por_tick_medio(),
            "ms_por_tick_p95": ritmo.ms_por_tick_p95(),
        }
        estado_console["ultimas"] = stats
        engine.mundo.db.meta.salvar(MetaChave.ESTATISTICAS, json.dumps(stats, ensure_ascii=False))

    agora = time.time()
    intervalo = cfg_get(cfg_obs, "console_resumo_a_cada_s_reais")
    if estado_console["ultimas"] is not None and agora - estado_console["ultimo_console_s"] >= intervalo:
        print(formatar_resumo_console(estado_console["ultimas"]))
        estado_console["ultimo_console_s"] = agora


def checkpoint_wal_se_devido(engine, config: dict, estado_wal: dict) -> None:
    """O04 (docs/16_PLANO_PAINEL_E_IA.md): força o checkpoint do WAL a cada
    `wal_checkpoint_a_cada_ticks` — sem isto o arquivo só cresce enquanto o painel
    segura leitores (checkpoint starvation, medido 1,19 GB). Três `ocupado`
    seguidos vira um único warning (não um por tentativa)."""
    cadencia = cfg_get(cfg_get(config, "simulacao"), "wal_checkpoint_a_cada_ticks")
    if engine.mundo.tick_count % cadencia != 0:
        return
    ocupado, _, _ = engine.mundo.db.checkpoint_wal()
    if ocupado:
        estado_wal["ocupado_seguidas"] += 1
        if estado_wal["ocupado_seguidas"] == 3:
            WorldLogger.warning(
                "[WAL] checkpoint não completou 3 vezes seguidas — algum leitor está "
                "segurando um snapshot antigo (o painel lendo o banco inteiro?).")
    else:
        estado_wal["ocupado_seguidas"] = 0


def start_simulation():
    # Este é o ponto de entrada: é aqui que as dependências são construídas, uma vez
    # por processo (11_ARQUITETURA.md Seção 7). Os gerenciadores recebem o `EstadoDoMundo`
    # e a config, nunca a engine inteira (R-F01).
    #
    # X03 (docs/15_PLANO_MUNDO_CRIVEL.md, decisão ❽): `JobMarket.processar_contratacoes`
    # e `InfrastructureManager.processar_desgaste`/`processar_reparos_espontaneos`
    # SAÍRAM daqui — moravam num `processar_gatilhos_periodicos` próprio, fora de
    # qualquer benchmark (armadilha 16: 21% do custo real por dia simulado nunca
    # tinha sido medido). Agora são rotinas de `GameLoop._rotinas_diarias`,
    # construídas e despachadas por `engine.tick()` sozinho. `bootstrap_market` é a
    # exceção — roda uma vez no boot, não por tick, então continua aqui, com um
    # `JobMarket` só pra isso (sem `mundo`: não aplica nada em memória).
    engine = SimulationEngine()
    JobMarket(engine.mundo.db, engine.config).bootstrap_market()
    mestre = MestreManager(engine.mundo.db, engine.config)
    coletor_estatisticas = ColetorDeEstatisticas(engine.mundo, engine.config)
    ritmo = RitmoDoLaco(cfg_get(cfg_get(engine.config, "simulacao"), "janela_medicao_ritmo_ticks"))
    estado_console = {"ultimas": None, "ultimo_console_s": time.time()}
    estado_wal = {"ocupado_seguidas": 0}

    print(f"🌍 Mundo carregado com {len(engine.mundo.npcs)} habitantes e {len(engine.mundo.locais)} locais.")
    print("Simulação em tempo real 1:1 (1 min de jogo = 1 min real na velocidade 1x).")

    # M01: começa com a versão já carregada no boot — não recarrega à toa no primeiro laço.
    ultima_versao_locais = engine.mundo.db.meta.carregar(MetaChave.LOCAIS_VERSAO)

    try:
        while True:
            # M01: checado a cada volta do laço (mesmo pausado).
            ultima_versao_locais = sincronizar_locais_se_mudou(engine, ultima_versao_locais)
            # F01: a fila do Mestre drena a cada volta do laço, mesmo pausado — é
            # exatamente quando o jogador prepara uma cena antes de avançar o tempo.
            drenar_acoes_do_mestre(engine, mestre)

            status_pausa = engine.mundo.db.meta.carregar(MetaChave.SIMULACAO_PAUSADA)
            v_str = engine.mundo.db.meta.carregar(MetaChave.VELOCIDADE)
            velocidade = float(v_str) if v_str else 1.0

            if status_pausa == "1":
                # Modo Mestre de IA (Frente 5): mesmo pausado, o jogador pode pedir pra
                # avançar N minutos controlados. run_simulation.py continua sendo o único
                # processo dono da SimulationEngine — o dashboard só sinaliza via
                # mundo_meta, nunca instancia uma segunda engine.
                restante_str = engine.mundo.db.meta.carregar(MetaChave.AVANCAR_MINUTOS)
                restante = int(restante_str) if restante_str else 0

                if restante > 0:
                    inicio = time.perf_counter()
                    engine.tick()
                    # D03: sem espera de ritmo aqui de propósito ("roda o mais rápido
                    # possível") — só registra o custo real do tick pras estatísticas.
                    ritmo.registrar_tick(time.perf_counter() - inicio)
                    engine.mundo.db.meta.salvar(MetaChave.AVANCAR_MINUTOS, str(restante - 1))
                    atualizar_estatisticas(engine, coletor_estatisticas, engine.config, velocidade, ritmo, estado_console)
                    checkpoint_wal_se_devido(engine, engine.config, estado_wal)
                    continue  # roda o mais rápido possível, sem o sleep de ritmo normal

                time.sleep(1.0)
                continue

            # D03 (docs/16_PLANO_PAINEL_E_IA.md): descontar quanto o tick já levou do
            # tempo de espera — o laço antigo dormia 60/velocidade cheio, sempre, mesmo
            # em velocidade alta onde isso é 5 ms desperdiçados por tick à toa.
            inicio_ciclo = time.perf_counter()
            engine.tick()
            duracao_tick = time.perf_counter() - inicio_ciclo
            espera = ritmo.espera_s(velocidade, duracao_tick)
            if espera > 0:
                time.sleep(espera)
            # Ciclo completo (tick + espera) — é isso que "velocidade efetiva" mede
            # (Armadilha 22: a pedida não é a entregue).
            ritmo.registrar_tick(time.perf_counter() - inicio_ciclo)

            # O01 (docs/16_PLANO_PAINEL_E_IA.md): o print por tick saiu — o resumo
            # periódico do coletor de estatísticas (O03) substitui isso.
            atualizar_estatisticas(engine, coletor_estatisticas, engine.config, velocidade, ritmo, estado_console)
            checkpoint_wal_se_devido(engine, engine.config, estado_wal)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
