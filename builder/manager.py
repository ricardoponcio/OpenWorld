"""
SCRIPT: manager.py
FUNÇÃO: Orquestrador Principal de Construção de Mundo.
DESCRIÇÃO: Este script coordena a criação inicial do banco de dados, gera o mapa base, 
           os locais padrão e invoca o Generator para criar a população.
USO: python3 builder/manager.py --npcs [QTD] --ia (para geração criativa).
"""
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
                    categoria=l_data.get('categoria', 'publico'),
                    descricao=l_data.get('descricao', f"Local temático de {tema}."), coordenadas=coord)
        db.salvar_local(loc)

    # Criar Casas
    for i, c_id in enumerate(casas_ids):
        coord = mapa_coords.get(c_id, [0,0])
        db.salvar_local(Local(
            id=c_id, 
            nome=f"Residência {i:02d}", 
            tipo="Casa", 
            categoria="residencia",
            descricao="Uma moradia simples.",
            coordenadas=coord
        ))

    # 3. Gerar NPCs
    nomes_gerados = []
    for i in range(num_npcs):
        # Decidir gênero de forma balanceada (Alternado)
        genero_alvo = 'M' if i % 2 == 0 else 'F'

        # NPCs trabalham em locais que não são sociais
        loc_trabalho = random.choice([l for l in profissoes_pool if l['tipo'] != 'Social'])
        casa = random.choice(casas_ids)
        
        dna = None
        if usar_ia:
            print(f"  🧠 Consultando IA para habitante {i+1} ({genero_alvo}) de {tema}...")
            dna = AIWorldGenerator.generate_npc_dna(tema, loc_trabalho['nome'], loc_trabalho['tipo'], genero_alvo, nomes_gerados)
        
        if dna:
            nome = dna.get('nome', f"Habitante {i}")
            profissao = dna.get('cargo', f"Trabalhador de {loc_trabalho['nome']}")
            genero = dna.get('genero', genero_alvo)
        else:
            # Fallback imersivo
            prefixo = "Sir" if genero_alvo == 'M' else "Lady"
            sobrenome = random.choice(["Blackwood", "Thorne", "Stormwind", "Ironfist", "Greycastle", "Oakheart"])
            nome = f"{prefixo} {random.randint(10, 99)} de {sobrenome}"
            profissao = f"Auxiliar de {loc_trabalho['nome']}"
            genero = genero_alvo
        
        nomes_gerados.append(nome)



        # Sorteia idade inicial (18 a 65 anos) e calcula data_nascimento (começo em 1200)
        idade_inicial = random.randint(18, 65)
        ano_nasc = 1200 - idade_inicial
        mes_nasc = random.randint(1, 12)
        dia_nasc = random.randint(1, 28)
        data_nascimento = f"{ano_nasc:04d}-{mes_nasc:02d}-{dia_nasc:02d}T00:00:00"
        estagio_vida = "adulto" if idade_inicial <= 50 else "idoso"

        npc = NPC(
            id=f"npc_{i:03d}",
            nome=nome,
            profissao=profissao,
            casa_id=casa,
            local_trabalho_id=loc_trabalho['id'],
            localizacao_atual_id=casa,
            dinheiro_total_pc=random.randint(200, 2000),
            genero=genero,
            data_nascimento=data_nascimento,
            estagio_vida=estagio_vida
        )
        db.salvar_npc(npc)
        print(f"  ✅ Gerado: {nome} ({genero}) | Idade: {idade_inicial} anos ({estagio_vida}) | Atuação: {profissao}")




    print(f"\n✨ Mundo populado com {num_npcs} habitantes!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=5)
    parser.add_argument("--tema", type=str, default="Fantasia Medieval")
    parser.add_argument("--ia", action="store_true", help="Usa Ollama para gerar nomes e raças")
    args = parser.parse_args()
    
    build_world(args.npcs, args.tema, args.ia)
