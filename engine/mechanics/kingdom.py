"""
MODULE: kingdom.py
FUNÇÃO: Políticas sociais do reino (pensão por idade e sopão comunitário).

DESCRIÇÃO:
    Recebe o mundo e a config, não a engine (R-F01): precisa da lista de NPCs, do
    contador de ticks (para a amostragem de log) e dos parâmetros do bloco `reino`.
"""
from ..models import NPC, EstagioVida
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo


class KingdomManager:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

    def processar_pagamentos_reino(self):
        """Varredura diária (ex: 08:00) para pagar aposentadorias do reino aos idosos."""
        cfg_reino = cfg_get(self._config, "reino")
        pensao_diaria = cfg_get(cfg_reino, "pensao_aposentadoria")

        pagos = 0
        for npc in self._mundo.npcs:
            if npc.esta_vivo() and npc.is_idoso():
                npc.dinheiro_total_pc += pensao_diaria
                pagos += 1

        if pagos > 0:
            WorldLogger.info(f"👑 [REINO] O Rei pagou aposentadoria de {pensao_diaria} PC para {pagos} anciões da vila.")

    def fornecer_sopao(self, npc: NPC, fome_rec_do_tick: float, energia_ganho_do_tick: float):
        """Fornece alimento gratuito para cidadãos na miséria."""
        cfg_reino = cfg_get(self._config, "reino")
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

        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.info(f"🍲 [SOPÃO COMUNITÁRIO] O reino forneceu um sopão para {npc.nome}, evitando a inanição.", npc=npc)
        return True
