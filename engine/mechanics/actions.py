from ..models import NPC, Acao, EstagioVida, ContadorMundo
from ..logger import WorldLogger
from .movement import NPCMovementManager
from ..consultas_npc import NPCUtils
from ..consultas_local import LocationUtils
from ..config_loader import cfg_get
from .kingdom import KingdomManager
from ..mundo import EstadoDoMundo
from . import agenda


def salario_por_minuto(npc: NPC, locais: dict, cfg_acoes: dict) -> float:
    """N02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco N): o salário vem do `Local` de
    trabalho (`salario_base`, 50 a 110 PC conforme o edifício, gravado pelo
    cartógrafo) — `salario_divisor_minutos` (config `acoes.trabalhar`, 600 = minutos
    de um expediente de 10h) é só o CONVERSOR pra PC por minuto, não mais o salário
    em si. Chamado tanto por `NPCActionManager._executar_trabalhar` quanto por
    `GameLoop._aplicar_efeito_continuo` (H04) — a MESMA conta nas duas, ou elas
    divergem em silêncio (armadilha 12, docs/13_PLANO_POPULACAO_E_ESCALA.md). NPC sem
    `local_trabalho_id` válido (fallback/em obra) ganha 0."""
    local = locais.get(npc.local_trabalho_id) if npc.local_trabalho_id else None
    salario_diario = local.salario_base if local is not None else 0
    divisor = cfg_get(cfg_acoes, "trabalhar", "salario_divisor_minutos")
    return salario_diario / divisor


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

        `npcs_por_casa` (P03, docs/12_PLANO_CIDADE_VIVA.md): agrupamento de moradores por
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

    def encontrar_pagador_e_parcela(self, npc: NPC, npcs_por_casa: dict = None):
        """Quem paga a refeição de `npc` (o próprio, ou o pai/mãe mais rico da casa se
        `npc` for dependente) e o custo/ganho POR MINUTO de uma refeição progressiva
        (`parcelas_refeicao` minutos). Extraído de `_executar_comer` (H04, docs/
        14_PLANO_AVANCO_E_CALIBRAGEM.md) pra ser reusado por
        `GameLoop._candidatos_extra_agenda`/`_aplicar_efeito_continuo`, que precisam
        da MESMA conta pra saber quantos minutos de COMER dá pra pular com segurança
        — nunca duplicada, ou as duas versões divergem em silêncio (armadilha 12)."""
        cfg = cfg_get(cfg_get(self._config, "acoes"), "comer")
        custo_base   = cfg_get(cfg, "custo_pc")
        fome_rec_max = cfg_get(cfg, "fome_perda")
        parcelas_refeicao = float(cfg_get(cfg, "parcelas_refeicao"))

        pagador = npc
        num_dependentes = 0
        is_dependent = npc.eh_dependente()

        if is_dependent:
            # Encontrar pai/mãe na mesma casa para pagar a conta
            pais_elegiveis = []
            # X04 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 19): índice mantido
            # incrementalmente (A04) em vez de varrer `mundo.npcs` — caminho por
            # minuto, por NPC.
            moradores = self._mundo.npcs_por_casa.get(npc.casa_id, ())
            for n in moradores:
                if n.id != npc.id and n.id in (npc.mae_id, npc.pai_id):
                    pais_elegiveis.append(n)
            if pais_elegiveis:
                pais_elegiveis.sort(key=lambda p: p.dinheiro_total_pc, reverse=True)
                pagador = pais_elegiveis[0]
        else:
            # X04 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 19): `npcs_por_casa` já é
            # `mundo.npcs_por_casa` (A04) quando o chamador não passa o próprio —
            # nunca mais o fallback O(NPCs) de `contar_dependentes_na_casa`.
            num_dependentes = NPCUtils.contar_dependentes_na_casa_agrupado(
                npc, npcs_por_casa if npcs_por_casa is not None else self._mundo.npcs_por_casa)

        # N03 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco N): cada NPC — dependente ou não —
        # come uma refeição de `custo_pc`, ponto. `multiplicador_por_dependente`
        # cobrava a refeição do adulto MAIS a de cada filho, separadamente — uma
        # família com 3 filhos pagava a refeição do adulto majorada em 2,4× (0,8 ×
        # 3) E as 3 refeições dos filhos por cima. O custo familiar já cresce com o
        # número de filhos porque cada um come a própria refeição.
        # Comer progressivo (a refeição inteira leva N ticks de 1 minuto, ver "parcelas_refeicao").
        # Dinheiro é fracionário desde a Frente 4 — sem arredondar/forçar piso de 1 PC por tick.
        custo_do_tick = custo_base / parcelas_refeicao
        fome_rec_do_tick = fome_rec_max / parcelas_refeicao
        energia_ganho_do_tick = cfg_get(cfg, "energia_ganho") / parcelas_refeicao
        return pagador, is_dependent, num_dependentes, custo_do_tick, fome_rec_do_tick, energia_ganho_do_tick

    def minutos_seguros_para_pular_comer(self, npc: NPC, npcs_por_casa: dict = None) -> int:
        """H04 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): quantos minutos de `Acao.COMER`
        dá pra PULAR em bloco (`GameLoop._aplicar_efeito_continuo`) com garantia de
        que, ao longo de todos eles, o pagador teria dinheiro pra preço CHEIO — o
        menor entre "quantos minutos até a fome cruzar `esta_comendo_fome_minima`" (a
        refeição para de valer a pena) e "quantos minutos o saldo do pagador
        sustenta preço cheio". Depois desse número, o minuto real (`_executar_comer`)
        tem que rodar de verdade — ele decide sozinho entre preço cheio, pagamento
        parcial e sopão, e essa ramificação NÃO é replicada aqui de propósito (é
        exatamente o tipo de "estado interno de curta duração" que A02 já apontava
        como fora de escopo pra generalizar)."""
        cfg_dec = cfg_get(self._config, "ia_decisao")
        pagador, _, _, custo_do_tick, fome_rec_do_tick, _ = self.encontrar_pagador_e_parcela(npc, npcs_por_casa)

        minutos_fome = agenda.minutos_ate_cruzar(
            npc.fome, -fome_rec_do_tick, cfg_get(cfg_dec, "esta_comendo_fome_minima"))
        minutos_dinheiro = (int(pagador.dinheiro_total_pc // custo_do_tick)
                            if custo_do_tick > 0 else agenda.INFINITO)
        return max(0, min(minutos_fome, minutos_dinheiro))

    def _executar_comer(self, npc: NPC, cfg_acoes: dict, cfg_bio: dict, npcs_por_casa: dict = None):
        self._movimento.mover_para_restaurante(npc)

        (pagador, is_dependent, num_dependentes, custo_do_tick,
         fome_rec_do_tick, energia_ganho_do_tick) = self.encontrar_pagador_e_parcela(npc, npcs_por_casa)

        if pagador.dinheiro_total_pc >= custo_do_tick:
            npc.fome -= fome_rec_do_tick
            pagador.dinheiro_total_pc -= custo_do_tick
            npc.energia += energia_ganho_do_tick

            # O01 (docs/16_PLANO_PAINEL_E_IA.md): sem amostragem, era a linha mais
            # frequente do log — 161.971+110.578+94.518 ocorrências numa amostra de
            # 300 MB (Seção 2.2), uma por refeição bem-sucedida de cada NPC.
            if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
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

            # O02 (docs/16_PLANO_PAINEL_E_IA.md): era um warning por NPC subnutrido,
            # por tick — vira estatística agregada, lida pelo coletor (O03).
            self._mundo.contar(ContadorMundo.REFEICAO_PARCIAL)
        else:
            # NPC tentou comer mas não tinha dinheiro
            sopao_ok = self._reino.fornecer_sopao(npc, fome_rec_do_tick, energia_ganho_do_tick)

            if not sopao_ok:
                # O02: idem — 20.241+15.585+... linhas de "sem dinheiro" numa
                # amostra de log (Seção 2.2).
                self._mundo.contar(ContadorMundo.SEM_DINHEIRO_SEM_SOPAO)

    def _executar_trabalhar(self, npc: NPC, cfg_acoes: dict):
        if not npc.local_trabalho_id:
            npc.acao_atual = Acao.OCIOSO
            return

        self._movimento.mover_para_trabalho(npc)

        cfg = cfg_get(cfg_acoes, "trabalhar")
        perda_energia = cfg_get(cfg, "energia_perda")
        salario = salario_por_minuto(npc, self._mundo.locais, cfg_acoes)

        npc.energia -= perda_energia
        npc.dinheiro_total_pc += salario

        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.debug(f"💼 [TRABALHO] {npc.nome} trabalhou e ganhou {salario:.2f} PC (Dinheiro: {npc.dinheiro_total_pc} PC | Energia: {npc.energia:.1f})", npc=npc)

    def _executar_socializar(self, npc: NPC, cfg_acoes: dict):
        """N01 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco N): `custo_pc` é cobrado por
        VISITA, não por minuto — 1,33 PC/min dava 136,9 PC/dia, a maior despesa de
        toda classe (71% da renda do trabalhador, 3,4× a pensão do idoso).

        `chegou_agora` é `localizacao_atual_id` tendo mudado nesta chamada —
        `mover_para_social` (N01) fica no mesmo local social entre ticks, então "não
        mudou" só acontece continuando uma visita já paga. ⚠️ Não cobre o caso raro
        de um NPC que já estava, por coincidência, parado num local social (ex.:
        `mover_aleatoriamente`) no exato tick em que a decisão vira SOCIALIZAR — ele
        entra de graça; aceito (erro sempre a favor do NPC, nunca o inverso do bug
        que esta tarefa corrige)."""
        localizacao_antes = npc.localizacao_atual_id
        self._movimento.mover_para_social(npc)
        chegou_agora = npc.localizacao_atual_id != localizacao_antes

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
        # já alimenta esse cálculo. Ver docs/05_ROADMAP.md, Frente 3.
        if custo_real == 0 or not chegou_agora:
            # Local público (sempre grátis), ou visita já paga na chegada — o ganho
            # social continua todo tick, sem cobrar de novo.
            npc.social += ganho_pago
        elif npc.dinheiro_total_pc >= custo_real:
            npc.dinheiro_total_pc -= custo_real
            npc.social += ganho_pago
        else:
            # Sem dinheiro pra entrar: socializa de graça, com ganho menor.
            npc.social += ganho_gratis

    def _executar_cuidar_prole(self, npc: NPC, cfg_bio: dict):
        # Mover para casa
        self._movimento.mover_para_casa(npc)

        # Interage e reduz a fome/cansaço dos bebês/crianças na mesma casa
        # X04 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 19): índice, não varredura.
        moradores = self._mundo.npcs_por_casa.get(npc.casa_id, ())
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

            # X04 (docs/15_PLANO_MUNDO_CRIVEL.md, armadilha 19): índice, não varredura —
            # mas `list(...)` faz uma CÓPIA: o laço abaixo chama `mudar_casa`, que
            # muta a MESMA lista que `npcs_por_casa` guarda (remove `m` do balde de
            # `dono.casa_id`) — iterar direto sobre o balde vivo pularia elementos.
            moradores = list(self._mundo.npcs_por_casa.get(dono.casa_id, ()))
            for m in moradores:
                eh_proprio = (m.id == dono.id)
                eh_conjuge = (dono.conjuge_id and m.id == dono.conjuge_id)

                # Apenas filhos dependentes se movem com os pais. Filhos adultos continuam na casa antiga.
                eh_filho_dependente = False
                if (m.pai_id and m.pai_id in [dono.id, dono.conjuge_id]) or (m.mae_id and m.mae_id in [dono.id, dono.conjuge_id]):
                    if m.eh_dependente():
                        eh_filho_dependente = True

                if eh_proprio or eh_conjuge or eh_filho_dependente:
                    self._mundo.mudar_casa(m, obra.id)
                    self._mundo.mover_npc(m, obra.id)
                    self._mundo.db.npcs.salvar(m)
                    self._mundo.acordar(m)  # A03: mudou de casa, reavalia agora

            self._mundo.registrar_local(obra)  # P02: status virou 1 — reindexa (ex.: residencias_ativas)
            self._mundo.db.lotes.concluir(obra.id, obra.id)  # O01: lote passa de 'obra' pra 'ocupado'
            WorldLogger.evento_mundo(f"🏡 [MUDANÇA] A família de {dono.nome} finalizou a obra e se mudou para a {obra.nome}!", npc=dono)
            npc.acao_atual = Acao.OCIOSO
