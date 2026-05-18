import time
import random
from datetime import datetime
from .models import NPC, Evento, Acao, TipoEvento, EstagioVida
from .logger import WorldLogger
from .utils import NPCUtils

class NPCSocialManager:
    @staticmethod
    def processar_interacoes(engine):
        # Utiliza o helper para agrupar NPCs por localização
        por_local = NPCUtils.agrupar_npcs_por_localizacao(engine.npcs, ignorar_dormindo=True)
            
        for loc_id, lista in por_local.items():
            if len(lista) >= 2:
                if random.random() < 0.3:
                    n1, n2 = random.sample(lista, 2)
                    if n1.id != n2.id:
                        NPCSocialManager.gerar_evento_interacao(engine, n1, n2, loc_id)

        # Processar coabitação entre casais de alta afinidade no final do tick social
        NPCSocialManager.processar_coabitacao(engine)

    @staticmethod
    def processar_coabitacao(engine):
        """NPCs adultos solteiros que têm alta afinidade podem decidir morar juntos para constituir família."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        # Chance de união por tick (baixa para ser realista, ex: 2%)
        chance_uniao = 0.02
        
        # Filtrar NPCs vivos e férteis/adultos
        adultos_ferteis = [n for n in engine.npcs if n.esta_vivo() and n.pode_procriar()]
        
        for n1 in adultos_ferteis:
            # Utiliza o helper para obter parceiros adultos na mesma moradia
            parceiros_adultos = NPCUtils.obter_parceiros_adultos_na_casa(engine.npcs, n1)
            if len(parceiros_adultos) > 0:
                continue
                
            # Encontrar potenciais parceiros do gênero oposto com alta afinidade
            for n2 in adultos_ferteis:
                if n1.id == n2.id or n1.genero == n2.genero:
                    continue
                
                # Se n2 também já divide a casa com outro adulto, pula
                parceiros_adultos_2 = NPCUtils.obter_parceiros_adultos_na_casa(engine.npcs, n2)
                if len(parceiros_adultos_2) > 0:
                    continue
                
                # Verificar afinidade
                afinidade = n1.relacionamentos.get(n2.id, 0)
                limiar_uniao = cfg_bio.get("concepcao_afinidade_minima", 80)
                
                if afinidade >= limiar_uniao and n1.casa_id != n2.casa_id:
                    if random.random() < chance_uniao:
                        # Decidem morar juntos!
                        casa_escolhida = n1.casa_id or n2.casa_id
                        if not casa_escolhida:
                            continue
                            
                        # Mudar a casa de n2 para a casa de n1
                        n2.casa_id = casa_escolhida
                        n2.localizacao_atual_id = casa_escolhida
                        
                        # Salvar no banco
                        engine.db.salvar_npc(n2)
                        
                        # Registrar Evento de União
                        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
                        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
                        
                        nome_casa = engine.locais[casa_escolhida].nome if casa_escolhida in engine.locais else "uma nova moradia"
                        resumo = f"❤️ Amor na Vila! {n1.nome} e {n2.nome} decidiram morar juntos em {nome_casa}."
                        
                        evento = Evento(
                            id=f"evt_uniao_{int(time.time())}_{random.randint(0,999)}",
                            timestamp=timestamp_rpg,
                            local_id=casa_escolhida,
                            envolvidos=[n1.id, n2.id],
                            tipo_evento=TipoEvento.CONVERSA.value,
                            modificador_afinidade=30,
                            resumo_estruturado=resumo
                        )
                        engine.db.salvar_evento(evento)
                        
                        # Aumentar afinidade ainda mais
                        n1.relacionamentos[n2.id] = min(1000, n1.relacionamentos[n2.id] + 30)
                        n2.relacionamentos[n1.id] = min(1000, n2.relacionamentos[n1.id] + 30)
                        engine.db.salvar_relacionamento(n1.id, n2.id, n1.relacionamentos[n2.id], "Aliado")
                        
                        WorldLogger.info(f"❤️ [UNIÃO] {resumo}", npc=n1)
                        WorldLogger.queue_db_log(n2, "INFO", f"❤️ [UNIÃO] {resumo}")
                        
                        # Retorna para evitar processar mais de uma união no mesmo tick
                        return

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
        WorldLogger.debug(f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})", npc=n1)
        WorldLogger.queue_db_log(n2, "DEBUG", f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})")

        # --- ROMANCE FÍSICO: Decisão de coabitação durante conversa real ---
        if n1.esta_vivo() and n1.pode_procriar() and n2.esta_vivo() and n2.pode_procriar():
            if n1.genero != n2.genero and n1.casa_id != n2.casa_id:
                # Utiliza o helper para contar parceiros adultos nas respectivas casas
                parceiros_1 = NPCUtils.obter_parceiros_adultos_na_casa(engine.npcs, n1)
                parceiros_2 = NPCUtils.obter_parceiros_adultos_na_casa(engine.npcs, n2)
                
                if len(parceiros_1) == 0 and len(parceiros_2) == 0:
                    cfg_bio = engine.config.get("biologia_e_sociedade", {})
                    limiar_uniao = cfg_bio.get("concepcao_afinidade_minima", 80)
                    if nova_afinidade >= limiar_uniao:
                        # Chance de 15% de decidir morar junto durante a conversa real
                        if random.random() < 0.15:
                            casa_escolhida = n1.casa_id or n2.casa_id
                            if casa_escolhida:
                                n2.casa_id = casa_escolhida
                                n2.localizacao_atual_id = casa_escolhida
                                engine.db.salvar_npc(n2)
                                
                                nome_casa = engine.locais[casa_escolhida].nome if casa_escolhida in engine.locais else "uma nova moradia"
                                resumo_uniao = f"❤️ AMOR NA VILA! {n1.nome} e {n2.nome} aproximaram-se tanto durante a conversa que decidiram morar juntos em {nome_casa}!"
                                
                                # Aumentar afinidade pela união
                                n1.relacionamentos[n2.id] = min(1000, nova_afinidade + 50)
                                n2.relacionamentos[n1.id] = min(1000, nova_afinidade + 50)
                                engine.db.salvar_relacionamento(n1.id, n2.id, n1.relacionamentos[n2.id], "Aliado")
                                
                                evento_uniao = Evento(
                                    id=f"evt_uniao_{int(time.time())}_{random.randint(0,999)}",
                                    timestamp=timestamp_rpg,
                                    local_id=casa_escolhida,
                                    envolvidos=[n1.id, n2.id],
                                    tipo_evento=TipoEvento.CONVERSA.value,
                                    modificador_afinidade=50,
                                    resumo_estruturado=resumo_uniao
                                )
                                engine.db.salvar_evento(evento_uniao)
                                
                                WorldLogger.info(f"❤️ [UNIÃO] {resumo_uniao}", npc=n1)
                                WorldLogger.queue_db_log(n2, "INFO", f"❤️ [UNIÃO] {resumo_uniao}")
