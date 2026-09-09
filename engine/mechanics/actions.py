import random
from ..models import NPC, Acao, EstagioVida, HumorNPC
from ..logger import WorldLogger
from .movement import NPCMovementManager
from ..utils import NPCUtils, LocationUtils
from ..config_loader import cfg_get
from .kingdom import KingdomManager

class NPCActionManager:
    @staticmethod
    def executar_acao(engine, npc: NPC):
        """Orquestra e delega a execução da ação atual do NPC."""
        cfg_acoes = cfg_get(engine.config, "acoes")
        cfg_bio   = cfg_get(engine.config, "biologia_e_sociedade")

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
        elif acao == Acao.CONSTRUIR:
            NPCActionManager._executar_construir(engine, npc)
        elif acao == Acao.OCIOSO:
            NPCActionManager._executar_ocioso(engine, npc)

    @staticmethod
    def _executar_dormir(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_casa(engine, npc)

        cfg = cfg_get(cfg_acoes, "dormir")
        npc.energia += cfg_get(cfg, "energia_ganho")
        if npc.energia > 100.0:
            npc.energia = 100.0

        hora = engine.data_simulada.hour
        cfg_dec = cfg_get(engine.config, "ia_decisao")
        sono_obrigatorio = (hora >= cfg_get(cfg_dec, "hora_inicio_sono_obrigatorio") or
                            hora <  cfg_get(cfg_dec, "hora_inicio_trabalho"))

        # Mesmo limiar de "quase descansado" usado pela Utility AI (NPCBrain) — antes
        # era um 85.0 hardcoded aqui, independente do 85 hardcoded em logic.py.
        energia_quase_descansado = cfg_get(cfg_dec, "energia_quase_descansado")
        if npc.energia >= energia_quase_descansado and not sono_obrigatorio:
            npc.acao_atual = Acao.OCIOSO
            WorldLogger.debug(f"🥱 {npc.nome} acordou e mudou para Ocioso (Energia: {npc.energia:.1f})", npc=npc)

    @staticmethod
    def _executar_comer(engine, npc: NPC, cfg_acoes: dict, cfg_bio: dict):
        NPCMovementManager.mover_para_restaurante(engine, npc)

        cfg = cfg_get(cfg_acoes, "comer")
        custo_base   = cfg_get(cfg, "custo_pc")
        fome_rec_max = cfg_get(cfg, "fome_perda")
        multiplicador_por_dependente = cfg_get(cfg, "multiplicador_por_dependente")
        parcelas_refeicao = float(cfg_get(cfg, "parcelas_refeicao"))

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

        multiplicador = 1.0 + (multiplicador_por_dependente * num_dependentes)
        custo_final = int(custo_base * multiplicador)

        # Comer progressivo (a refeição inteira leva N ticks de 15 minutos, ver "parcelas_refeicao")
        custo_do_tick = max(1, int(custo_final / parcelas_refeicao))
        fome_rec_do_tick = fome_rec_max / parcelas_refeicao
        energia_ganho_do_tick = cfg_get(cfg, "energia_ganho") / parcelas_refeicao

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
            sopao_ok = KingdomManager.fornecer_sopao(engine, npc, fome_rec_do_tick, energia_ganho_do_tick)

            if not sopao_ok and engine.tick_count % 4 == 0:
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

        cfg = cfg_get(cfg_acoes, "trabalhar")
        salario       = cfg_get(cfg, "salario_pc")
        perda_energia = cfg_get(cfg, "energia_perda")

        npc.energia -= perda_energia
        npc.dinheiro_total_pc += salario

        if engine.tick_count % 4 == 0:
            WorldLogger.debug(f"💼 [TRABALHO] {npc.nome} trabalhou e ganhou {salario} PC (Dinheiro: {npc.dinheiro_total_pc} PC | Energia: {npc.energia:.1f})", npc=npc)

    @staticmethod
    def _executar_socializar(engine, npc: NPC, cfg_acoes: dict):
        NPCMovementManager.mover_para_local_social(engine, npc)

        cfg  = cfg_get(cfg_acoes, "socializar")
        custo = cfg_get(cfg, "custo_pc")
        ganho_pago = cfg_get(cfg, "social_ganho")
        ganho_gratis = cfg_get(cfg, "social_ganho_gratis")
        chance_alegre = cfg_get(cfg, "chance_ficar_alegre")
        chance_triste = cfg_get(cfg, "chance_ficar_triste")

        local_atual = engine.locais.get(npc.localizacao_atual_id)
        custo_real = custo
        if local_atual and LocationUtils.is_local_publico(local_atual):
            custo_real = 0

        if npc.dinheiro_total_pc >= custo_real:
            if custo_real > 0:
                npc.dinheiro_total_pc -= custo_real
            # Acelera ganho social
            npc.social += ganho_pago
            if npc.social > 100.0:
                npc.social = 100.0

            # Melhora humor
            if random.random() < chance_alegre:
                npc.humor = HumorNPC.ALEGRE.value
        else:
            # Se não tem dinheiro (e tentou ir a um local pago), tenta socializar de graça mas com menos ganho
            npc.social += ganho_gratis
            if npc.social > 100.0:
                npc.social = 100.0

            if random.random() < chance_triste:
                npc.humor = HumorNPC.TRISTE.value

    @staticmethod
    def _executar_cuidar_prole(engine, npc: NPC, cfg_bio: dict):
        # Mover para casa
        NPCMovementManager.mover_para_casa(engine, npc)

        # Interage e reduz a fome/cansaço dos bebês/crianças na mesma casa
        moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, npc.casa_id, apenas_vivos=True)
        criancas = [m for m in moradores if m.id != npc.id and (m.mae_id == npc.id or m.pai_id == npc.id) and m.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value)]

        ganho_social_filho = cfg_get(cfg_bio, "cuidar_prole_ganho_social")
        consumo_energia_adulto = cfg_get(cfg_bio, "cuidar_prole_consumo_energia")

        for c in criancas:
            # Reduz solidão do filho
            c.social += ganho_social_filho
            if c.social > 100.0:
                c.social = 100.0

        # Interagir drena energia do adulto
        npc.energia -= consumo_energia_adulto
        if engine.tick_count % 4 == 0:
            WorldLogger.debug(f"🍼 [FAMÍLIA] {npc.nome} passou tempo cuidando de sua prole em casa.", npc=npc)

    @staticmethod
    def _executar_ocioso(engine, npc: NPC):
        # Anda aleatoriamente pela vila
        NPCMovementManager.mover_aleatoriamente(engine, npc)

        cfg_ocioso = cfg_get(cfg_get(engine.config, "acoes"), "ocioso")
        social_perda = cfg_get(cfg_ocioso, "social_perda")

        # Recupera social levemente se encontrar pessoas na rua, drena caso contrário
        npc.social -= social_perda
        if npc.social < 0.0:
            npc.social = 0.0

    @staticmethod
    def _executar_construir(engine, npc: NPC):
        obra = NPCUtils.obter_obra_do_npc(engine.locais, npc)

        if not obra:
            npc.acao_atual = Acao.OCIOSO
            return

        NPCMovementManager.mover_para_obra(engine, npc, obra.id)

        cfg = cfg_get(cfg_get(engine.config, "acoes"), "construir")
        perda_energia = cfg_get(cfg, "energia_perda")
        ganho_fome = cfg_get(cfg, "fome_ganho")
        ganho_integridade = cfg_get(cfg, "integridade_ganho_por_tick")

        npc.energia -= perda_energia
        npc.fome += ganho_fome
        obra.integridade += ganho_integridade  # Conclui em ~10 ticks (~2.5 horas in-game de trabalho ativo)
        engine.db.salvar_local(obra)

        if engine.tick_count % 4 == 0:
            WorldLogger.debug(f"🔨 [CONSTRUÇÃO] {npc.nome} está construindo a casa! (Integridade: {obra.integridade}%)", npc=npc)

        if obra.integridade >= 100:
            obra.integridade = 100
            obra.status = 1
            nome_familia = obra.nome.replace("Obra de ", "")
            obra.nome = f"Residência {nome_familia}"

            # Identifica o dono da obra para mover a família correta (evita migração nômade em bloco)
            dono_id = obra.descricao.replace("Dono: ", "").strip()
            dono = next((n for n in engine.npcs if n.id == dono_id), None)
            if not dono:
                dono = npc

            moradores = NPCUtils.obter_moradores_da_casa(engine.npcs, dono.casa_id, apenas_vivos=True)
            for m in moradores:
                eh_proprio = (m.id == dono.id)
                eh_conjuge = (dono.conjuge_id and m.id == dono.conjuge_id)

                # Apenas filhos dependentes se movem com os pais. Filhos adultos continuam na casa antiga.
                eh_filho_dependente = False
                if (m.pai_id and m.pai_id in [dono.id, dono.conjuge_id]) or (m.mae_id and m.mae_id in [dono.id, dono.conjuge_id]):
                    is_dep = (m.profissao == "dependente" or getattr(m, 'estagio_vida', '') in ('bebe', 'crianca'))
                    if is_dep:
                        eh_filho_dependente = True

                if eh_proprio or eh_conjuge or eh_filho_dependente:
                    m.casa_id = obra.id
                    m.localizacao_atual_id = obra.id
                    engine.db.salvar_npc(m)

            engine.db.salvar_local(obra)
            WorldLogger.info(f"🏡 [MUDANÇA] A família de {dono.nome} finalizou a obra e se mudou para a {obra.nome}!", npc=dono)
            npc.acao_atual = Acao.OCIOSO
