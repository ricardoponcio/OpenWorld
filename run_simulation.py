import time
from engine.core import SimulationEngine
from engine.logger import WorldLogger
from engine.mechanics import JobMarket
from engine.mechanics.mestre import MestreManager
from engine.models import MetaChave


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
            # 60s reais = 1 min de jogo na velocidade 1x (tempo real de verdade) — Frente 4.
            espera = max(0.005, 60.0 / velocidade)

            if status_pausa == "1":
                # Modo Mestre de IA (Frente 5): mesmo pausado, o jogador pode pedir pra
                # avançar N minutos controlados. run_simulation.py continua sendo o único
                # processo dono da SimulationEngine — o dashboard só sinaliza via
                # mundo_meta, nunca instancia uma segunda engine.
                restante_str = engine.mundo.db.meta.carregar(MetaChave.AVANCAR_MINUTOS)
                restante = int(restante_str) if restante_str else 0

                if restante > 0:
                    engine.tick()
                    engine.mundo.db.meta.salvar(MetaChave.AVANCAR_MINUTOS, str(restante - 1))
                    continue  # roda o mais rápido possível, sem o sleep de ritmo normal

                time.sleep(1.0)
                continue

            engine.tick()

            # O01 (docs/16_PLANO_PAINEL_E_IA.md): o print por tick saiu — o resumo
            # periódico do coletor de estatísticas (O03) substitui isso.
            time.sleep(espera)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
