from ..models import NPC, Acao, EstagioVida
from ..logger import WorldLogger
from .movement import NPCMovementManager
from ..consultas_npc import NPCUtils
from ..consultas_local import LocationUtils
from ..config_loader import cfg_get
from .kingdom import KingdomManager
from ..mundo import EstadoDoMundo

class NPCActionManager:
    """Executa a ação já escolhida pela Utility AI. Recebe o mundo e a config, não a
    engine (R-F01). Movimento e políticas do reino são colaboradores de domínio e
    entram pelo construtor, para que um teste de ação possa passar um dublê de
    movimento e verificar só o efeito sobre o NPC."""

    def __init__(self, mundo: EstadoDoMundo, config: dict,
                 movimento: NPCMovementManager = None, reino: KingdomManager = None):
        self._mundo = mundo
        self._config = config
        self._movimento = movimento or NPCMovementManager(mundo, config)
        self._reino = reino or KingdomManager(mundo, config)

    def executar_acao(self, npc: NPC, npcs_por_casa: dict = None):
        """Orquestra e delega a execução da ação atual do NPC.

        `npcs_por_casa` (P03, docs/PLANO_CIDADE_VIVA.md): agrupamento de moradores por
        casa, pré-calculado UMA VEZ por tick por `GameLoop.executar_tick` — evita que
        `_executar_comer` (chamado por NPC, por tick) refaça a varredura O(NPCs)."""
        cfg_acoes = cfg_get(self._config, "acoes")
        cfg_bio   = cfg_get(self._config, "biologia_e_sociedade")

        acao = npc.acao_atual

        if acao == Acao.DORMIR:
            self._executar_dormir(npc, cfg_acoes)
        elif acao == Acao.COMER:
            self._executar_comer(npc, cfg_acoes, cfg_bio, npcs_por_casa)
        elif acao == Acao.TRABALHAR:
            self._executar_trabalhar(npc, cfg_acoes)
        elif acao == Acao.SOCIALIZAR:
            self._executar_socializar(npc, cfg_acoes)
        elif acao == Acao.CUIDAR_PROLE:
            self._executar_cuidar_prole(npc, cfg_bio)
        elif acao == Acao.CONSTRUIR:
            self._executar_construir(npc)
        elif acao == Acao.OCIOSO:
            self._executar_ocioso(npc)

    def _executar_dormir(self, npc: NPC, cfg_acoes: dict):
        self._movimento.mover_para_casa(npc)

        cfg = cfg_get(cfg_acoes, "dormir")
        npc.energia += cfg_get(cfg, "energia_ganho")

        hora = self._mundo.data_simulada.hour
        cfg_dec = cfg_get(self._config, "ia_decisao")
        sono_obrigatorio = (hora >= cfg_get(cfg_dec, "hora_inicio_sono_obrigatorio") or
                            hora <  cfg_get(cfg_dec, "hora_inicio_trabalho"))

        # Mesmo limiar de "quase descansado" usado pela Utility AI (NPCBrain) — antes
        # era um 85.0 hardcoded aqui, independente do 85 hardcoded em logic.py.
        energia_quase_descansado = cfg_get(cfg_dec, "energia_quase_descansado")
        if npc.energia >= energia_quase_descansado and not sono_obrigatorio:
            npc.acao_atual = Acao.OCIOSO
            WorldLogger.debug(f"🥱 {npc.nome} acordou e mudou para Ocioso (Energia: {npc.energia:.1f})", npc=npc)

    def _executar_comer(self, npc: NPC, cfg_acoes: dict, cfg_bio: dict, npcs_por_casa: dict = None):
        self._movimento.mover_para_restaurante(npc)

        cfg = cfg_get(cfg_acoes, "comer")
        custo_base   = cfg_get(cfg, "custo_pc")
        fome_rec_max = cfg_get(cfg, "fome_perda")
        multiplicador_por_dependente = cfg_get(cfg, "multiplicador_por_dependente")
        parcelas_refeicao = float(cfg_get(cfg, "parcelas_refeicao"))

        pagador = npc
        num_dependentes = 0
        is_dependent = npc.eh_dependente()

        if is_dependent:
            # Encontrar pai/mãe na mesma casa para pagar a conta
            pais_elegiveis = []
            moradores = NPCUtils.obter_moradores_da_casa(self._mundo.npcs, npc.casa_id, apenas_vivos=True)
            for n in moradores:
                if n.id != npc.id and n.id in (npc.mae_id, npc.pai_id):
                    pais_elegiveis.append(n)
            if pais_elegiveis:
                pais_elegiveis.sort(key=lambda p: p.dinheiro_total_pc, reverse=True)
                pagador = pais_elegiveis[0]
        elif npcs_por_casa is not None:
            num_dependentes = NPCUtils.contar_dependentes_na_casa_agrupado(npc, npcs_por_casa)
        else:
            num_dependentes = NPCUtils.contar_dependentes_na_casa(self._mundo.npcs, npc)

        multiplicador = 1.0 + (multiplicador_por_dependente * num_dependentes)
        custo_final = custo_base * multiplicador

        # Comer progressivo (a refeição inteira leva N ticks de 1 minuto, ver "parcelas_refeicao").
        # Dinheiro é fracionário desde a Frente 4 — sem arredondar/forçar piso de 1 PC por tick.
        custo_do_tick = custo_final / parcelas_refeicao
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
            sopao_ok = self._reino.fornecer_sopao(npc, fome_rec_do_tick, energia_ganho_do_tick)

            if not sopao_ok and WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
                if is_dependent:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] O dependente {npc.nome} está com fome, mas seu responsável {pagador.nome} não tem dinheiro!", npc=npc)
                else:
                    WorldLogger.warning(f"⚠️  [ECONOMIA] {npc.nome} está sem dinheiro para comer!", npc=npc)

    def _executar_trabalhar(self, npc: NPC, cfg_acoes: dict):
        if not npc.local_trabalho_id:
            npc.acao_atual = Acao.OCIOSO
            return

        self._movimento.mover_para_trabalho(npc)

        cfg = cfg_get(cfg_acoes, "trabalhar")
        salario       = cfg_get(cfg, "salario_pc")
        perda_energia = cfg_get(cfg, "energia_perda")

        npc.energia -= perda_energia
        npc.dinheiro_total_pc += salario

        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.debug(f"💼 [TRABALHO] {npc.nome} trabalhou e ganhou {salario} PC (Dinheiro: {npc.dinheiro_total_pc} PC | Energia: {npc.energia:.1f})", npc=npc)

    def _executar_socializar(self, npc: NPC, cfg_acoes: dict):
        self._movimento.mover_para_social(npc)

        cfg  = cfg_get(cfg_acoes, "socializar")
        custo = cfg_get(cfg, "custo_pc")
        ganho_pago = cfg_get(cfg, "social_ganho")
        ganho_gratis = cfg_get(cfg, "social_ganho_gratis")

        local_atual = self._mundo.locais.get(npc.localizacao_atual_id)
        custo_real = custo
        if local_atual and LocationUtils.is_local_publico(local_atual):
            custo_real = 0

        # O humor não é mais setado aqui diretamente — ele é um retrato contínuo
        # do bem-estar (energia/fome/social), recalculado a cada tick por
        # NPCMoodManager. Socializar continua afetando `social` normalmente, que
        # já alimenta esse cálculo. Ver docs/ROADMAP.md, Frente 3.
        if npc.dinheiro_total_pc >= custo_real:
            if custo_real > 0:
                npc.dinheiro_total_pc -= custo_real
            npc.social += ganho_pago
        else:
            # Se não tem dinheiro (e tentou ir a um local pago), tenta socializar de graça mas com menos ganho
            npc.social += ganho_gratis

    def _executar_cuidar_prole(self, npc: NPC, cfg_bio: dict):
        # Mover para casa
        self._movimento.mover_para_casa(npc)

        # Interage e reduz a fome/cansaço dos bebês/crianças na mesma casa
        moradores = NPCUtils.obter_moradores_da_casa(self._mundo.npcs, npc.casa_id, apenas_vivos=True)
        criancas = [m for m in moradores if m.id != npc.id and (m.mae_id == npc.id or m.pai_id == npc.id) and m.estagio_vida in (EstagioVida.BEBE.value, EstagioVida.CRIANCA.value)]

        ganho_social_filho = cfg_get(cfg_bio, "cuidar_prole_ganho_social")
        consumo_energia_adulto = cfg_get(cfg_bio, "cuidar_prole_consumo_energia")

        for c in criancas:
            # Reduz solidão do filho — o clamp final é responsabilidade de
            # `normalizar_necessidades`, chamado no próprio turno de `c` (R-B09).
            c.social += ganho_social_filho

        # Interagir drena energia do adulto
        npc.energia -= consumo_energia_adulto
        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.debug(f"🍼 [FAMÍLIA] {npc.nome} passou tempo cuidando de sua prole em casa.", npc=npc)

    def _executar_ocioso(self, npc: NPC):
        # Anda aleatoriamente pela vila
        self._movimento.mover_aleatoriamente(npc)

        cfg_ocioso = cfg_get(cfg_get(self._config, "acoes"), "ocioso")
        social_perda = cfg_get(cfg_ocioso, "social_perda")

        # Recupera social levemente se encontrar pessoas na rua, drena caso contrário
        npc.social -= social_perda

    def _executar_construir(self, npc: NPC):
        obra = NPCUtils.obter_obra_do_npc(self._mundo, npc)

        if not obra:
            npc.acao_atual = Acao.OCIOSO
            return

        self._movimento.mover_para_obra(npc, obra.id)

        cfg = cfg_get(cfg_get(self._config, "acoes"), "construir")
        perda_energia = cfg_get(cfg, "energia_perda")
        ganho_fome = cfg_get(cfg, "fome_ganho")
        ganho_integridade = cfg_get(cfg, "integridade_ganho_por_tick")

        npc.energia -= perda_energia
        npc.fome += ganho_fome
        obra.integridade += ganho_integridade  # Conclui em ~10 ticks (~2.5 horas in-game de trabalho ativo)
        self._mundo.registrar_local(obra)

        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.debug(f"🔨 [CONSTRUÇÃO] {npc.nome} está construindo a casa! (Integridade: {obra.integridade}%)", npc=npc)

        if obra.integridade >= 100:
            obra.integridade = 100
            obra.status = 1

            # Identifica o dono da obra pelo campo dedicado (R-C03) — não mais
            # parseando "Dono: " de descricao — pra mover a família correta (evita
            # migração nômade em bloco) e nomear a residência.
            dono = next((n for n in self._mundo.npcs if n.id == obra.dono_npc_id), None) or npc
            obra.nome = f"Residência {dono.nome.split()[-1]}"

            moradores = NPCUtils.obter_moradores_da_casa(self._mundo.npcs, dono.casa_id, apenas_vivos=True)
            for m in moradores:
                eh_proprio = (m.id == dono.id)
                eh_conjuge = (dono.conjuge_id and m.id == dono.conjuge_id)

                # Apenas filhos dependentes se movem com os pais. Filhos adultos continuam na casa antiga.
                eh_filho_dependente = False
                if (m.pai_id and m.pai_id in [dono.id, dono.conjuge_id]) or (m.mae_id and m.mae_id in [dono.id, dono.conjuge_id]):
                    if m.eh_dependente():
                        eh_filho_dependente = True

                if eh_proprio or eh_conjuge or eh_filho_dependente:
                    m.casa_id = obra.id
                    m.localizacao_atual_id = obra.id
                    self._mundo.db.npcs.salvar(m)

            self._mundo.registrar_local(obra)  # P02: status virou 1 — reindexa (ex.: residencias_ativas)
            WorldLogger.info(f"🏡 [MUDANÇA] A família de {dono.nome} finalizou a obra e se mudou para a {obra.nome}!", npc=dono)
            npc.acao_atual = Acao.OCIOSO
