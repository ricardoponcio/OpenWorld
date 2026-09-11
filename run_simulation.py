import time
from engine.core import SimulationEngine
from engine.mechanics import JobMarket, InfrastructureManager
from engine.models import MetaChave

def processar_gatilhos_periodicos(engine, market):
    """Gatilhos baseados no relógio do jogo (não em contagem de ticks — ver Frente 4)."""
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

def start_simulation():
    engine = SimulationEngine()
    market = JobMarket(engine.db, engine.config)
    market.bootstrap_market()

    print(f"🌍 Mundo carregado com {len(engine.npcs)} habitantes e {len(engine.locais)} locais.")
    print("Simulação em tempo real 1:1 (1 min de jogo = 1 min real na velocidade 1x).")

    try:
        while True:
            status_pausa = engine.db.carregar_meta(MetaChave.SIMULACAO_PAUSADA)
            v_str = engine.db.carregar_meta(MetaChave.VELOCIDADE)
            velocidade = float(v_str) if v_str else 1.0
            # 60s reais = 1 min de jogo na velocidade 1x (tempo real de verdade) — Frente 4.
            espera = max(0.005, 60.0 / velocidade)

            if status_pausa == "1":
                # Modo Mestre de IA (Frente 5): mesmo pausado, o jogador pode pedir pra
                # avançar N minutos controlados. run_simulation.py continua sendo o único
                # processo dono da SimulationEngine — o dashboard só sinaliza via
                # mundo_meta, nunca instancia uma segunda engine.
                restante_str = engine.db.carregar_meta(MetaChave.AVANCAR_MINUTOS)
                restante = int(restante_str) if restante_str else 0

                if restante > 0:
                    engine.tick()
                    processar_gatilhos_periodicos(engine, market)
                    engine.db.salvar_meta(MetaChave.AVANCAR_MINUTOS, str(restante - 1))
                    continue  # roda o mais rápido possível, sem o sleep de ritmo normal

                time.sleep(1.0)
                continue

            engine.tick()
            processar_gatilhos_periodicos(engine, market)

            if velocidade > 1.0:
                print(f"⏩ Velocidade: {velocidade}x")
            time.sleep(espera)

    except KeyboardInterrupt:
        print("\nSimulação pausada. Até logo, Mestre!")

if __name__ == "__main__":
    start_simulation()
