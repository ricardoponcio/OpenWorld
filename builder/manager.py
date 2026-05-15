import random
import argparse
import sys
import os

# Ajustar path para importar a engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.models import NPC, Local
from engine.database import DatabaseManager
from builder.generator import AIWorldGenerator
from builder.cartographer import Cartographer

def build_world(num_npcs=5, tema="Vila Medieval", usar_ia=False):
    db = DatabaseManager()
    
    print(f"🏗️  Iniciando Construção de Mundo: {tema}")
    
    # 1. Planejamento Dinâmico de Locais
    num_locais_alvo = max(5, num_npcs // 2)
    ai_locais = []
    
    if usar_ia:
        print(f"🧠 IA gerando planejamento urbano para {num_locais_alvo} locais...")
        ai_locais = AIWorldGenerator.generate_city_locations(tema, num_locais_alvo)
        
        # Validação: Se a IA falhar feio, usamos fallback
        if ai_locais and len(ai_locais) < 3:
            print(f"⚠️ IA gerou poucos locais ({len(ai_locais)}). Usando fallback.")
            ai_locais = None

        if ai_locais:
            for loc in ai_locais:
                if isinstance(loc, dict) and loc.get('nome', '').lower() in ['nome', 'locais', 'nome 1']:
                    loc['nome'] = f"{loc.get('tipo', 'Local')} de {tema}"
    
    if not ai_locais:
        print("⚠️ Usando locais padrão de alta fidelidade.")
        ai_locais = [
            {"nome": "Fazenda das Couves", "tipo": "Campo"},
            {"nome": "Forja de Aço", "tipo": "Oficina"},
            {"nome": "Taverna do Dragão", "tipo": "Social"},
            {"nome": "Quartel da Vila", "tipo": "Defesa"},
            {"nome": "Laboratório Arcano", "tipo": "Magia"},
            {"nome": "Doca do Porto", "tipo": "Mar"}
        ]

    # Normalizar locais
    profissoes_pool = []
    for i, loc in enumerate(ai_locais):
        if isinstance(loc, str):
            loc_dict = {"nome": loc, "tipo": "Outro", "id": f"loc_{i:02d}"}
        else:
            loc_dict = loc
            loc_dict['id'] = f"loc_{i:02d}"
        profissoes_pool.append(loc_dict)

    num_casas = (num_npcs // 2) + 1

    # --- CARTOGRAFIA ---
    carto = Cartographer(size=20)
    grid = carto.generate_terrain()
    
    locais_ids = [l['id'] for l in profissoes_pool]
    casas_ids = [f"casa_{i:02d}" for i in range(1, num_casas + 1)]
    locais_ids += casas_ids
    
    mapa_coords = carto.assign_coordinates(locais_ids)
    db.salvar_meta("mapa_terreno", carto.export_map())

    # Criar Locais no Banco
    for l_data in profissoes_pool:
        coord = mapa_coords.get(l_data['id'], [0, 0])
        loc = Local(id=l_data['id'], nome=l_data['nome'], tipo=l_data['tipo'], 
                    descricao=l_data.get('descricao', f"Local temático de {tema}."), coordenadas=coord)
        db.salvar_local(loc)

    # Criar Casas
    for c_id in casas_ids:
        coord = mapa_coords.get(c_id, [0,0])
        db.salvar_local(Local(c_id, f"Residência {c_id[-2:]}", "Casa", "Moradia.", coord))

    # 3. Gerar NPCs
    for i in range(num_npcs):
        # NPCs trabalham em locais que não são sociais
        loc_trabalho = random.choice([l for l in profissoes_pool if l['tipo'] != 'Social'])
        casa = random.choice(casas_ids)
        
        dna = None
        if usar_ia:
            print(f"  🧠 Consultando IA para habitante {i+1} de {tema}...")
            dna = AIWorldGenerator.generate_npc_dna(tema, loc_trabalho['nome'], loc_trabalho['tipo'])
        
        if dna:
            nome = dna.get('nome', f"Npc {i}")
            profissao = dna.get('cargo', f"Trabalhador de {loc_trabalho['nome']}")
        else:
            nome = f"Habitante {i+1}"
            profissao = f"Trabalhador de {loc_trabalho['nome']}"

        npc = NPC(
            id=f"npc_{i:03d}",
            nome=nome,
            profissao=profissao,
            casa_id=casa,
            local_trabalho_id=loc_trabalho['id'],
            localizacao_atual_id=casa,
            dinheiro_total_pc=random.randint(200, 2000)
        )
        db.salvar_npc(npc)
        print(f"  ✅ Gerado: {nome} | Atuação: {profissao}")



    print(f"\n✨ Mundo populado com {num_npcs} habitantes!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=5)
    parser.add_argument("--tema", type=str, default="Fantasia Medieval")
    parser.add_argument("--ia", action="store_true", help="Usa Ollama para gerar nomes e raças")
    args = parser.parse_args()
    
    build_world(args.npcs, args.tema, args.ia)
