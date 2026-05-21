"""
MODULE: loop.py
FUNÇÃO: Motor do Ciclo de Simulação (GameLoop).

DESCRIÇÃO:
    Gerencia a execução de cada tick da simulação do reino, incluindo
    processamento de metabolismo base, decisões e ações biológicas dos NPCs,
    pagamento de pensões, nascimentos, interações sociais e eventos dinâmicos.
"""
import random
from datetime import datetime, timedelta
from .models import NPC, Evento, Acao, EstagioVida
from .logger import WorldLogger
from .utils import NPCUtils
from .config_loader import cfg_get
from .mechanics import NPCBrain, NPCActionManager
from .mechanics.biology import NPCBiologyManager
from .mechanics.housing import NPCHousingManager
from .mechanics.kingdom import KingdomManager
from .mechanics.social import NPCSocialManager
from .mechanics.events import GlobalEventManager


class GameLoop:
    @staticmethod
    def executar_tick(engine):
        """
        Executa um tick completo da simulação social, biológica e econômica do reino.
        """
        engine.tick_count += 1
        engine.data_simulada += timedelta(minutes=15)
        
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        hora_formatada = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        engine.db.salvar_meta("hora_simulada_iso", engine.data_simulada.isoformat())
        engine.db.salvar_meta("hora_simulada", hora_formatada)
        
        WorldLogger.info(f"\n--- Tick {engine.tick_count} | {hora_formatada} ---")

        # 0. Atualizar Eventos Globais de Forma Desacoplada
        GlobalEventManager.atualizar_eventos_globais(engine)
        eventos_globais = engine.db.carregar_eventos_globais_ativos()

        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        concepcao_h  = cfg_get(cfg_bio, "concepcao_hora")
        crescimento_h = cfg_get(cfg_bio, "crescimento_hora")

        # 0.5. Concepção Noturna
        if engine.data_simulada.hour == concepcao_h and engine.data_simulada.minute == 0:
            NPCBiologyManager.processar_concepcao(engine)

        # 0.6. Evolução Temporal / Crescimento
        if engine.data_simulada.hour == crescimento_h and engine.data_simulada.minute == 0:
            NPCBiologyManager.processar_crescimento(engine)
            
        # 0.7. Expansão Imobiliária
        if engine.data_simulada.hour == 6 and engine.data_simulada.minute == 0:
            NPCHousingManager.processar_habitacao(engine)

        # 0.8. Pagamento de Aposentadorias
        if engine.data_simulada.hour == 8 and engine.data_simulada.minute == 0:
            KingdomManager.processar_pagamentos_reino(engine)

        maes_parto = []

        for npc in engine.npcs:
            if not npc.esta_vivo():
                continue
                
            # 1. Metabolismo Base
            meta = engine.config["metabolismo"]
            energia_perda = meta["energia_base_perda"]
            fome_ganho = random.uniform(meta["fome_base_ganho_min"], meta["fome_base_ganho_max"])
            
            # Se estiver dormindo, reduz o ganho de fome e a perda de energia
            if npc.acao_atual == Acao.DORMIR:
                fome_ganho *= meta.get("multiplicador_fome_dormindo", 0.33)
                energia_perda *= meta.get("multiplicador_energia_dormindo", 0.0)
            
            # Se for gestante, aumenta consumo de comida e reduz drástica de energia
            if npc.genero == 'F' and npc.gravidez_ticks > 0:
                mult_energia = cfg_get(cfg_bio, "gravidez_multiplicador_perda_energia")
                mult_fome    = cfg_get(cfg_bio, "gravidez_multiplicador_ganho_fome")
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
            moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id:
                    if n.mae_id == npc.id or n.pai_id == npc.id:
                        if n.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value) or n.profissao == 'dependente':
                            npc.num_dependentes += 1

            acao_anterior = npc.acao_atual
            NPCBrain.decidir_acao(npc, engine.data_simulada.hour, engine.config["ia_decisao"], engine.locais, eventos_globais)

            if npc.acao_atual != acao_anterior:
                WorldLogger.debug(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}", npc=npc)

            # 3. Execução (Vindo do Config)
            NPCActionManager.executar_acao(engine, npc)

            # 4. Lógica Biológica (Saúde e Morte)
            if npc.fome > 90:
                perda_saude = cfg_get(cfg_bio, "inaniacao_perda_saude")
                npc.saude -= perda_saude
                WorldLogger.warning(f"💔 [INANIÇÃO] {npc.nome} está perdendo saúde! (Saúde: {npc.saude})", npc=npc)
            elif npc.fome < 20 and npc.acao_atual == Acao.DORMIR:
                if npc.saude < 100:
                    ganho_saude = cfg_get(cfg_bio, "dormir_ganho_saude")
                    npc.saude = min(100, npc.saude + ganho_saude)

            # Garantir limites
            npc.energia = max(0, min(100, npc.energia))
            npc.fome = max(0, min(100, npc.fome))
            npc.social = max(0, min(100, npc.social))
            npc.saude = max(0, min(100, npc.saude))
            
            if npc.saude <= 0:
                NPCBiologyManager.processar_morte(engine, npc)
                continue
            
            engine.db.salvar_npc(npc)
        
        # Limpeza de Falecidos da Memória
        engine.npcs = [n for n in engine.npcs if n.saude > 0]

        # Processar nascimentos de partos ocorridos neste tick
        for mae in maes_parto:
            NPCBiologyManager.processar_parto(engine, mae)
            
        NPCSocialManager.processar_interacoes(engine)
