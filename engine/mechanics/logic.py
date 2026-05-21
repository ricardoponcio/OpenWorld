import json
from ..models import Acao, NPC, HumorNPC
from ..config_loader import cfg_get
from typing import Dict, List

class NPCBrain:
    @staticmethod
    def calcular_utilidade(npc: NPC, hora_atual: int, cfg: Dict, locais: Dict = None, eventos_globais: List = []) -> Dict[Acao, float]:
        utilidades = {acao: 0.0 for acao in Acao}
        if Acao.CONSTRUIR not in utilidades: utilidades[Acao.CONSTRUIR] = 0.0

        is_dependent = (npc.profissao == "dependente" or getattr(npc, 'estagio_vida', '') in ('bebe', 'crianca'))

        # --- GATILHOS DE NECESSIDADE ---
        
        # Comer:
        # Se o NPC já está comendo, ele quer continuar comendo até ficar totalmente satisfeito (fome < 10)
        esta_comendo = (npc.acao_atual == Acao.COMER and npc.fome > 10)
        gatilho_fome = cfg["gatilho_fome_dormindo"] if npc.acao_atual == Acao.DORMIR else cfg["gatilho_fome_normal"]
        if npc.fome > gatilho_fome or esta_comendo:
            valor_fome = npc.fome * 4.0
            if esta_comendo:
                valor_fome += 100.0  # Bônus massivo para não interromper a refeição na metade
            
            # Se não tem dinheiro, a vontade de comer cai (prioriza trabalho ou sono), exceto para dependentes ou idosos (que têm sopão)
            if not is_dependent and not npc.is_idoso() and npc.dinheiro_total_pc < 15:
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
            hora_fim_sono = cfg.get("hora_fim_sono_obrigatorio", 6)
            if hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < hora_fim_sono:
                # É de madrugada, a vontade de dormir deve ser absoluta para evitar que vagueiem pelas ruas
                utilidades[Acao.DORMIR] = 200.0
            elif npc.energia < 95 or npc.acao_atual == Acao.DORMIR:
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
            
        # Debuff de Socialização se estiver pobre, a menos que existam locais públicos/gratuitos (praças/parques) no mundo
        limiar_pobreza = cfg_get(cfg, "limiar_pobreza_pc")
        if npc.dinheiro_total_pc < limiar_pobreza:
            from ..utils import LocationUtils
            tem_local_gratis = False
            if locais:
                for l in locais.values():
                    if l.tipo == 'Social' and getattr(l, 'status', 1) == 1:
                        if LocationUtils.is_local_publico(l):
                            tem_local_gratis = True
                            break
            if not tem_local_gratis:
                utilidades[Acao.SOCIALIZAR] = 0.0
            else:
                # Se tem parque público, ele pode ir socializar de graça, mas o incentivo é menor
                utilidades[Acao.SOCIALIZAR] *= 0.4
            
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
            
        # Construir casa: Se o NPC ou o cônjuge forem donos de uma obra inacabada
        utilidades[Acao.CONSTRUIR] = 0.0
        if locais and not is_dependent and npc.energia >= 25:
            # Não constrói no horário de trabalho formal
            tem_trabalho_ativo = (npc.local_trabalho_id is not None and npc.local_trabalho_id != "" and cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"])
            # Não constrói na madrugada silenciosa (sono profundo)
            hora_sono = (hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < 5)
            
            if not tem_trabalho_ativo and not hora_sono:
                from ..utils import NPCUtils
                if NPCUtils.obter_obra_do_npc(locais, npc):
                    utilidades[Acao.CONSTRUIR] = 200.0  # Foco altíssimo para terminar a casa
        
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

        # --- FORÇAR LIMITES DE DEPENDENTES ---
        if is_dependent:
            utilidades[Acao.TRABALHAR] = 0.0
            utilidades[Acao.SOCIALIZAR] = 0.0
            utilidades[Acao.CUIDAR_PROLE] = 0.0

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

        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, cfg, locais, eventos_globais)
        npc.acao_atual = max(utilidades, key=utilidades.get)

        # Validação de Segurança do Trabalho
        if npc.acao_atual == Acao.TRABALHAR:
            loc_trab = locais.get(npc.local_trabalho_id) if locais else None
            if not loc_trab or getattr(loc_trab, 'status', 1) != 1:
                npc.acao_atual = Acao.OCIOSO
