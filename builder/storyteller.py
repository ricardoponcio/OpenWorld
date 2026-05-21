import sqlite3
"""
SCRIPT: storyteller.py
FUNÇÃO: Arquiteto Narrativo e de Construção.
DESCRIÇÃO: Utiliza IA para descrever e criar novos prédios ou eventos mundiais, 
           enriquecendo o lore enquanto mantém a coerência com as categorias técnicas.
"""
import json
import os
import sys
import random
from datetime import datetime

# Adicionar o diretório raiz ao path para importar a engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine.ai import AIStorytellerClient

DB_PATH = "database/openworld.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_storyteller(tema="Cyberpunk"):
    print(f"🎬 Storyteller: Analisando o estado de {tema}...")
    
    conn = get_db_connection()
    # 1. Coletar Contexto
    npcs = conn.execute("SELECT id, nome, profissao, local_trabalho_id, casa_id FROM npcs").fetchall()
    locais = conn.execute("SELECT id, nome, tipo FROM locais WHERE status = 1").fetchall()
    rels = conn.execute("SELECT npc_a_id, npc_b_id, afinidade, vinculo FROM relacionamentos WHERE afinidade != 0 LIMIT 10").fetchall()
    evs = conn.execute("SELECT resumo_estruturado FROM eventos ORDER BY timestamp DESC LIMIT 10").fetchall()
    ativos = conn.execute("SELECT titulo FROM eventos_globais WHERE ticks_restantes > 0").fetchall()
    
    contexto = {
        "npcs": [f"{n['id']}: {n['nome']} ({n['profissao']}) | Trab: {n['local_trabalho_id']} | Casa: {n['casa_id']}" for n in npcs],
        "locais": [f"{l['id']}: {l['nome']} ({l['tipo']})" for l in locais],

        "relacionamentos": [f"{r['npc_a_id']} e {r['npc_b_id']} são {r['vinculo']} (Af:{r['afinidade']})" for r in rels],
        "ultimos_fatos": [e['resumo_estruturado'] for e in evs],
        "eventos_ativos": [a['titulo'] for a in ativos]
    }
    
    prompt = f"""
    Você é o Storyteller e Arquiteto do OpenWorld. O tema é {tema}.
    Baseado no estado atual, gere UM evento global e, se necessário, ALTERAÇÕES FÍSICAS no mundo.
    
    ESTADO ATUAL:
    {json.dumps(contexto, indent=2)}
    
    IMPORTANTE: Ao usar comandos como 'DESTRUIR_LOCAL' ou 'AFETAR_NPC', use APENAS os IDs listados acima (ex: loc_01, npc_001).
    
    REGRAS DE AÇÕES DE MUNDO:
    - 'CRIAR_LOCAL': {{ "nome": "...", "tipo": "Trabalho | Social | Casa", "categoria": "fazenda|quartel|taverna|escola|hospital|loja|fabrica", "descricao": "..." }}
    - 'CRIAR_NPC': {{ "nome": "...", "profissao": "...", "profissao_id": "fazendeiro|guarda|taberneiro|professor|medico|comerciante|operário" }}
    - 'DESTRUIR_LOCAL': {{ "id": "..." }}
    - 'AFETAR_NPC': {{ "id": "...", "dados": {{ "saude": -10, "humor": "..." }} }}
    - 'REATRIBUIR_NPC': {{ "id": "...", "dados": {{ "local_trabalho_id": "ID_OU_NOVO_LOCAL", "casa_id": "ID_OU_NOVO_LOCAL" }} }}
    
    DIRETRIZES DE COMPORTAMENTO:
    1. OBEDEÇA AO COMANDO: Se o usuário pedir para construir, FOQUE na construção. Não gere desastres aleatórios que destruam o progresso sem uma justificativa narrativa épica.
    2. USE CATEGORIAS REAIS: Para 'CRIAR_LOCAL', use uma das categorias listadas acima para que o mercado de trabalho funcione.
    3. NÃO HALLUCINE IDs: Use apenas os IDs fornecidos no contexto.
    
    MODIFICADORES VÁLIDOS:
    - TRABALHAR, DORMIR, SOCIALIZAR, COMER, OCIOSO


    
    DICA: Para 'REATRIBUIR_NPC', se quiser usar o local que você acabou de criar no mesmo JSON, use o ID "NOVO_LOCAL".

    RETORNE APENAS UM JSON PURO. NÃO ADICIONE NENHUM TEXTO ANTES OU DEPOIS.
    NÃO USE MARKDOWN (```json).
    
    EXEMPLO DE RESPOSTA PERFEITA:
    {{
        "titulo": "Explosão na Padaria",
        "descricao": "Um botijão de gás explodiu.",
        "tipo": "CATASTROFE",
        "modificadores": {{ "COMER": -10 }},
        "duracao_ticks": 5,
        "acoes_mundo": [
            {{ "comando": "DESTRUIR_LOCAL", "id": "loc_01" }},
            {{ "comando": "REATRIBUIR_NPC", "id": "npc_01", "dados": {{ "local_trabalho_id": "loc_02" }} }}
        ]
    }}
    """
    
    print("🧠 Consultando a Mente do Mundo...")
    try:
        evento = AIStorytellerClient.gerar_evento_global(tema, contexto)


        
        # 1. Salvar Evento Global
        ev_id = f"glob_{int(datetime.now().timestamp())}"
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO eventos_globais 
                          VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                       (ev_id, evento['titulo'], evento['descricao'], evento['tipo'], 
                        evento.get('afeta_local_id'), json.dumps(evento['modificadores']), 
                        evento['duracao_ticks']))

        # 2. Processar Ações de Mundo
        for acao in evento.get('acoes_mundo', []):
            # Normalizar dados (suporta 'dados' ou campos no nível principal)
            d = acao.get('dados', acao)
            cmd = acao.get('comando')

            if cmd == 'CRIAR_LOCAL':
                # Encontrar coordenadas vazias
                existentes = [tuple(json.loads(r['coordenadas'])) for r in conn.execute("SELECT coordenadas FROM locais").fetchall()]
                cx, cy = random.randint(0, 19), random.randint(0, 19)
                while (cx, cy) in existentes:
                    cx, cy = random.randint(0, 19), random.randint(0, 19)
                
                new_id = f"loc_dyn_{int(datetime.now().timestamp())}_{random.randint(0,99)}"
                # Agora salvamos com as 10 colunas
                conn.execute("""
                    INSERT INTO locais (id, nome, tipo, categoria, descricao, coordenadas, status, integridade, capacidade, salario_base) 
                    VALUES (?, ?, ?, ?, ?, ?, 1, 100, 5, 100)
                """, (
                    new_id, 
                    d.get('nome', 'Local Indefinido'), 
                    d.get('tipo', 'Social'), 
                    d.get('categoria', 'generic'),
                    d.get('descricao', ''), 
                    json.dumps([cx, cy])
                ))
                print(f"🏗️  CONSTRUÇÃO: {d.get('nome')} [{d.get('categoria', 'generic')}] erguido em ({cx}, {cy})!")



            elif cmd == 'REATRIBUIR_NPC':
                target_npc = acao.get('id')
                
                trab_id = d.get('local_trabalho_id')
                if trab_id == "NOVO_LOCAL" and 'new_id' in locals():
                    trab_id = new_id
                
                casa_id = d.get('casa_id')
                if casa_id == "NOVO_LOCAL" and 'new_id' in locals():
                    casa_id = new_id
                
                if trab_id:
                    check = conn.execute("SELECT id FROM locais WHERE id = ?", (trab_id,)).fetchone()
                    if check:
                        conn.execute("UPDATE npcs SET local_trabalho_id = ? WHERE id = ?", (trab_id, target_npc))
                        print(f"💼 EMPREGO: {target_npc} agora trabalha em {trab_id}!")
                
                if casa_id:
                    check = conn.execute("SELECT id FROM locais WHERE id = ?", (casa_id,)).fetchone()
                    if check:
                        conn.execute("UPDATE npcs SET casa_id = ? WHERE id = ?", (casa_id, target_npc))
                        print(f"🏠 MUDANÇA: {target_npc} mudou-se para {casa_id}!")

            elif cmd == 'DESTRUIR_LOCAL':
                conn.execute("UPDATE locais SET status = 0, integridade = 0 WHERE id = ?", (acao.get('id'),))
                print(f"💥 DESTRUIÇÃO: Local {acao.get('id')} foi reduzido a escombros!")

            elif cmd == 'AFETAR_NPC':
                conn.execute("UPDATE npcs SET saude = saude + ?, humor = ? WHERE id = ?", 
                             (d.get('saude', 0), d.get('humor', 'Neutro'), acao.get('id')))
                print(f"👤 NPC AFETADO: {acao.get('id')} agora está {d.get('humor')}!")

        conn.commit()

        
        print(f"✨ EVENTO LANÇADO: {evento['titulo']}!")
        print(f"📜 {evento['descricao']}")
        print(f"⚙️ Modificadores: {evento['modificadores']}")
        
    except Exception as e:
        print(f"❌ Erro ao gerar evento: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    tema = sys.argv[1] if len(sys.argv) > 1 else "Cyberpunk"
    run_storyteller(tema)
