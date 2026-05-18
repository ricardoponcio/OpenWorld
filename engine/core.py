import time
import random
import sqlite3
from datetime import datetime, timedelta
from .models import NPC, Local, Evento, Acao, EstagioVida, HumorNPC, TipoEvento

from .mechanics import NPCBrain, NPCBiologyManager, NPCLegacyManager, NPCSocialManager, NPCActionManager, NPCHousingManager
from .database import DatabaseManager
from .logger import WorldLogger
from .utils import NPCUtils

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

    def recarregar_habitantes(self):
        """Recarrega os NPCs do banco para sincronizar com mudanças externas (ex: JobMarket)."""
        novos_npcs = self.db.carregar_npcs()
        if novos_npcs:
            self.npcs = novos_npcs
            WorldLogger.debug(f"🔄 Memória sincronizada com o banco de dados ({len(self.npcs)} NPCs).")


    def tick(self):

        self.tick_count += 1
        self.data_simulada += timedelta(minutes=15)
        
        dia = (self.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        hora_formatada = f"Dia {dia}, {self.data_simulada.strftime('%H:%M')}"
        
        self.db.salvar_meta("hora_simulada_iso", self.data_simulada.isoformat())
        self.db.salvar_meta("hora_simulada", hora_formatada)
        
        WorldLogger.info(f"\n--- Tick {self.tick_count} | {hora_formatada} ---")

        # 0. Carregar e Atualizar Eventos Globais
        eventos_globais = self.db.carregar_eventos_globais_ativos()
        for ev in eventos_globais:
            novos_ticks = ev['ticks_restantes'] - 1
            conn = sqlite3.connect(self.db.db_path)
            if novos_ticks <= 0:
                conn.execute("DELETE FROM eventos_globais WHERE id = ?", (ev['id'],))
            else:
                conn.execute("UPDATE eventos_globais SET ticks_restantes = ? WHERE id = ?", (novos_ticks, ev['id']))
            conn.commit()
            conn.close()

        cfg_bio = self.config.get("biologia_e_sociedade", {})
        concepcao_h = cfg_bio.get("concepcao_hora", 3)
        crescimento_h = cfg_bio.get("crescimento_hora", 4)

        # 0.5. Concepção Noturna
        if self.data_simulada.hour == concepcao_h and self.data_simulada.minute == 0:
            NPCBiologyManager.processar_concepcao(self)

        # 0.6. Evolução Temporal / Crescimento
        if self.data_simulada.hour == crescimento_h and self.data_simulada.minute == 0:
            NPCBiologyManager.processar_crescimento(self)
            
        # 0.7. Expansão Imobiliária
        if self.data_simulada.hour == 6 and self.data_simulada.minute == 0:
            NPCHousingManager.processar_habitacao(self)

        maes_parto = []

        for npc in self.npcs:
            if not npc.esta_vivo():
                continue
                
            # 1. Metabolismo Base
            meta = self.config["metabolismo"]
            energia_perda = meta["energia_base_perda"]
            fome_ganho = random.uniform(meta["fome_base_ganho_min"], meta["fome_base_ganho_max"])
            
            # Se for gestante, aumenta consumo de comida e reduz drástica de energia
            if npc.genero == 'F' and npc.gravidez_ticks > 0:
                mult_energia = cfg_bio.get("gravidez_multiplicador_perda_energia", 2.0)
                mult_fome = cfg_bio.get("gravidez_multiplicador_ganho_fome", 1.5)
                energia_perda *= mult_energia
                fome_ganho *= mult_fome
                
                # Decrementar ticks de gravidez
                npc.gravidez_ticks -= 1
                if npc.gravidez_ticks == 0:
                    maes_parto.append(npc)
                    
            npc.energia -= energia_perda
            npc.fome += fome_ganho
            npc.social -= random.uniform(meta["social_base_perda_min"], meta["social_base_perda_max"])
            
            # 2. Decisão (Agora com Eventos Globais)
            # Contar dependentes na mesma casa
            npc.num_dependentes = 0
            moradores = NPCUtils.obter_moradores_da_casa(self.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id:
                    if n.mae_id == npc.id or n.pai_id == npc.id:
                        if n.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value) or n.profissao == 'dependente':
                            npc.num_dependentes += 1

            acao_anterior = npc.acao_atual
            NPCBrain.decidir_acao(npc, self.data_simulada.hour, self.config["ia_decisao"], self.locais, eventos_globais)



            
            if npc.acao_atual != acao_anterior:
                WorldLogger.debug(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}", npc=npc)

            # 3. Execução (Vindo do Config)
            NPCActionManager.executar_acao(self, npc)

            # 4. Lógica Biológica (Saúde e Morte)
            if npc.fome > 90:
                perda_saude = cfg_bio.get("inaniacao_perda_saude", 5)
                npc.saude -= perda_saude
                WorldLogger.warning(f"💔 [INANIÇÃO] {npc.nome} está perdendo saúde! (Saúde: {npc.saude})", npc=npc)
            elif npc.fome < 20 and npc.acao_atual == Acao.DORMIR:
                if npc.saude < 100:
                    ganho_saude = cfg_bio.get("dormir_ganho_saude", 2)
                    npc.saude = min(100, npc.saude + ganho_saude)

            # Garantir limites
            npc.energia = max(0, min(100, npc.energia))
            npc.fome = max(0, min(100, npc.fome))
            npc.social = max(0, min(100, npc.social))
            npc.saude = max(0, min(100, npc.saude))
            
            if npc.saude <= 0:
                NPCBiologyManager.processar_morte(self, npc)
                continue
            
            self.db.salvar_npc(npc)
        
        # Limpeza de Falecidos da Memória
        self.npcs = [n for n in self.npcs if n.saude > 0]

        # Processar nascimentos de partos ocorridos neste tick
        for mae in maes_parto:
            NPCBiologyManager.processar_parto(self, mae)
            
        NPCSocialManager.processar_interacoes(self)



