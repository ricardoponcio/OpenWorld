"""
SCRIPT: setup_jobs.py
FUNÇÃO: Arquiteto da Economia Urbana e Profissões.
DESCRIÇÃO: Define as profissões mestras e vincula cada uma a uma categoria técnica de local 
           (militar, agricultura, etc). Essencial para o JobMarket funcionar.
MOMENTO: Executar sempre após o manager.py para garantir que o mercado esteja populado.
"""
import sqlite3
import os
import sys

# Adiciona o diretório raiz ao path para importar o engine
sys.path.append(os.getcwd())
from engine.database import DatabaseManager

DB_PATH = "database/openworld.db"

def setup_jobs():
    # Garante que as tabelas existam (o __init__ já chama _init_db)
    db_mgr = DatabaseManager(DB_PATH)

    if not os.path.exists(DB_PATH):


        print("❌ Banco de dados não encontrado. Rode o manager.py primeiro.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Adicionar colunas novas caso não existam (Migração manual para SQLite)
    print("🔄 Verificando colunas novas...")
    try:
        cursor.execute("ALTER TABLE locais ADD COLUMN categoria TEXT DEFAULT 'generic'")
        cursor.execute("ALTER TABLE locais ADD COLUMN capacidade INTEGER DEFAULT 5")
        cursor.execute("ALTER TABLE locais ADD COLUMN salario_base INTEGER DEFAULT 100")
    except sqlite3.OperationalError:
        pass # Colunas já existem

    try:
        cursor.execute("ALTER TABLE npcs ADD COLUMN profissao_id TEXT")
    except sqlite3.OperationalError:
        pass # Coluna já existe

    # 2. Popular Profissões Mestres (Categorias Técnicas)
    profissoes = [
        ('fazendeiro', 'Fazendeiro', 'agricultura'),
        ('guarda', 'Guarda', 'militar'),
        ('taberneiro', 'Taberneiro', 'social'),
        ('professor', 'Professor', 'educacao'),
        ('medico', 'Médico', 'saude'),
        ('comerciante', 'Comerciante', 'comercio'),
        ('operário', 'Operário', 'industria'),
        ('ocioso', 'Desempregado', 'nenhum')
    ]


    print("📥 Populando tabela de profissões...")
    cursor.executemany("INSERT OR REPLACE INTO profissoes (id, nome, categoria_local_id) VALUES (?, ?, ?)", profissoes)

    # 3. Tentar mapear NPCs atuais
    print("🧠 Mapeando NPCs atuais para profissões mestres...")
    npcs = cursor.execute("SELECT id, profissao FROM npcs").fetchall()
    for npc_id, prof_nome in npcs:
        prof_nome_low = prof_nome.lower()
        
        # Mapeamento heurístico rico
        match_id = 'ocioso'
        
        # Regras de casamento heurístico para IA criativa
        if any(w in prof_nome_low for w in ['ferreiro', 'forja', 'metal', 'ferro', 'operário', 'artesão', 'alquimista', 'alquimia', 'aprendiz']):
            # Profissões industriais ou artesanais
            if any(w in prof_nome_low for w in ['alquimista', 'alquimia', 'médico', 'cura', 'hospital']):
                match_id = 'medico'
            else:
                match_id = 'operário'
        elif any(w in prof_nome_low for w in ['guarda', 'patrulha', 'defesa', 'militar', 'soldado', 'elite', 'marinho', 'capitão', 'navegante']):
            match_id = 'guarda'
        elif any(w in prof_nome_low for w in ['fazendeiro', 'fazenda', 'campo', 'agricultura', 'pomar', 'terra', 'cultivo', 'vegetal', 'arvoreira']):
            match_id = 'fazendeiro'
        elif any(w in prof_nome_low for w in ['taberneiro', 'taberna', 'taverna', 'cozinheiro', 'estalagem', 'social', 'servente']):
            match_id = 'taberneiro'
        elif any(w in prof_nome_low for w in ['professor', 'escola', 'bibliotecário', 'estudioso', 'escriba', 'sábio', 'vigário']):
            match_id = 'professor'
        elif any(w in prof_nome_low for w in ['comerciante', 'loja', 'mercado', 'vendedor', 'taberneiro', 'padeiro']):
            match_id = 'comerciante'
            
        # Se falhar, tenta casamento substring aproximado padrão
        if match_id == 'ocioso':
            for p_id, p_nome, cat in profissoes:
                if p_id in prof_nome_low or p_nome.lower() in prof_nome_low:
                    match_id = p_id
                    break
                    
        # Se ainda for ocioso, atribui uma profissão de combate ou trabalho padrão aleatória
        if match_id == 'ocioso':
            import random
            match_id = random.choice(['operário', 'fazendeiro', 'guarda', 'comerciante'])
        
        cursor.execute("UPDATE npcs SET profissao_id = ? WHERE id = ?", (match_id, npc_id))

    # 4. Tentar mapear Locais atuais
    print("🏠 Mapeando locais atuais para categorias...")
    locais = cursor.execute("SELECT id, nome, tipo FROM locais").fetchall()
    for loc_id, nome, tipo in locais:
        nome_low = nome.lower()
        tipo_low = tipo.lower()
        
        cat = 'generic'
        if 'fazenda' in nome_low or 'campo' in nome_low or 'agricultura' in nome_low:
            cat = 'fazenda'
        elif 'quartel' in nome_low or 'guarda' in nome_low or 'elite' in nome_low or 'defesa' in tipo_low:
            cat = 'quartel'
        elif 'taverna' in nome_low or 'bar' in nome_low or 'dragão' in nome_low or 'social' in tipo_low:
            cat = 'taverna'
        elif 'escola' in nome_low or 'laboratório' in nome_low or 'alquimia' in nome_low or 'magia' in tipo_low or 'arcano' in nome_low:
            cat = 'universidade'
        elif 'forja' in nome_low or 'oficina' in tipo_low or 'porto' in nome_low or 'doca' in nome_low or 'mar' in tipo_low or 'mina' in nome_low:
            cat = 'forja'
        elif 'comercio' in tipo_low or 'loja' in tipo_low or 'mercado' in nome_low:
            cat = 'mercado'
            
        cursor.execute("UPDATE locais SET categoria = ?, capacidade = 5, salario_base = 100 WHERE id = ?", (cat, loc_id))

    conn.commit()
    conn.close()
    print("✅ Mercado de Trabalho configurado com sucesso!")

if __name__ == "__main__":
    setup_jobs()
