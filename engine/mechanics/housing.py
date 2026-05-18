import time
import random
from datetime import datetime
from ..models import Acao, Local
from ..logger import WorldLogger
from ..utils import NPCUtils

class NPCHousingManager:
    @staticmethod
    def processar_habitacao(engine):
        """Verifica diariamente casas superlotadas e inicia a construção de novos lotes para aliviar o espaço."""
        por_casa = NPCUtils.agrupar_por_casa(engine.npcs)
            
        for casa_id, moradores in por_casa.items():
            if casa_id not in engine.locais: continue
            
            casa = engine.locais[casa_id]
            # Se a casa estiver superlotada
            if len(moradores) > casa.capacidade:
                # Procura um casal adulto
                casais = [m for m in moradores if NPCUtils.tem_conjuge(m)]
                if not casais: continue
                
                # Escolhe o casal (pega o primeiro para simplificar)
                n1 = casais[0]
                n2 = next((m for m in moradores if m.id == n1.conjuge_id), None)
                
                # Se não tem um lote em construção, demarcar um!
                # Para evitar múltiplas obras, checamos se eles já são donos de uma obra.
                if NPCUtils.obter_obra_do_npc(engine.locais, n1): continue
                
                # Requer o cartógrafo para alocar
                from ..world.cartographer import Cartographer
                import json
                
                grid_json = engine.db.carregar_meta("mapa_terreno")
                if not grid_json: continue
                
                carto = Cartographer()
                carto.grid = json.loads(grid_json)
                
                nova_obra_id = f"casa_obra_{int(time.time())}_{random.randint(0,999)}"
                coords = carto.assign_coordinates([nova_obra_id])
                if nova_obra_id not in coords: continue
                
                # Salvar novo mapa
                engine.db.salvar_meta("mapa_terreno", carto.export_map())
                
                # Criar a obra
                obra = Local(
                    id=nova_obra_id,
                    nome=f"Obra de {n1.nome.split()[-1]}",
                    tipo="Casa",
                    categoria="residencia",
                    descricao=f"Dono: {n1.id}",
                    coordenadas=coords[nova_obra_id],
                    status=0,
                    integridade=0,
                    capacidade=5
                )
                engine.locais[nova_obra_id] = obra
                engine.db.salvar_local(obra)
                
                WorldLogger.info(f"🏗️ [EXPANSÃO URBANA] Devido à superlotação, a família de {n1.nome} iniciou a construção de uma nova casa na vila!", npc=n1)
