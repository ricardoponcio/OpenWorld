import time
from engine.core import SimulationEngine
from engine.mechanics import JobMarket, InfrastructureManager

def start_simulation():
    engine = SimulationEngine()
    market = JobMarket()
    
    if not engine.npcs:
        print("❌ Nenhum habitante encontrado no banco de dados!")
        print("💡 Execute primeiro: python3 world_builder.py --npcs 10")
        return

    print(f"🌍 Mundo carregado com {len(engine.npcs)} habitantes e {len(engine.locais)} locais.")
    print("Simulação em tempo real (2s real = 15min jogo).")
    
    ticks = 0
    try:
        while True:
            status_pausa = engine.db.carregar_meta("simulacao_pausada")
            v_str = engine.db.carregar_meta("velocidade_simulacao")
            velocidade = float(v_str) if v_str else 1.0
            espera = max(0.1, 2.0 / velocidade)

            if status_pausa == "1":
                time.sleep(1.0)
                continue

            engine.tick()
            ticks += 1

            # A cada 20 ticks (~5h jogo): mercado de trabalho e recarga de habitantes
            if ticks % 20 == 0:
                market.processar_contratacoes()
                engine.recarregar_habitantes()

            # A cada 96 ticks (1 dia jogo = 96 × 15min): decadência e reparos de infraestrutura
            if ticks % 96 == 0:
                InfrastructureManager.processar_desgaste(engine)
                InfrastructureManager.processar_reparos_espontaneos(engine)

            if velocidade > 1.0:
                print(f"⏩ Velocidade: {velocidade}x")
            time.sleep(espera)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
