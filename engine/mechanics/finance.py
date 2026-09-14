import time
import random
from datetime import datetime
from ..models import NPC, Evento, Acao, EstagioVida, TipoEvento
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils

from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo

class NPCLegacyManager:
    """Testamento e herança de um NPC falecido. Recebe o mundo e a config, não a
    engine (R-F01): precisa da lista de NPCs (para achar herdeiros) e dos
    repositórios de NPC e evento."""

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def processar_heranca(self, npc: NPC, timestamp_rpg: str):
        """Processa o testamento e a herança financeira de um NPC recém-falecido."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        
        herdeiros = []
        for n in self._mundo.npcs:
            if n.esta_vivo() and (n.mae_id == npc.id or n.pai_id == npc.id):
                herdeiros.append(n)
                
        if not herdeiros and npc.casa_id:
            parceiros = []
            # X04 (docs/PLANO_MUNDO_CRIVEL.md, armadilha 19): índice, não varredura.
            moradores = self._mundo.npcs_por_casa.get(npc.casa_id, ())
            for n in moradores:
                if n.id != npc.id:
                    afinidade = npc.relacionamentos.get(n.id, 0)
                    limiar_conjuge = cfg_get(cfg_bio, "heranca_afinidade_minima_conjuge")
                    if afinidade >= limiar_conjuge:
                        parceiros.append((n, afinidade))
            if parceiros:
                parceiros.sort(key=lambda x: x[1], reverse=True)
                herdeiros.append(parceiros[0][0])
                
        total_heranca = npc.dinheiro_total_pc
        if total_heranca > 0:
            if herdeiros:
                parte = total_heranca / len(herdeiros)  # divisão exata — dinheiro é fracionário desde a Frente 4
                nomes_herdeiros = ", ".join([h.nome for h in herdeiros])
                for h in herdeiros:
                    h.dinheiro_total_pc += parte
                    self._mundo.db.npcs.salvar(h) # Persistir o dinheiro herdado no banco
                
                resumo_heranca = f"Testamento de {npc.nome}: A herança de {npc.dinheiro_formatado} foi dividida entre os herdeiros vivos ({nomes_herdeiros})."
                WorldLogger.info(f"💰 [HERANÇA] {resumo_heranca}", npc=npc)
                
                evt_heranca = Evento(
                    id=f"evt_heranca_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id] + [h.id for h in herdeiros],
                    tipo_evento=TipoEvento.HERANCA.value,
                    modificador_afinidade=cfg_get(cfg_bio, "heranca_evento_modificador_afinidade"),
                    resumo_estruturado=resumo_heranca
                )
                self._mundo.db.eventos.salvar(evt_heranca)
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
                self._mundo.db.eventos.salvar(evt_reino)
                
            npc.dinheiro_total_pc = 0
