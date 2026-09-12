import time
from engine.core import SimulationEngine
from engine.mechanics import JobMarket, InfrastructureManager
from engine.models import MetaChave


def sincronizar_locais_se_mudou(engine, ultima_versao_vista: str) -> str:
    """M01 (docs/PLANO_POPULACAO_E_ESCALA.md): o Modo Mestre roda no processo do
    Flask e escreve locais direto no SQLite — o processo da simulação só percebe se
    alguém checar. Um `SELECT` de uma linha por tick é ruído (o mesmo caminho já lê
    SIMULACAO_PAUSADA/VELOCIDADE todo tick); recarregar 24 mil locais por tick não
    seria. Só recarrega quando o contador de fato mudou desde a última checagem."""
    versao_atual = engine.mundo.db.meta.carregar(MetaChave.LOCAIS_VERSAO)
    if versao_atual != ultima_versao_vista:
        engine.recarregar_locais()
        return versao_atual
    return ultima_versao_vista

def processar_gatilhos_periodicos(engine, market, infra):
    """Gatilhos baseados no relógio do jogo (não em contagem de ticks — ver Frente 4)."""
    hora = engine.mundo.data_simulada.hour
    minuto = engine.mundo.data_simulada.minute
    if minuto == 0:
        if hora % 5 == 0:
            # A cada 5h de jogo: mercado de trabalho e recarga de habitantes
            market.processar_contratacoes()
            engine.recarregar_habitantes()
        if hora == 2:
            # 1x por dia de jogo: decadência e reparos de infraestrutura
            infra.processar_desgaste()
            infra.processar_reparos_espontaneos()

def start_simulation():
    # Este é o ponto de entrada: é aqui que as dependências são construídas, uma vez
    # por processo (ARQUITETURA.md Seção 7). Os gerenciadores recebem o `EstadoDoMundo`
    # e a config, nunca a engine inteira (R-F01).
    engine = SimulationEngine()
    market = JobMarket(engine.mundo.db, engine.config)
    infra = InfrastructureManager(engine.mundo, engine.config)
    market.bootstrap_market()

    print(f"🌍 Mundo carregado com {len(engine.mundo.npcs)} habitantes e {len(engine.mundo.locais)} locais.")
    print("Simulação em tempo real 1:1 (1 min de jogo = 1 min real na velocidade 1x).")

    # M01: começa com a versão já carregada no boot — não recarrega à toa no primeiro laço.
    ultima_versao_locais = engine.mundo.db.meta.carregar(MetaChave.LOCAIS_VERSAO)

    try:
        while True:
            # M01: checado a cada volta do laço (mesmo pausado — o Modo Mestre cria/
            # destrói local com a simulação parada, pra preparar uma cena antes de
            # avançar).
            ultima_versao_locais = sincronizar_locais_se_mudou(engine, ultima_versao_locais)

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
                    processar_gatilhos_periodicos(engine, market, infra)
                    engine.mundo.db.meta.salvar(MetaChave.AVANCAR_MINUTOS, str(restante - 1))
                    continue  # roda o mais rápido possível, sem o sleep de ritmo normal

                time.sleep(1.0)
                continue

            engine.tick()
            processar_gatilhos_periodicos(engine, market, infra)

            if velocidade > 1.0:
                print(f"⏩ Velocidade: {velocidade}x")
            time.sleep(espera)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
