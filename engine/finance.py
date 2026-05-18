import time
import random
from datetime import datetime
from .models import NPC, Evento, Acao, EstagioVida, TipoEvento
from .logger import WorldLogger
from .utils import NPCUtils

class NPCLegacyManager:
    @staticmethod
    def processar_morte(engine, npc: NPC):
        """Processa o falecimento de um NPC, liberando seus recursos e registrando o óbito."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        # 1. Registrar o evento no banco para consistência histórica
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        idade_anos = 0
        if npc.data_nascimento:
            try:
                ano_nasc = int(npc.data_nascimento.split('-')[0])
                idade_anos = engine.data_simulada.year - ano_nasc
            except:
                pass
                
        idade_str = f" aos {idade_anos} anos" if idade_anos > 0 else ""
        resumo = f"Luto na Vila: O habitante {npc.nome} faleceu{idade_str} devido a problemas de saúde/inanição."
        
        evento = Evento(
            id=f"evt_morte_{int(time.time())}_{random.randint(0,999)}",
            timestamp=timestamp_rpg,
            local_id=npc.casa_id or "rua",
            envolvidos=[npc.id],
            tipo_evento=TipoEvento.OBITO.value,
            modificador_afinidade=0,
            resumo_estruturado=resumo
        )
        engine.db.salvar_evento(evento)
        WorldLogger.info(f"💀 [ÓBITO] {resumo}", npc=npc)
        
        # --- FASE 5: Testamento Automático (Herança) ---
        herdeiros = []
        # 1. Procurar filhos vivos em qualquer lugar do mundo
        for n in engine.npcs:
            if n.esta_vivo() and (n.mae_id == npc.id or n.pai_id == npc.id):
                herdeiros.append(n)
                
        # 2. Se não houver filhos vivos, procurar parceiro/cônjuge na mesma casa com alta afinidade
        if not herdeiros and npc.casa_id:
            parceiros = []
            moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id:
                    afinidade = npc.relacionamentos.get(n.id, 0)
                    limiar_conjuge = cfg_bio.get("heranca_afinidade_minima_conjuge", 50)
                    if afinidade >= limiar_conjuge:
                        parceiros.append((n, afinidade))
            if parceiros:
                parceiros.sort(key=lambda x: x[1], reverse=True)
                herdeiros.append(parceiros[0][0])
                
        total_heranca = npc.dinheiro_total_pc
        if total_heranca > 0:
            if herdeiros:
                parte = total_heranca // len(herdeiros)
                nomes_herdeiros = ", ".join([h.nome for h in herdeiros])
                for h in herdeiros:
                    h.dinheiro_total_pc += parte
                    engine.db.salvar_npc(h) # Persistir o dinheiro herdado no banco
                
                resumo_heranca = f"Testamento de {npc.nome}: A herança de {npc.dinheiro_formatado} foi dividida entre os herdeiros vivos ({nomes_herdeiros})."
                WorldLogger.info(f"💰 [HERANÇA] {resumo_heranca}", npc=npc)
                
                evt_heranca = Evento(
                    id=f"evt_heranca_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id] + [h.id for h in herdeiros],
                    tipo_evento=TipoEvento.HERANCA.value,
                    modificador_afinidade=cfg_bio.get("heranca_evento_modificador_afinidade", 10),
                    resumo_estruturado=resumo_heranca
                )
                engine.db.salvar_evento(evt_heranca)
            else:
                resumo_heranca = f"O dinheiro de {npc.nome} ({npc.dinheiro_formatado}) foi recolhido pelo reino, pois não há herdeiros vivos."
                WorldLogger.info(f"👑 [REINO] {resumo_heranca}", npc=npc)
                
                evt_reino = Evento(
                    id=f"evt_reino_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.IMPOSTO.value,
                    modificador_afinidade=0,
                    resumo_estruturado=resumo_heranca
                )
                engine.db.salvar_evento(evt_reino)
                
            npc.dinheiro_total_pc = 0

        # 2. Desvincular de casa e trabalho para liberar capacidade no mercado
        npc.casa_id = ""
        npc.local_trabalho_id = ""
        npc.localizacao_atual_id = ""
        npc.acao_atual = Acao.OCIOSO
        npc.estagio_vida = EstagioVida.MORTO.value
        npc.saude = 0
        
        # 3. Salvar as alterações finais do NPC falecido no banco de dados
        engine.db.salvar_npc(npc)
