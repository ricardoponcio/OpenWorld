from ..models import NPC, EstagioVida
from ..logger import WorldLogger

class KingdomManager:
    @staticmethod
    def processar_pagamentos_reino(engine):
        """Varredura diária (ex: 08:00) para pagar aposentadorias do reino aos idosos."""
        cfg_reino = engine.config.get("reino", {})
        pensao_diaria = cfg_reino.get("pensao_aposentadoria", 40)  # Pagamento diário
        
        pagos = 0
        for npc in engine.npcs:
            if npc.esta_vivo() and npc.is_idoso():
                npc.dinheiro_total_pc += pensao_diaria
                pagos += 1
                
        if pagos > 0:
            WorldLogger.info(f"👑 [REINO] O Rei pagou aposentadoria de {pensao_diaria} PC para {pagos} anciões da vila.")

    @staticmethod
    def fornecer_sopao(engine, npc: NPC, fome_rec_do_tick: float, energia_ganho_do_tick: float):
        """Fornece alimento gratuito para cidadãos na miséria."""
        cfg_reino = engine.config.get("reino", {})
        if not cfg_reino.get("fornecer_sopao", True):
            return False
            
        # Permitir sopão se o NPC for idoso OU se estiver em extrema miséria e fome (> 60) sem dinheiro
        extremamente_pobre = npc.dinheiro_total_pc <= 0 and npc.fome > 60.0
        if not npc.is_idoso() and not extremamente_pobre:
            return False
            
        npc.fome -= (fome_rec_do_tick * 0.5)  # Sopão alimenta menos que refeição paga
        npc.energia += (energia_ganho_do_tick * 0.5)
        
        if engine.tick_count % 4 == 0:
            WorldLogger.info(f"🍲 [SOPÃO COMUNITÁRIO] O reino forneceu um sopão para {npc.nome}, evitando a inanição.", npc=npc)
        return True
