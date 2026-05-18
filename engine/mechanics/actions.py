import random
from ..models import NPC, Acao, EstagioVida, HumorNPC
from ..logger import WorldLogger
from .movement import NPCMovementManager
from ..utils import NPCUtils

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
            NPCActionManager._executar_ocioso(engine, npc)

    @staticmethod
    def _executar_dormir(engine, npc: NPC, cfg_acoes: dict):
        cfg = cfg_acoes.get("dormir", {})
        # Restaura energia
        npc.energia += cfg.get("energia_ganho", 5.0)
        if npc.energia > 100.0:
            npc.energia = 100.0
            
        # Acorda se estiver com energia cheia e não for sono obrigatório
        hora = engine.data_simulada.hour
        cfg_dec = engine.config.get("ia_decisao", {})
        sono_obrigatorio = (hora >= cfg_dec.get("hora_inicio_sono_obrigatorio", 22) or 
                            hora < cfg_dec.get("hora_fim_sono_obrigatorio", 8))
        
        if npc.energia >= 85.0 and not sono_obrigatorio:
            npc.acao_atual = Acao.OCIOSO
            WorldLogger.debug(f"🥱 {npc.nome} acordou e mudou para Ocioso (Energia: {npc.energia:.1f})", npc=npc)

    @staticmethod
    def _executar_comer(engine, npc: NPC, cfg_acoes: dict, cfg_bio: dict):
        NPCMovementManager.mover_para_restaurante(engine, npc)

        cfg = cfg_acoes.get("comer", {})
        custo_base = cfg.get("custo_pc", 15)
        fome_rec_max = cfg.get("fome_perda", 40.0)
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
        
        # Comer progressivo (a refeição inteira leva 3 ticks de 15 minutos = 45 minutos)
        custo_do_tick = max(1, int(custo_final / 3.0))
        fome_rec_do_tick = fome_rec_max / 3.0
        energia_ganho_do_tick = cfg.get("energia_ganho", 5.0) / 3.0
        
        if pagador.dinheiro_total_pc >= custo_do_tick:
            npc.fome -= fome_rec_do_tick
            pagador.dinheiro_total_pc -= custo_do_tick
            npc.energia += energia_ganho_do_tick
            
            if is_dependent:
                WorldLogger.debug(f"🍔 [ALIMENTAÇÃO PROGRESSIVA INFANTIL] O dependente {npc.nome} comeu uma porção. Custo: {custo_do_tick} PC (Pago por {pagador.nome} | Saldo: {pagador.dinheiro_total_pc} PC | Fome: {npc.fome:.1f})", npc=npc)
            else:
                dep_str = f" com {num_dependentes} dependentes" if num_dependentes > 0 else ""
                WorldLogger.debug(f"🍔 [ALIMENTAÇÃO PROGRESSIVA] {npc.nome} comeu uma porção{dep_str}. Custo: {custo_do_tick} PC (Dinheiro restante: {pagador.dinheiro_total_pc} PC | Fome: {npc.fome:.1f})", npc=npc)
        elif pagador.dinheiro_total_pc > 0:
            # Comer parcial do tick (subnutrido)
            proporcao = pagador.dinheiro_total_pc / custo_do_tick
            fome_rec = fome_rec_do_tick * proporcao
            custo_pago = pagador.dinheiro_total_pc
            pagador.dinheiro_total_pc = 0
            
            npc.fome -= fome_rec
            npc.energia += energia_ganho_do_tick * proporcao
            
            if is_dependent:
                WorldLogger.warning(f"⚠️  [SUBNUTRIÇÃO PROGRESSIVA INFANTIL] O dependente {npc.nome} comeu uma porção parcial (pago por {pagador.nome}, gastou {custo_pago} PC, reduziu fome em {fome_rec:.1f})", npc=npc)
            else:
                WorldLogger.warning(f"⚠️  [SUBNUTRIÇÃO PROGRESSIVA] {npc.nome} comeu uma porção parcial (gastou {custo_pago} PC, reduziu fome em {fome_rec:.1f})", npc=npc)
        else:
            # NPC tentou comer mas não tinha dinheiro
            if engine.tick_count % 4 == 0:
                if is_dependent:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] O dependente {npc.nome} está com fome, mas seu responsável {pagador.nome} não tem dinheiro!", npc=npc)
                else:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] {npc.nome} está sem dinheiro para comer!", npc=npc)

    @staticmethod
    def _executar_trabalhar(engine, npc: NPC, cfg_acoes: dict):
        if not npc.local_trabalho_id:
            npc.acao_atual = Acao.OCIOSO
            return
            
        NPCMovementManager.mover_para_trabalho(engine, npc)
        
        cfg = cfg_acoes.get("trabalhar", {})
        salario = cfg.get("salario_pc", 5)
        perda_energia = cfg.get("energia_perda", 1.8)
        
        npc.energia -= perda_energia
        npc.dinheiro_total_pc += salario
        
        if engine.tick_count % 4 == 0:
            WorldLogger.debug(f"💼 [TRABALHO] {npc.nome} trabalhou e ganhou {salario} PC (Dinheiro: {npc.dinheiro_total_pc} PC | Energia: {npc.energia:.1f})", npc=npc)

    @staticmethod
    def _executar_socializar(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_local_social(engine, npc)
        
        cfg = cfg_acoes.get("socializar", {})
        custo = cfg.get("custo_pc", 20)
        
        if npc.dinheiro_total_pc >= custo:
            npc.dinheiro_total_pc -= custo
            # Acelera ganho social
            npc.social += 15.0
            if npc.social > 100.0:
                npc.social = 100.0
            
            # Melhora humor
            if random.random() < 0.2:
                npc.humor = HumorNPC.ALEGRE.value
        else:
            # Se não tem dinheiro, tenta socializar de graça mas com menos ganho
            npc.social += 5.0
            if npc.social > 100.0:
                npc.social = 100.0
                
            if random.random() < 0.1:
                npc.humor = HumorNPC.TRISTE.value

    @staticmethod
    def _executar_cuidar_prole(engine, npc: NPC, cfg_bio: dict):
        # Mover para casa
        NPCMovementManager.mover_para_casa(engine, npc)
        
        # Interage e reduz a fome/cansaço dos bebês/crianças na mesma casa
        moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
        criancas = [m for m in moradores if m.id != npc.id and (m.mae_id == npc.id or m.pai_id == npc.id) and m.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value)]
        
        for c in criancas:
            # Reduz solidão do filho
            c.social += 10.0
            if c.social > 100.0:
                c.social = 100.0
                
        # Interagir drena um pouco de energia do adulto
        npc.energia -= 1.0
        if engine.tick_count % 4 == 0:
            WorldLogger.debug(f"🍼 [FAMÍLIA] {npc.nome} passou tempo cuidando de sua prole em casa.", npc=npc)

    @staticmethod
    def _executar_ocioso(engine, npc: NPC):
        # Anda aleatoriamente pela vila
        NPCMovementManager.mover_aleatoriamente(engine, npc)
        
        # Recupera social levemente se encontrar pessoas na rua, drena caso contrário
        npc.social -= 0.5
        if npc.social < 0.0:
            npc.social = 0.0
