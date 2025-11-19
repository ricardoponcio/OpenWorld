package dev.poncio.openworldengine.domain;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class Npc {

    private String id; // ID único para o NPC (usar UUID.randomUUID().toString())
    private String nome;
    private int idade;
    private String trabalho;
    private String habitacao;
    private String personalidade; // Dados dinâmicos/não relacionais, idealmente em formato JSON ou String
    private String idMae;
    private String idPai;

}