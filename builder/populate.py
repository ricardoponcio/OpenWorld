"""
SCRIPT: populate.py
FUNÇÃO: Povoamento Avançado com Inteligência Artificial.
DESCRIÇÃO: Setup inicial de cidades, locais, casas e geração assíncrona de NPCs
           com identidades geradas por IA (via Ollama) ou fallback procedural de alta fidelidade.
USO: python3 builder/populate.py --npcs 20 --ia-max-thread 4 --tema "Fantasia Medieval"
"""
import os
import sys
import json
import random
import argparse
import concurrent.futures
from datetime import datetime, timedelta

# Ajustar path para importar a engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.database import DatabaseManager
from engine.models import Local, NPC, EstadoCivil, Acao, CategoriaLocal, ProfissaoID
from engine.mechanics.market import JobMarket
from builder.generator import AIWorldGenerator
from engine.logger import WorldLogger
from engine.utils import CartographyImporter

MANIFEST_PATH = "database/world_manifest.json"
DB_PATH = "database/openworld.db"

def populate_world(num_npcs=20, tema="Fantasia Medieval", usar_ia=True, ia_max_thread=4):
    print(f"🏗️  Iniciando Povoamento Dinâmico de Mundo (Tema: {tema})")
    
    # 1. Garante Banco Inicializado
    db = DatabaseManager(DB_PATH)
    
    # 2. Lê e Importa Cartografia
    cidades_salvas = CartographyImporter.import_manifest(db, MANIFEST_PATH)
    if not cidades_salvas:
        return

    # 4. Elege a Cidade Principal (Spawn Point)
    cidade_spawn = cidades_salvas[0]
    print(f"🏰 Cidade Principal Selecionada: {cidade_spawn['nome']} (ID: {cidade_spawn['db_id']})")
    db.salvar_meta("cidade_simulada", str(cidade_spawn['db_id']))

    # 5. Geração de Locais Essenciais
    locais_base = [
        {"nome": "Fazenda do Povo", "tipo": "Campo", "categoria": CategoriaLocal.FAZENDA.value},
        {"nome": "Quartel da Guarda", "tipo": "Defesa", "categoria": CategoriaLocal.QUARTEL.value},
        {"nome": f"Taverna de {cidade_spawn['nome']}", "tipo": "Social", "categoria": CategoriaLocal.TAVERNA.value},
        {"nome": "Praça Central", "tipo": "Social", "categoria": CategoriaLocal.PUBLICO.value},
        {"nome": "Mercado das Sedas", "tipo": "Loja", "categoria": CategoriaLocal.MERCADO.value},
        {"nome": "Forja de Ferro", "tipo": "Oficina", "categoria": CategoriaLocal.FORJA.value}
    ]

    print(f"🏗️  Construindo {len(locais_base)} Locais Essenciais...")
    for i, l_data in enumerate(locais_base):
        x_local = random.randint(5, 35)
        y_local = random.randint(5, 35)
        loc = Local(
            id=f"loc_{i:02d}", 
            nome=l_data['nome'], 
            tipo=l_data['tipo'], 
            cidade_id=cidade_spawn['db_id'],
            categoria=l_data['categoria'],
            descricao=f"Estabelecimento fundamental na cidade de {cidade_spawn['nome']}.", 
            coordenadas=[x_local, y_local]
        )
        db.salvar_local(loc)

    # 6. Geração de Residências
    num_casas = max(5, num_npcs // 2)
    casas_ids = []
    print(f"🏠 Construindo {num_casas} Casas Residenciais...")
    for i in range(num_casas):
        c_id = f"casa_{i:02d}"
        casas_ids.append(c_id)
        x_local = random.randint(5, 35)
        y_local = random.randint(5, 35)
        db.salvar_local(Local(
            id=c_id, 
            nome=f"Residência {i:02d}", 
            tipo="Casa", 
            cidade_id=cidade_spawn['db_id'],
            categoria=CategoriaLocal.RESIDENCIA.value,
            descricao="Uma moradia padrão da cidade.",
            coordenadas=[x_local, y_local]
        ))

    # 7. Geração de NPCs com IA (Thread Pool paralela)
    print(f"👥 Povoando cidade com {num_npcs} habitantes usando IA (Workers: {ia_max_thread})...")
    nomes_gerados = []
    npc_params = []
    
    # Preparar parâmetros para cada thread
    for i in range(num_npcs):
        genero_alvo = 'M' if i % 2 == 0 else 'F'
        casa = random.choice(casas_ids)
        # Seleciona local de trabalho base (apenas não sociais para inicialização)
        loc_trabalho = random.choice([l for l in locais_base if l['categoria'] not in (CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value)])
        npc_params.append((i, genero_alvo, loc_trabalho, casa))

    def generate_single_npc(params):
        idx, genero, loc, casa = params
        dna = None
        if usar_ia:
            try:
                dna = AIWorldGenerator.generate_npc_dna(tema, loc['nome'], loc['tipo'], genero, nomes_gerados)
            except Exception as e:
                print(f"⚠️ Falha na geração IA para NPC {idx}: {e}. Ativando Fallback.")
        return (params, dna)

    # Executar thread pool para chamadas rápidas
    resultados = []
    if usar_ia and ia_max_thread > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=ia_max_thread) as executor:
            resultados = list(executor.map(generate_single_npc, npc_params))
    else:
        for p in npc_params:
            resultados.append(generate_single_npc(p))

    # Carregar limites biológicos do config.json
    config_path = "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg_bio = cfg.get("biologia_e_sociedade", {})
    except:
        cfg_bio = {}
        
    limiar_morte = cfg_bio.get("crescimento_dias_idoso_para_morte", 120)

    npcs_gerados = []
    for params, dna in resultados:
        idx, genero_alvo, loc_trabalho, casa = params
        
        if dna:
            nome = dna.get('nome', f"Habitante {idx}")
            profissao = dna.get('cargo', "Aldeão")
            genero = dna.get('genero', genero_alvo)
        else:
            # Fallback procedural de alta fidelidade
            prefixo = "Sir" if genero_alvo == 'M' else "Lady"
            sobrenomes = ["Blackwood", "Thorne", "Stormwind", "Ironfist", "Greycastle", "Oakheart"]
            nome = f"{prefixo} {random.randint(10, 99)} de {random.choice(sobrenomes)}"
            profissao = "Aldeão"
            genero = genero_alvo

        nomes_gerados.append(nome)

        # Distribuir idades proporcionalmente (85% adultos reprodutores, 15% idosos)
        if random.random() < 0.85:
            idade_inicial_anos = random.randint(18, 35)
            estagio_vida = "adulto"
        else:
            idade_inicial_anos = random.randint(55, 70)
            estagio_vida = "idoso"

        idade_inicial_dias = int((idade_inicial_anos / 80.0) * limiar_morte)
        data_inicio = datetime(1200, 1, 1, 0, 0)
        dt_nasc = data_inicio - timedelta(days=idade_inicial_dias)

        npc = NPC(
            id=f"npc_{idx:03d}",
            nome=nome,
            profissao=profissao,
            profissao_id=ProfissaoID.OCIOSO.value,
            cidade_id=cidade_spawn['db_id'],
            casa_id=casa,
            local_trabalho_id="",
            localizacao_atual_id=casa,
            dinheiro_total_pc=random.randint(300, 1500),
            genero=genero,
            data_nascimento=dt_nasc.isoformat(),
            estagio_vida=estagio_vida
        )
        db.salvar_npc(npc)
        npcs_gerados.append(npc)
        print(f"  ✅ Gerado: {nome} ({genero}) | Idade: {idade_inicial_anos} anos | Cargo IA: {profissao}")

    # 8. Formar Casais Iniciais Casados
    print("\n❤️  Estabelecendo casais iniciais casados e coabitantes na vila...")
    adultos_m = [n for n in npcs_gerados if n.genero == 'M' and n.estagio_vida == 'adulto']
    adultos_f = [n for n in npcs_gerados if n.genero == 'F' and n.estagio_vida == 'adulto']
    
    num_casais = min(len(adultos_m), len(adultos_f), num_npcs // 4)
    for idx in range(num_casais):
        m = adultos_m[idx]
        f = adultos_f[idx]
        
        # Escolher uma casa em comum para eles morarem
        casa_comum = m.casa_id or f.casa_id or casas_ids[0]
        m.casa_id = casa_comum
        m.localizacao_atual_id = casa_comum
        f.casa_id = casa_comum
        f.localizacao_atual_id = casa_comum
        
        # Formalizar casamento
        m.estado_civil = EstadoCivil.CASADO.value
        m.conjuge_id = f.id
        f.estado_civil = EstadoCivil.CASADO.value
        f.conjuge_id = m.id
        
        # Ajustar sobrenomes para combinar
        sobrenome_m = m.nome.split()[-1] if len(m.nome.split()) > 1 else ""
        if sobrenome_m and sobrenome_m not in f.nome:
            f.nome = f"{f.nome} {sobrenome_m}"
            
        # Definir afinidade muito alta para concepção imediata
        af = random.randint(85, 95)
        m.relacionamentos[f.id] = af
        f.relacionamentos[m.id] = af
        
        db.salvar_npc(m)
        db.salvar_npc(f)
        
        db.salvar_relacionamento(m.id, f.id, af, "Cônjuge")
        print(f"  ❤️  CASAL FORMADO: {m.nome} e {f.nome} morando na {casa_comum} (Afinidade: {af})!")

    # 9. Relacionamentos Sociais Iniciais
    print("\n💞 Estabelecendo laços sociais e amizades prévias na comunidade...")
    for npc_a in npcs_gerados:
        qtd_amigos = random.randint(2, min(4, len(npcs_gerados) - 1))
        alvos = random.sample([n for n in npcs_gerados if n.id != npc_a.id], k=qtd_amigos)
        
        for npc_b in alvos:
            if npc_b.id in npc_a.relacionamentos:
                continue
                
            af = random.randint(15, 55)
            npc_a.relacionamentos[npc_b.id] = af
            npc_b.relacionamentos[npc_a.id] = af
            
            db.salvar_npc(npc_a)
            db.salvar_npc(npc_b)
            
            vinculo = "Amigo" if af >= 30 else "Conhecido"
            db.salvar_relacionamento(npc_a.id, npc_b.id, af, vinculo)

    # 10. Bootstrap de Vagas e Contratação imediata
    print("\n💼 Inicializando mercado de trabalho e preenchendo vagas...")
    market = JobMarket()
    market.bootstrap_market()
    market.processar_contratacoes()

    print("\n✨ POVOAMENTO COM IA CONCLUÍDO COM SUCESSO!")
    print(f"🏰 Cidade '{cidade_spawn['nome']}' ativa com {len(npcs_gerados)} habitantes prontos para simular.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=20, help="Quantidade de NPCs para gerar")
    parser.add_argument("--tema", type=str, default="Fantasia Medieval", help="Tema criativo da simulação")
    parser.add_argument("--ia-max-thread", type=int, default=4, help="Threads simultâneas de IA via ThreadPool")
    parser.add_argument("--desativar-ia", action="store_true", help="Gera NPCs apenas via fallback procedural rápido")
    args = parser.parse_args()
    
    usar_ia = not args.desativar_ia
    populate_world(args.npcs, args.tema, usar_ia, args.ia_max_thread)
