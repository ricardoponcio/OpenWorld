import time
from engine.core import SimulationEngine
from engine.mechanics import JobMarket, InfrastructureManager

def start_simulation():
    engine = SimulationEngine()
    market = JobMarket()
    market.bootstrap_market()

    print(f"🌍 Mundo carregado com {len(engine.npcs)} habitantes e {len(engine.locais)} locais.")
    print("Simulação em tempo real 1:1 (1 min de jogo = 1 min real na velocidade 1x).")

    try:
        while True:
            status_pausa = engine.db.carregar_meta("simulacao_pausada")
            v_str = engine.db.carregar_meta("velocidade_simulacao")
            velocidade = float(v_str) if v_str else 1.0
            # 60s reais = 1 min de jogo na velocidade 1x (tempo real de verdade) — Frente 4.
            espera = max(0.005, 60.0 / velocidade)

            if status_pausa == "1":
                time.sleep(1.0)
                continue

            engine.tick()

            # Gatilhos periódicos baseados no relógio do jogo (não em contagem de ticks —
            # ticks agora são de 1 minuto; contar "a cada N ticks" dependeria do tamanho do
            # tick e voltaria a quebrar se ele mudasse de novo. Ver docs/ROADMAP.md, Frente 4.
            hora = engine.data_simulada.hour
            minuto = engine.data_simulada.minute
            if minuto == 0:
                if hora % 5 == 0:
                    # A cada 5h de jogo: mercado de trabalho e recarga de habitantes
                    market.processar_contratacoes()
                    engine.recarregar_habitantes()
                if hora == 2:
                    # 1x por dia de jogo: decadência e reparos de infraestrutura
                    InfrastructureManager.processar_desgaste(engine)
                    InfrastructureManager.processar_reparos_espontaneos(engine)

            if velocidade > 1.0:
                print(f"⏩ Velocidade: {velocidade}x")
            time.sleep(espera)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
