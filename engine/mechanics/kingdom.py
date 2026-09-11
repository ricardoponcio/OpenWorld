from ..models import NPC, EstagioVida
from ..logger import WorldLogger
from ..config_loader import cfg_get

class KingdomManager:
    @staticmethod
    def processar_pagamentos_reino(engine):
        """Varredura diária (ex: 08:00) para pagar aposentadorias do reino aos idosos."""
        cfg_reino = cfg_get(engine.config, "reino")
        pensao_diaria = cfg_get(cfg_reino, "pensao_aposentadoria")
        
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
        cfg_reino = cfg_get(engine.config, "reino")
        if not cfg_get(cfg_reino, "fornecer_sopao"):
            return False
            
        # Permitir sopão se o NPC for idoso OU se estiver em extrema miséria e fome sem dinheiro
        limiar_miseria = cfg_get(cfg_reino, "sopao_fome_limiar_miseria")
        fator = cfg_get(cfg_reino, "sopao_fator_potencia")
        extremamente_pobre = npc.dinheiro_total_pc <= 0 and npc.fome > limiar_miseria
        if not npc.is_idoso() and not extremamente_pobre:
            return False

        npc.fome -= (fome_rec_do_tick * fator)  # Sopão alimenta menos que refeição paga
        npc.energia += (energia_ganho_do_tick * fator)

        if WorldLogger.deve_logar_amostra(engine.tick_count, engine.config):
            WorldLogger.info(f"🍲 [SOPÃO COMUNITÁRIO] O reino forneceu um sopão para {npc.nome}, evitando a inanição.", npc=npc)
        return True

