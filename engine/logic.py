from .models import Acao, NPC
from typing import Dict

class NPCBrain:
    @staticmethod
    def calcular_utilidade(npc: NPC, hora_atual: int, cfg: Dict) -> Dict[Acao, float]:
        utilidades = {acao: 0.0 for acao in Acao}
        
        # --- GATILHOS DE NECESSIDADE ---
        
        # Comer:
        gatilho_fome = cfg["gatilho_fome_dormindo"] if npc.acao_atual == Acao.DORMIR else cfg["gatilho_fome_normal"]
        if npc.fome > gatilho_fome or npc.acao_atual == Acao.COMER:
            utilidades[Acao.COMER] = npc.fome * 4.0 
            
        # Dormir: 
        if (cfg["hora_inicio_trabalho"] <= hora_atual < cfg["hora_inicio_sono_obrigatorio"]):
            utilidades[Acao.DORMIR] = 100.0 if npc.energia < cfg["energia_limiar_desmaio"] else 0.0
            # Bloqueia sono se estiver faminto no happy hour
            if npc.fome > cfg["fome_urgente_limiar"] and npc.acao_atual != Acao.DORMIR:
                utilidades[Acao.DORMIR] = 0.0
        else:
            # Noite: Sono normal
            if npc.energia < 95 or npc.acao_atual == Acao.DORMIR or (hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg["hora_inicio_trabalho"]):
                utilidades[Acao.DORMIR] = (100 - npc.energia) * 1.5

        # --- AGENDA E TRABALHO ---
        if cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"]:
            utilidades[Acao.TRABALHAR] = 150.0 
        else:
            utilidades[Acao.TRABALHAR] = 0.0

        # Socializar: Bônus GIGANTE no Happy Hour
        if cfg["hora_fim_trabalho"] < hora_atual < cfg["hora_inicio_sono_obrigatorio"]:
            utilidades[Acao.SOCIALIZAR] = cfg["bonus_happy_hour"] + (100 - npc.social)
        elif hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg["hora_inicio_trabalho"]:
            utilidades[Acao.SOCIALIZAR] = (100 - npc.social) * 1.5
        
        utilidades[Acao.OCIOSO] = 10.0

        # BÔNUS DE PERSISTÊNCIA
        if npc.acao_atual in utilidades:
            utilidades[npc.acao_atual] += cfg["bonus_persistencia"] 
            
        return utilidades

    @staticmethod
    def decidir_acao(npc: NPC, hora_atual: int, cfg: Dict, locais: Dict = None):
        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, cfg)
        npc.acao_atual = max(utilidades, key=utilidades.get)
        
        # Buscar locais sociais disponíveis
        sociais = [l_id for l_id, l in locais.items() if l.tipo == 'Social'] if locais else []
        restaurantes = [l_id for l_id, l in locais.items() if l.tipo in ['Social', 'Loja']] if locais else []

        if npc.acao_atual == Acao.DORMIR:
            npc.localizacao_atual_id = npc.casa_id
        elif npc.acao_atual == Acao.TRABALHAR:
            npc.localizacao_atual_id = npc.local_trabalho_id
        elif npc.acao_atual == Acao.SOCIALIZAR:
            # Vai para a primeira taverna/local social que encontrar, ou fica em casa
            npc.localizacao_atual_id = sociais[0] if sociais else npc.casa_id
        elif npc.acao_atual == Acao.COMER:
            # Se já está em casa ou num restaurante, fica. Senão, vai comer fora ou em casa.
            if npc.localizacao_atual_id not in (restaurantes + [npc.casa_id]):
                npc.localizacao_atual_id = restaurantes[0] if restaurantes else npc.casa_id

