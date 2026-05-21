"""
SCRIPT: world_bootstrap.py
FUNÇÃO: Setup inicial do Banco de Dados a partir da Cartografia Oficial.
DESCRIÇÃO:
    Lê o world_manifest.json gerado pelas rotinas de Cartografia (IA).
    Popula o SQLite com os Continentes e Cidades.
    Elege uma cidade para ser a instância de simulação ativa.
    Gera as tabelas de Jobs, Locais e NPCs base para essa cidade.
"""
import os
import sys
import json
import random
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.database import DatabaseManager
from engine.mechanics.market import JobMarket
from engine.models import Local, NPC, EstadoCivil, Acao, CategoriaLocal, ProfissaoID
from engine.utils import CartographyImporter

MANIFEST_PATH = "database/world_manifest.json"
DB_PATH = "database/openworld.db"

class WorldBootstrap:
    @staticmethod
    def run():
        print("🧨 Iniciando Bootstrap do Mundo Simulado...")

        # 1. Garante Banco Inicializado
        db = DatabaseManager(DB_PATH)
    
        # 3. Importa Cartografia
        cidades_salvas = CartographyImporter.import_manifest(db, MANIFEST_PATH)
    
        if not cidades_salvas:
            return
    
        # 5. Elege a Cidade Principal (Spawn Point da Simulação)
        # Por padrão vamos pegar a primeira, mas pode ser randômico.
        cidade_spawn = cidades_salvas[0]
        print(f"🏰 Cidade Elegida para Simulação: {cidade_spawn['nome']} (ID: {cidade_spawn['db_id']})")
        
        db.salvar_meta("cidade_simulada", str(cidade_spawn['db_id']))
    
        # 6. Geração de Locais Base Locais na Cidade
        # Vamos criar um set básico de locais espalhados numa grade 40x40 abstrata (Mapa Local)
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
    
        # Cria 10 Casas Residenciais
        num_casas = 10
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
    
        # 7. Geração de 20 NPCs
        num_npcs = 20
        print(f"👥 Povoando a cidade com {num_npcs} habitantes...")
        
        limiar_idoso = 100
        limiar_morte = 120
    
        for i in range(num_npcs):
            genero = 'M' if i % 2 == 0 else 'F'
            casa = random.choice(casas_ids)
            
            prefixo = "Sir" if genero == 'M' else "Lady"
            sobrenomes = ["Blackwood", "Thorne", "Stormwind", "Ironfist", "Greycastle", "Oakheart"]
            nome = f"{prefixo} {random.randint(10, 99)} de {random.choice(sobrenomes)}"
            
            if random.random() < 0.85:
                idade_inicial_anos = random.randint(18, 35)
            else:
                idade_inicial_anos = random.randint(55, 70)
                
            idade_inicial_dias = int((idade_inicial_anos / 80.0) * limiar_morte)
            
            if idade_inicial_anos <= 50:
                estagio_vida = "adulto"
            else:
                estagio_vida = "idoso"
                
            data_inicio = datetime(1200, 1, 1, 0, 0)
            dt_nasc = data_inicio - timedelta(days=idade_inicial_dias)
            
            npc = NPC(
                id=f"npc_{i:03d}",
                nome=nome,
                profissao="Aldeão",
                profissao_id=ProfissaoID.OCIOSO.value,
                cidade_id=cidade_spawn['db_id'],
                casa_id=casa,
                local_trabalho_id="",
                localizacao_atual_id=casa,
                dinheiro_total_pc=random.randint(200, 2000),
                genero=genero,
                data_nascimento=dt_nasc.isoformat(),
                estagio_vida=estagio_vida
            )
            db.salvar_npc(npc)
    
        print("✨ BOOTSTRAP CONCLUÍDO! O banco de dados está sincronizado com a Cartografia e pronto para simular.")
