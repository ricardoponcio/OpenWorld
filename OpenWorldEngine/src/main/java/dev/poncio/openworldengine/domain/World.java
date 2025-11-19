package dev.poncio.openworldengine.domain;

import java.util.ArrayList;
import java.util.List;

public class World {

    // Lista que armazena todos os NPCs na simulação
    private final List<Npc> npcs;

    public World() {
        this.npcs = new ArrayList<>();
    }

    /**
     * Adiciona um novo NPC ao mundo.
     * @param npc O objeto Npc a ser adicionado.
     */
    public void addNpc(Npc npc) {
        this.npcs.add(npc);
    }

    /**
     * Retorna o número atual de NPCs no mundo.
     * @return O número de NPCs.
     */
    public int getNpcCount() {
        return this.npcs.size();
    }

    /**
     * Retorna a lista de todos os NPCs do mundo.
     * @return Uma lista não modificável de Npc.
     */
    public List<Npc> getNpcs() {
        return new ArrayList<>(this.npcs);
    }
}