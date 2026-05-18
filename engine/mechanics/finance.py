import time
import random
from datetime import datetime
from ..models import NPC, Evento, Acao, EstagioVida, TipoEvento
from ..logger import WorldLogger
from ..utils import NPCUtils

class NPCLegacyManager:
    @staticmethod
    def processar_heranca(engine, npc: NPC, timestamp_rpg: str):
        """Processa o testamento e a herança financeira de um NPC recém-falecido."""
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        
        # --- Testamento Automático (Herança) ---
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
