import random
from .models import NPC, Acao, EstagioVida, HumorNPC
from .logger import WorldLogger
from .movement import NPCMovementManager
from .utils import NPCUtils

class NPCActionManager:
    @staticmethod
    def executar_acao(engine, npc: NPC):
        """Orquestra e delega a execução da ação atual do NPC."""
        cfg_acoes = engine.config.get("acoes", {})
        cfg_bio = engine.config.get("biologia_e_sociedade", {})
        
        acao = npc.acao_atual
        
        if acao == Acao.DORMIR:
            NPCActionManager._executar_dormir(engine, npc, cfg_acoes)
        elif acao == Acao.COMER:
            NPCActionManager._executar_comer(engine, npc, cfg_acoes, cfg_bio)
        elif acao == Acao.TRABALHAR:
            NPCActionManager._executar_trabalhar(engine, npc, cfg_acoes)
        elif acao == Acao.SOCIALIZAR:
            NPCActionManager._executar_socializar(engine, npc, cfg_acoes)
        elif acao == Acao.CUIDAR_PROLE:
            NPCActionManager._executar_cuidar_prole(engine, npc, cfg_bio)
        elif acao == Acao.OCIOSO:
            NPCActionManager._executar_ocioso(engine, npc, cfg_acoes)
            
        # Validação Final de Segurança de Localização redundante e robusta
        if npc.localizacao_atual_id not in engine.locais and npc.localizacao_atual_id != npc.casa_id:
            npc.localizacao_atual_id = npc.casa_id

    @staticmethod
    def _executar_dormir(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_casa(engine, npc)
        cfg = cfg_acoes.get("dormir", {})
        npc.energia += cfg.get("energia_ganho", 15.0)
        npc.fome += cfg.get("fome_ganho", 2.0)

    @staticmethod
    def _executar_comer(engine, npc: NPC, cfg_acoes: dict, cfg_bio: dict):
        NPCMovementManager.mover_para_restaurante(engine, npc)

        cfg = cfg_acoes.get("comer", {})
        custo_base = cfg.get("custo_pc", 15)
        fome_rec_max = cfg.get("fome_perda", 30.0)
        pc_por_fome = custo_base / fome_rec_max
        
        pagador = npc
        num_dependentes = 0
        is_dependent = (npc.profissao == "dependente" or npc.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value))
        
        if is_dependent:
            # Encontrar pai/mãe na mesma casa para pagar a conta
            pais_elegiveis = []
            moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id and n.id in (npc.mae_id, npc.pai_id):
                    pais_elegiveis.append(n)
            if pais_elegiveis:
                pais_elegiveis.sort(key=lambda p: p.dinheiro_total_pc, reverse=True)
                pagador = pais_elegiveis[0]
        else:
            moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id:
                    if n.mae_id == npc.id or n.pai_id == npc.id:
                        if n.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value) or n.profissao == 'dependente':
                            num_dependentes += 1
                            
        multiplicador = 1.0 + (0.8 * num_dependentes)
        custo_final = int(custo_base * multiplicador)
        
        if pagador.dinheiro_total_pc >= custo_final:
            npc.fome -= fome_rec_max
            pagador.dinheiro_total_pc -= custo_final
            npc.energia += cfg.get("energia_ganho", 5.0)
            
            if is_dependent:
                WorldLogger.debug(f"🍔 [ALIMENTAÇÃO INFANTIL] O dependente {npc.nome} comeu. A refeição custou {custo_final} PC e foi paga por {pagador.nome} (Saldo restante: {pagador.dinheiro_total_pc} PC | Fome: {npc.fome:.1f})", npc=npc)
            else:
                dep_str = f" com {num_dependentes} dependentes" if num_dependentes > 0 else ""
                WorldLogger.debug(f"🍔 [ALIMENTAÇÃO] {npc.nome} comprou uma refeição{dep_str} por {custo_final} PC (Dinheiro restante: {npc.dinheiro_total_pc} PC | Fome: {npc.fome:.1f})", npc=npc)
        elif pagador.dinheiro_total_pc > 0:
            # Comer parcial (subnutrido)
            fome_rec = pagador.dinheiro_total_pc / pc_por_fome
            npc.fome -= fome_rec
            custo_pago = pagador.dinheiro_total_pc
            pagador.dinheiro_total_pc = 0
            energia_ganho = (custo_pago / custo_final) * cfg.get("energia_ganho", 5.0)
            npc.energia += energia_ganho
            
            if is_dependent:
                WorldLogger.warning(f"⚠️  [SUBNUTRIÇÃO INFANTIL] O dependente {npc.nome} comeu parcialmente (pago por {pagador.nome}, gastou {custo_pago} PC, reduziu fome em {fome_rec:.1f})", npc=npc)
            else:
                WorldLogger.warning(f"⚠️  [SUBNUTRIÇÃO] {npc.nome} comeu parcialmente (gastou {custo_pago} PC, reduziu fome em {fome_rec:.1f})", npc=npc)
        else:
            # NPC tentou comer mas não tinha dinheiro
            if engine.tick_count % 4 == 0:
                if is_dependent:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] O dependente {npc.nome} está com fome, mas seu responsável {pagador.nome} não tem dinheiro!", npc=npc)
                else:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] {npc.nome} está sem dinheiro para comer!", npc=npc)

    @staticmethod
    def _executar_trabalhar(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_trabalho(engine, npc)
        # Se ao tentar trabalhar ele virar ocioso (trabalho inativo), aborta os efeitos de trabalho
        if npc.acao_atual == Acao.OCIOSO:
            NPCActionManager._executar_ocioso(engine, npc, engine.config.get("acoes", {}))
            return
            
        cfg = cfg_acoes.get("trabalhar", {})
        npc.energia -= cfg.get("energia_perda", 10.0)
        npc.dinheiro_total_pc += cfg.get("salario_pc", 100)

    @staticmethod
    def _executar_socializar(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_social(engine, npc)

        cfg = cfg_acoes.get("socializar", {})
        custo = cfg.get("custo_pc", 10)
        if npc.dinheiro_total_pc >= custo:
            npc.energia -= cfg.get("energia_perda", 5.0)
            npc.social += cfg.get("social_ganho", 15.0)
            npc.dinheiro_total_pc -= custo

    @staticmethod
    def _executar_cuidar_prole(engine, npc: NPC, cfg_bio: dict):
        NPCMovementManager.mover_para_casa(engine, npc)
        custo_energia = cfg_bio.get("cuidar_prole_consumo_energia", 2.0)
        ganho_social = cfg_bio.get("cuidar_prole_ganho_social", 15.0)
        npc.energia -= custo_energia
        npc.social = min(100.0, npc.social + ganho_social)
        npc.humor = HumorNPC.ALEGRE.value
        WorldLogger.debug(f"👶 [CUIDADO] {npc.nome} cuidou dos filhos em casa (Social: {npc.social:.1f} | Humor: {npc.humor})", npc=npc)

    @staticmethod
    def _executar_ocioso(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_casa(engine, npc)
        cfg = cfg_acoes.get("ocioso", {})
        npc.energia += cfg.get("energia_ganho", 2.0)
