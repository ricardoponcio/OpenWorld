import time
import random
from datetime import datetime, timedelta
from .models import NPC, Local, Evento, Acao
from .logic import NPCBrain
from .database import DatabaseManager

import json
import os

class SimulationEngine:
    def __init__(self, db_path="database/openworld.db"):
        self.db = DatabaseManager(db_path)
        self.npcs = self.db.carregar_npcs()
        self.locais = self.db.carregar_locais()
        self.tick_count = 0
        
        # Carregar Configuração
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        hora_salva = self.db.carregar_meta("hora_simulada_iso")
        if hora_salva:
            try:
                self.data_simulada = datetime.fromisoformat(hora_salva)
            except:
                self.data_simulada = datetime(1200, 1, 1, 6, 0)
        else:
            self.data_simulada = datetime(1200, 1, 1, 6, 0)

    def adicionar_npc(self, npc: NPC):
        self.db.salvar_npc(npc)
        self.npcs = self.db.carregar_npcs()

    def adicionar_local(self, local: Local):
        self.locais[local.id] = local

    def tick(self):
        self.tick_count += 1
        self.data_simulada += timedelta(minutes=15)
        
        dia = (self.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        hora_formatada = f"Dia {dia}, {self.data_simulada.strftime('%H:%M')}"
        
        self.db.salvar_meta("hora_simulada_iso", self.data_simulada.isoformat())
        self.db.salvar_meta("hora_simulada", hora_formatada)
        
        print(f"\n--- Tick {self.tick_count} | {hora_formatada} ---")
        
        for npc in self.npcs:
            # 1. Metabolismo Base (Vindo do Config)
            meta = self.config["metabolismo"]
            npc.energia -= meta["energia_base_perda"]
            npc.fome += random.uniform(meta["fome_base_ganho_min"], meta["fome_base_ganho_max"])
            npc.social -= random.uniform(meta["social_base_perda_min"], meta["social_base_perda_max"])
            
            # 2. Decisão (Agora passa o config e os locais para o Brain)
            acao_anterior = npc.acao_atual
            NPCBrain.decidir_acao(npc, self.data_simulada.hour, self.config["ia_decisao"], self.locais)

            
            if npc.acao_atual != acao_anterior:
                print(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}")

            # 3. Execução (Vindo do Config)
            cfg_acoes = self.config["acoes"]
            if npc.acao_atual == Acao.DORMIR:
                npc.energia += cfg_acoes["dormir"]["energia_ganho"]
                npc.fome += cfg_acoes["dormir"]["fome_ganho"]
            elif npc.acao_atual == Acao.COMER:
                npc.fome -= cfg_acoes["comer"]["fome_perda"]
                npc.dinheiro_total_pc -= cfg_acoes["comer"]["custo_pc"]
                npc.energia += cfg_acoes["comer"]["energia_ganho"]
            elif npc.acao_atual == Acao.TRABALHAR:
                npc.energia -= cfg_acoes["trabalhar"]["energia_perda"]
                npc.dinheiro_total_pc += cfg_acoes["trabalhar"]["salario_pc"]
            elif npc.acao_atual == Acao.SOCIALIZAR:
                npc.energia -= cfg_acoes["socializar"]["energia_perda"]
                npc.social += cfg_acoes["socializar"]["social_ganho"]
                npc.dinheiro_total_pc -= cfg_acoes["socializar"]["custo_pc"]
            elif npc.acao_atual == Acao.OCIOSO:
                npc.energia += cfg_acoes["ocioso"]["energia_ganho"]



            
            # Garantir limites
            npc.energia = max(0, min(100, npc.energia))
            npc.fome = max(0, min(100, npc.fome))
            npc.social = max(0, min(100, npc.social))
            
            self.db.salvar_npc(npc)
            
        self.processar_interacoes()

    def processar_interacoes(self):
        por_local = {}
        for npc in self.npcs:
            if npc.acao_atual == Acao.DORMIR: continue
            loc_id = npc.localizacao_atual_id
            if loc_id not in por_local: por_local[loc_id] = []
            por_local[loc_id].append(npc)
            
        for loc_id, lista in por_local.items():
            if len(lista) >= 2:
                if random.random() < 0.3:
                    n1, n2 = random.sample(lista, 2)
                    if n1.id != n2.id:
                        self.gerar_evento_interacao(n1, n2, loc_id)

    def gerar_evento_interacao(self, n1: NPC, n2: NPC, loc_id: str):
        local_nome = self.locais[loc_id].nome if loc_id in self.locais else loc_id
        
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
        self.db.salvar_relacionamento(n1.id, n2.id, nova_afinidade, vinculo)

        tipo = "CONVERSA" if mod >= 0 else "DISCUSSAO"
        resumo = f"{n1.nome} e {n2.nome} tiveram uma {tipo} em {local_nome}."
        dia = (self.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {self.data_simulada.strftime('%H:%M')}"
        
        evento = Evento(f"evt_{int(time.time())}_{random.randint(0,999)}", 
                        timestamp_rpg, loc_id, [n1.id, n2.id], tipo, mod, resumo)
        
        self.db.salvar_evento(evento)
        print(f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})")

