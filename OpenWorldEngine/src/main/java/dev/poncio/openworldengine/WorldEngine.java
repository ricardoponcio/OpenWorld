package dev.poncio.openworldengine;

import dev.poncio.openworldengine.domain.Npc;
import dev.poncio.openworldengine.domain.World;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class WorldEngine {

    // Define o passo de tempo fixo para a simulação
    private static final int SIMULATION_TICK_RATE_MS = 1000; // 1 segundo por tick
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
    private final AtomicBoolean isRunning = new AtomicBoolean(false);

    // O objeto que gerencia o estado do nosso mundo
    private final World world = new World();

    // Serviço para gerar NPCs usando a camada Python
    private final NpcGeneratorService npcGeneratorService = new NpcGeneratorService();

    public void start() {
        if (isRunning.compareAndSet(false, true)) {
            System.out.println("Motor do mundo iniciado.");
            scheduler.scheduleAtFixedRate(this::update, 0, SIMULATION_TICK_RATE_MS, TimeUnit.MILLISECONDS);
        }
    }

    public void stop() {
        if (isRunning.compareAndSet(true, false)) {
            System.out.println("Motor do mundo parado.");
            scheduler.shutdown();
        }
    }

    // O coração da simulação
    private void update() {
        // Passo 1: Lógica do jogo (simulação)
        System.out.println("--- Tick de simulação ---");

        // Exemplo: Gerar 5 NPCs se ainda não existirem
        if (world.getNpcCount() < 5) {
            System.out.println("Criando novos NPCs...");
            // Lógica para chamar o serviço de criação de NPC
            createNPCs(5 - world.getNpcCount());
        }

        // Passo 2: Lógica de eventos/interações
        // Exemplo: Simular interações entre os NPCs existentes
        simulateInteractions();

        // Passo 3: Persistir o estado do mundo
        persistWorldState();
    }

    // Ações base do game loop (para serem implementadas)
    private void createNPCs(int count) {
        for (int i = 0; i < count; i++) {
            try {
                // Chama o serviço de geração e adiciona o NPC ao mundo
                Npc newNpc = npcGeneratorService.generateNpc("Gere um NPC para uma vila rural chamada 'Oakwood'.");
                world.addNpc(newNpc);
                System.out.println("NPC '" + newNpc.getNome() + "' criado e adicionado ao mundo.");
            } catch (Exception e) {
                System.err.println("Erro ao gerar NPC: " + e.getMessage());
                // Em um sistema real, você teria um tratamento de erro mais robusto.
            }
        }
    }

    private void simulateInteractions() {
        // Lógica para NPCs interagirem (p.ex., criar relacionamentos)
    }

    private void persistWorldState() {
        // Lógica para salvar o estado dos NPCs no banco de dados
    }

    public static void main(String[] args) {
        WorldEngine engine = new WorldEngine();
        engine.start();

        // Para parar o motor após um tempo, por exemplo
        // try { Thread.sleep(30000); } catch (InterruptedException e) {}
        // engine.stop();
    }
}