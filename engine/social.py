import time
import random
from datetime import datetime
from .models import NPC, Evento, Acao
from .logger import WorldLogger

class NPCSocialManager:
    @staticmethod
    def processar_interacoes(engine):
        por_local = {}
        for npc in engine.npcs:
            if npc.acao_atual == Acao.DORMIR: continue
            loc_id = npc.localizacao_atual_id
            if loc_id not in por_local: por_local[loc_id] = []
            por_local[loc_id].append(npc)
            
        for loc_id, lista in por_local.items():
            if len(lista) >= 2:
                if random.random() < 0.3:
                    n1, n2 = random.sample(lista, 2)
                    if n1.id != n2.id:
                        NPCSocialManager.gerar_evento_interacao(engine, n1, n2, loc_id)

    @staticmethod
    def gerar_evento_interacao(engine, n1: NPC, n2: NPC, loc_id: str):
        local_nome = engine.locais[loc_id].nome if loc_id in engine.locais else loc_id
        
        # Lógica de Afinidade
        mod = random.choice([-5, 5, 10])
        nova_afinidade = n1.relacionamentos.get(n2.id, 0) + mod
        
        n1.relacionamentos[n2.id] = nova_afinidade
        n2.relacionamentos[n1.id] = nova_afinidade
        
        # Determinar Vínculo
        vinculo = "Conhecido"
        if nova_afinidade >= 70: vinculo = "Aliado"
        elif nova_afinidade >= 30: vinculo = "Amigo"
        elif nova_afinidade < -20: vinculo = "Rival"
        elif nova_afinidade < -50: vinculo = "Inimigo"

        # Salvar na tabela oficial de relacionamentos
        engine.db.salvar_relacionamento(n1.id, n2.id, nova_afinidade, vinculo)

        tipo = "CONVERSA" if mod >= 0 else "DISCUSSAO"
        resumo = f"{n1.nome} e {n2.nome} tiveram uma {tipo} em {local_nome}."
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        evento = Evento(f"evt_{int(time.time())}_{random.randint(0,999)}", 
                        timestamp_rpg, loc_id, [n1.id, n2.id], tipo, mod, resumo)
        
        engine.db.salvar_evento(evento)
        WorldLogger.debug(f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})")
