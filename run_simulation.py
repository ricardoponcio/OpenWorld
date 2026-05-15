import time
from engine.core import SimulationEngine

def start_simulation():
    engine = SimulationEngine()
    
    if not engine.npcs:
        print("❌ Nenhum habitante encontrado no banco de dados!")
        print("💡 Execute primeiro: python3 world_builder.py --npcs 10")
        return

    print(f"🌍 Mundo carregado com {len(engine.npcs)} habitantes e {len(engine.locais)} locais.")
    print("Simulação em tempo real (2s real = 15min jogo).")
    
    try:
        while True:
            # Verificar se a simulação está pausada
            status_pausa = engine.db.carregar_meta("simulacao_pausada")

            if status_pausa == "1":
                # print("⏸️ Simulação Pausada...")
                time.sleep(1.0)
                continue

            engine.tick()
            time.sleep(2.0)
    except KeyboardInterrupt:

        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
