import json
from ..models import Acao, NPC, HumorNPC
from ..config_loader import cfg_get
from typing import Dict, List

class NPCBrain:
    @staticmethod
    def calcular_utilidade(npc: NPC, hora_atual: int, config: Dict, locais: Dict = None, eventos_globais: List = []) -> Dict[Acao, float]:
        """
        `config` é o config.json completo (não mais só o bloco "ia_decisao") — precisamos
        também de "acoes.comer.custo_pc" para o gatilho de "não tenho dinheiro pra comer".
        Todos os pesos de utilidade (antes literais soltos) agora vêm de
        config["ia_decisao"], ver docs/AUDITORIA_HARDCODE.md.
        """
        cfg = cfg_get(config, "ia_decisao")
        utilidades = {acao: 0.0 for acao in Acao}
        if Acao.CONSTRUIR not in utilidades: utilidades[Acao.CONSTRUIR] = 0.0

        is_dependent = (npc.profissao == "dependente" or getattr(npc, 'estagio_vida', '') in ('bebe', 'crianca'))

        # --- GATILHOS DE NECESSIDADE ---

        # Comer:
        # Se o NPC já está comendo, ele quer continuar comendo até ficar totalmente satisfeito (fome < 10)
        esta_comendo = (npc.acao_atual == Acao.COMER and npc.fome > 10)
        gatilho_fome = cfg["gatilho_fome_dormindo"] if npc.acao_atual == Acao.DORMIR else cfg["gatilho_fome_normal"]
        if npc.fome > gatilho_fome or esta_comendo:
            valor_fome = npc.fome * cfg_get(cfg, "multiplicador_valor_fome")
            if esta_comendo:
                valor_fome += cfg_get(cfg, "bonus_nao_interromper_refeicao")  # Bônus para não interromper a refeição na metade

            # Se não tem dinheiro nem para uma refeição, a vontade de comer cai (prioriza trabalho ou
            # sono), exceto para dependentes ou idosos (que têm sopão)
            custo_refeicao = cfg_get(config, "acoes", "comer", "custo_pc")
            if not is_dependent and not npc.is_idoso() and npc.dinheiro_total_pc < custo_refeicao:
                valor_fome *= cfg_get(cfg, "fator_fome_sem_dinheiro")
            utilidades[Acao.COMER] = valor_fome

        # Dormir:
        energia_quase_descansado = cfg_get(cfg, "energia_quase_descansado")
        utilidade_dormir_maxima = cfg_get(cfg, "utilidade_dormir_maxima")
        if (cfg["hora_inicio_trabalho"] <= hora_atual < cfg["hora_inicio_sono_obrigatorio"]):
            # Se exausto (energia abaixo do desmaio) ou já está dormindo e não está totalmente descansado
            esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < energia_quase_descansado)

            if npc.energia < cfg["energia_limiar_desmaio"] or esta_descansando:
                utilidades[Acao.DORMIR] = utilidade_dormir_maxima
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
                utilidades[Acao.DORMIR] = utilidade_dormir_maxima
            elif npc.energia < cfg_get(cfg, "energia_satisfacao_sono") or npc.acao_atual == Acao.DORMIR:
                utilidades[Acao.DORMIR] = (100 - npc.energia) * cfg_get(cfg, "multiplicador_dormir_leve")

        # --- AGENDA E TRABALHO ---
        if npc.local_trabalho_id and cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"]:
            esta_descansando = (npc.acao_atual == Acao.DORMIR and npc.energia < energia_quase_descansado)
            # Se o NPC estiver exausto ou no processo de descanso forçado, ele não consegue trabalhar
            if npc.energia < cfg["energia_limiar_desmaio"] or esta_descansando:
                utilidades[Acao.TRABALHAR] = 0.0
            else:
                utilidades[Acao.TRABALHAR] = cfg_get(cfg, "utilidade_trabalhar")
        else:
            utilidades[Acao.TRABALHAR] = 0.0

        # Socializar: Bônus GIGANTE no Happy Hour
        if cfg["hora_fim_trabalho"] < hora_atual < cfg["hora_inicio_sono_obrigatorio"]:
            utilidades[Acao.SOCIALIZAR] = cfg["bonus_happy_hour"] + (100 - npc.social)
        elif hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg["hora_inicio_trabalho"]:
            utilidades[Acao.SOCIALIZAR] = (100 - npc.social) * cfg_get(cfg, "multiplicador_socializar_fora_happy_hour")

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
                utilidades[Acao.SOCIALIZAR] *= cfg_get(cfg, "fator_socializar_com_local_publico_pobre")

        # Se tem dependentes, reduz a utilidade de socializar
        num_dep = getattr(npc, 'num_dependentes', 0)
        if num_dep > 0:
            utilidades[Acao.SOCIALIZAR] *= cfg_get(cfg, "fator_socializar_com_dependentes")

        # Cuidar da Prole: Apenas se tiver dependentes na mesma casa
        if num_dep > 0:
            vontade_cuidar = (100 - npc.social) * cfg_get(cfg, "multiplicador_vontade_cuidar_prole")
            if not (cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"]):
                vontade_cuidar += cfg_get(cfg, "bonus_cuidar_prole_fora_expediente")  # Prefere cuidar fora do horário de trabalho
            if npc.energia < cfg_get(cfg, "energia_minima_cuidar_prole"):
                vontade_cuidar = 0.0
            utilidades[Acao.CUIDAR_PROLE] = vontade_cuidar
        else:
            utilidades[Acao.CUIDAR_PROLE] = 0.0

        # Construir casa: Se o NPC ou o cônjuge forem donos de uma obra inacabada
        utilidades[Acao.CONSTRUIR] = 0.0
        if locais and not is_dependent and npc.energia >= cfg_get(cfg, "energia_minima_construir"):
            # Não constrói no horário de trabalho formal
            tem_trabalho_ativo = (npc.local_trabalho_id is not None and npc.local_trabalho_id != "" and cfg["hora_inicio_trabalho"] <= hora_atual <= cfg["hora_fim_trabalho"])
            # Não constrói na madrugada silenciosa (sono profundo)
            hora_sono = (hora_atual >= cfg["hora_inicio_sono_obrigatorio"] or hora_atual < cfg_get(cfg, "hora_fim_construir_madrugada"))

            if not tem_trabalho_ativo and not hora_sono:
                from ..utils import NPCUtils
                if NPCUtils.obter_obra_do_npc(locais, npc):
                    utilidades[Acao.CONSTRUIR] = cfg_get(cfg, "utilidade_construir")  # Foco altíssimo para terminar a casa

        utilidades[Acao.OCIOSO] = cfg_get(cfg, "utilidade_ociosa_base")

        # --- MODIFICADORES DE HUMOR ---
        if npc.humor in [HumorNPC.PANICO.value, HumorNPC.MEDO.value, HumorNPC.ANGUSTIADO.value]:
            utilidades[Acao.DORMIR] += cfg_get(cfg, "bonus_dormir_medo")  # Tendência a se esconder em casa
            utilidades[Acao.SOCIALIZAR] -= cfg_get(cfg, "penalidade_socializar_medo")

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
    def decidir_acao(npc: NPC, hora_atual: int, config: Dict, locais: Dict = None, eventos_globais: List = []):
        """`config` é o config.json completo — ver `calcular_utilidade`."""
        # --- REDE DE SEGURANÇA: Habitação ---
        if locais and (npc.casa_id not in locais):
            casas_disponiveis = [l_id for l_id, l in locais.items() if l.tipo == 'Casa' or getattr(l, 'categoria', '') == 'residencia']
            if casas_disponiveis:
                npc.casa_id = casas_disponiveis[0]

        utilidades = NPCBrain.calcular_utilidade(npc, hora_atual, config, locais, eventos_globais)
        npc.acao_atual = max(utilidades, key=utilidades.get)

        # Validação de Segurança do Trabalho
        if npc.acao_atual == Acao.TRABALHAR:
            loc_trab = locais.get(npc.local_trabalho_id) if locais else None
            if not loc_trab or getattr(loc_trab, 'status', 1) != 1:
                npc.acao_atual = Acao.OCIOSO
