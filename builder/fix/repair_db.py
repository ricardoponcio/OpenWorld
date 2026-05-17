"""
SCRIPT: repair_db.py
OBJETIVO: Saneamento e Reabilitação do Banco de Dados.
MOMENTO DE USO: Use este script quando notar NPCs travados na coordenada (0,0) ou quando o banco de dados 
                apresentar inconsistências após migrações de esquema (ex: strings de profissão em colunas de ID).
MOTIVAÇÃO: Criado após um evento crítico de 'Desvio de Colunas' onde IDs de casas foram sobrescritos por 
           nomes de profissões (como 'guarda' ou 'ocioso'), causando o isolamento dos NPCs no limbo do mapa.
"""
import sqlite3
import json

def repair():
    conn = sqlite3.connect('database/openworld.db')
    cursor = conn.cursor()

    print("🧹 Realizando faxina nas colunas de Localização e Trabalho...")
    
    # 1. Recuperação Habitacional
    cursor.execute("SELECT id FROM locais WHERE tipo = 'Casa' OR categoria = 'residencia'")
    casas_validas = [r[0] for r in cursor.fetchall()]
    
    if not casas_validas:
        print("⚠️ Nenhuma casa encontrada para realocação.")
        return

    cursor.execute("SELECT id FROM npcs")
    npcs_ids = [r[0] for r in cursor.fetchall()]
    
    for i, npc_id in enumerate(npcs_ids):
        nova_casa = casas_validas[i % len(casas_validas)]
        cursor.execute("UPDATE npcs SET casa_id = ? WHERE id = ? AND (casa_id NOT IN (SELECT id FROM locais) OR casa_id IN ('ocioso', 'guarda'))", (nova_casa, npc_id))

    # 2. Reset de Estado
    cursor.execute("UPDATE npcs SET localizacao_atual_id = casa_id, local_trabalho_id = NULL, acao_atual = 'Ocioso'")
    
    # 3. Limpeza de Profissões
    print("💼 Sanitizando IDs de profissão...")
    cursor.execute("UPDATE npcs SET profissao_id = 'ocioso' WHERE profissao_id NOT IN (SELECT id FROM profissoes)")

    conn.commit()
    conn.close()
    print("✅ Reparo concluído! NPCs foram enviados para casas válidas e estão prontos para o JobMarket.")

if __name__ == "__main__":
    repair()
