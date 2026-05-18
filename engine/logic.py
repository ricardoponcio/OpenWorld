import json
from .models import Acao, NPC, HumorNPC
from typing import Dict, List

class NPCBrain:
    @staticmethod
    def calcular_utilidade(npc: NPC, hora_atual: int, cfg: Dict, eventos_globais: List = []) -> Dict[Acao, float]:
        utilidades = {acao: 0.0 for acao in Acao}

        
        # --- GATILHOS DE NECESSIDADE ---
        
        # Comer:
        # Se o NPC já está comendo, ele quer continuar comendo até ficar totalmente satisfeito (fome < 10)
        esta_comendo = (npc.acao_atual == Acao.COMER and npc.fome > 10)
        gatilho_fome = cfg["gatilho_fome_dormindo"] if npc.acao_atual == Acao.DORMIR else cfg["gatilho_fome_normal"]
        if npc.fome > gatilho_fome or esta_comendo:
            valor_fome = npc.fome * 4.0
            if esta_comendo:
                valor_fome += 100.0  # Bônus massivo para não interromper a refeição na metade
            # Se não tem dinheiro, a vontade de comer cai (prioriza trabalho)
            if npc.dinheiro_total_pc < 15:
                valor_fome *= 0.1
            utilidades[Acao.COMER] = valor_fome
            
        # Dormir: 
        if (cfg["hora_inicio_trabalho"] <= hora_atual < cfg["hora_inicio_sono_obrigatorio"]):
            # Se exausto (energia abaixo do desmaio) ou já está dormindo e não está totalmente descansado (energia < 85)
            esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < 85)
            
            if npc.energia < cfg["energia_limiar_desmaio"] or esta_descansando:
                utilidades[Acao.DORMIR] = 200.0
            else:
                utilidades[Acao.DORMIR] = 0.0
            
            # Bloqueia sono se estiver faminto no happy hour, exceto se estiver exausto ou descansando
            if npc.fome > cfg["fome_urgente_limiar"] and npc.acao_atual != Acao.DORMIR and not (npc.energia < cfg["energia_limiar_desmaio"] or esta_descansando):
                utilidades[Acao.DORMIR] = 0.0
        else:
            # Noite: Sono normal
            if npc.energia < 95 or npc.acao_atual == Acao.DORMIR or (hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg["hora_inicio_trabalho"]):
                utilidades[Acao.DORMIR] = (100 - npc.energia) * 1.5

        # --- AGENDA E TRABALHO ---
        if npc.local_trabalho_id and cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"]:
            esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < 85)
            # Se o NPC estiver exausto ou no processo de descanso forçado, ele não consegue trabalhar
            if npc.energia < cfg["energia_limiar_desmaio"] or esta_descansando:
                utilidades[Acao.TRABALHAR] = 0.0
            else:
                utilidades[Acao.TRABALHAR] = 150.0 
        else:
            utilidades[Acao.TRABALHAR] = 0.0


        # Socializar: Bônus GIGANTE no Happy Hour
        if cfg["hora_fim_trabalho"] < hora_atual < cfg["hora_inicio_sono_obrigatorio"]:
            utilidades[Acao.SOCIALIZAR] = cfg["bonus_happy_hour"] + (100 - npc.social)
        elif hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg["hora_inicio_trabalho"]:
            utilidades[Acao.SOCIALIZAR] = (100 - npc.social) * 1.5
            
        # Debuff de Socialização: se o NPC tiver menos de 50 PC (pouco dinheiro), ele não sai para socializar
        if npc.dinheiro_total_pc < 50:
            utilidades[Acao.SOCIALIZAR] = 0.0
            
        # Se tem dependentes, reduz a utilidade de socializar em 50%
        num_dep = getattr(npc, 'num_dependentes', 0)
        if num_dep > 0:
            utilidades[Acao.SOCIALIZAR] *= 0.5
        
        # Cuidar da Prole: Apenas se tiver dependentes na mesma casa
        if num_dep > 0:
            vontade_cuidar = (100 - npc.social) * 1.2
            if not (cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"]):
                vontade_cuidar += 40.0  # Prefere cuidar fora do horário de trabalho
            if npc.energia < 20:
                vontade_cuidar = 0.0
            utilidades[Acao.CUIDAR_PROLE] = vontade_cuidar
        else:
            utilidades[Acao.CUIDAR_PROLE] = 0.0
        
        utilidades[Acao.OCIOSO] = 10.0

        # --- MODIFICADORES DE HUMOR ---
        if npc.humor in [HumorNPC.PANICO.value, HumorNPC.MEDO.value, HumorNPC.ANGUSTIADO.value]:
            utilidades[Acao.DORMIR] += 50.0 # Tendência a se esconder em casa
            utilidades[Acao.SOCIALIZAR] -= 30.0

        # --- MODIFICADORES DE EVENTOS GLOBAIS ---
        for ev in eventos_globais:
            try:
                mods = json.loads(ev['modificadores'])
                for acao_str, peso in mods.items():
                    if acao_str in Acao.__members__:
                        utilidades[Acao[acao_str]] += peso
            except: continue

        if npc.acao_atual in utilidades and utilidades[npc.acao_atual] > 0.0:
            utilidades[npc.acao_atual] += cfg["bonus_persistencia"] 
            
        return utilidades

    @staticmethod
    def decidir_acao(npc: NPC, hora_atual: int, cfg: Dict, locais: Dict = None, eventos_globais: List = []):
        # --- REDE DE SEGURANÇA: Habitação ---
        if locais and (npc.casa_id not in locais):
            casas_disponiveis = [l_id for l_id, l in locais.items() if l.tipo == 'Casa' or getattr(l, 'categoria', '') == 'residencia']
            if casas_disponiveis:
                npc.casa_id = casas_disponiveis[0]

        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, cfg, eventos_globais)
        npc.acao_atual = max(utilidades, key=utilidades.get)

        # Validação de Segurança do Trabalho
        if npc.acao_atual == Acao.TRABALHAR:
            loc_trab = locais.get(npc.local_trabalho_id) if locais else None
            if not loc_trab or getattr(loc_trab, 'status', 1) != 1:
                npc.acao_atual = Acao.OCIOSO



