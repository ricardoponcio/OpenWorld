"""
MODULE: loop.py
FUNÇÃO: Motor do Ciclo de Simulação (GameLoop).

DESCRIÇÃO:
    Orquestra cada tick: avança o relógio, atualiza eventos globais, dispara rotinas
    agendadas por hora, e processa cada NPC vivo (metabolismo, decisão, ação,
    consequências de saúde, humor, morte). `GameLoop` só orquestra — a regra de cada
    etapa mora no gerenciador especializado (R-D02: antes um único método de 123 linhas
    fazia tudo isso inline).

    É uma classe de instância construída uma vez por processo (R-F01): ela monta os
    gerenciadores no __init__ e os reusa a cada tick, em vez de receber a engine inteira
    e reconstruir tudo 1440 vezes por dia simulado. Cada gerenciador recebe só o
    `EstadoDoMundo` e a config — nenhum deles conhece a `SimulationEngine`.
"""
import random
from datetime import timedelta
from .models import NPC, Acao, Genero, MetaChave, ESCALA_MAXIMA
from .logger import WorldLogger
from .consultas_npc import NPCUtils
from .config_loader import cfg_get
from .tempo import RelogioMundo
from .mundo import EstadoDoMundo
from .mechanics import NPCBrain, NPCActionManager
from .mechanics.reproduction import NPCReproductionManager
from .mechanics.lifecycle import NPCLifecycleManager
from .mechanics.housing import NPCHousingManager
from .mechanics.urbanismo import GerenciadorUrbanismo
from .mechanics.kingdom import KingdomManager
from .mechanics.social import NPCSocialManager
from .mechanics.events import GlobalEventManager
from .mechanics.mood import NPCMoodManager
from .mechanics import agenda


class GameLoop:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

        # N03 (docs/PLANO_POPULACAO_E_ESCALA.md): estes dois blocos são lidos por NPC,
        # todo tick, dentro de `_aplicar_metabolismo`/`_aplicar_consequencias_de_saude`
        # (1,1 milhão de `cfg_get` por tick medido com 25.000 NPCs). Atributo de
        # instância, montado uma vez aqui — nunca global de módulo nem singleton
        # (ARQUITETURA.md Seção 7: a config é injetada por construtor, e os testes
        # contam com isso pra montar mundos com config diferente).
        self._cfg_bio = cfg_get(config, "biologia_e_sociedade")
        self._cfg_metabolismo = cfg_get(config, "metabolismo")

        # N04 (docs/PLANO_POPULACAO_E_ESCALA.md): retrato (por casa) usado por
        # `_atualizar_dependentes` pra saber quais casas mudaram de composição desde o
        # tick anterior. `None` força um recálculo completo — tanto no primeiro tick
        # quanto depois de `recarregar_habitantes()` trocar `mundo.npcs` por uma lista
        # nova (o mesmo NPC recarregado do banco nasce com `num_dependentes` no default
        # 0, e o retrato sozinho não perceberia isso — daí o segundo atributo abaixo).
        self._assinatura_casas_anterior = None
        self._ultima_lista_de_npcs = None

        # A02 (docs/PLANO_POPULACAO_E_ESCALA.md): quantos NPCs foram efetivamente
        # processados (metabolismo+decisão+ação) no último tick — não é estado de
        # simulação, é só um contador pra `bench_avanco.py`/testes lerem.
        self.decisoes_avaliadas_no_ultimo_tick = 0

        self._acoes = NPCActionManager(mundo, config)
        self._reproducao = NPCReproductionManager(mundo, config)
        self._ciclo_de_vida = NPCLifecycleManager(mundo, config)
        self._urbanismo = GerenciadorUrbanismo(mundo, config)
        self._habitacao = NPCHousingManager(mundo, config, self._urbanismo)
        self._reino = KingdomManager(mundo, config)
        self._social = NPCSocialManager(mundo, config)
        self._eventos_globais = GlobalEventManager(mundo)
        self._humor = NPCMoodManager(config)

        # A06 (docs/PLANO_POPULACAO_E_ESCALA.md): cada mecânica declara a própria
        # cadência (`CADENCIA`/`CADENCIA_HORA_CONFIG`, ver as classes) — acrescentar
        # uma rotina diária nova é acrescentar uma linha aqui, nunca editar
        # `_executar_rotinas_agendadas`. Só `por_dia` existe de verdade hoje; um modo
        # grosso futuro (D17, Seção 5.5 do plano) seria "rode só as `por_dia` e
        # resolva o resto por taxa" — não implementado, mas o ponto de extensão é
        # este registro.
        self._rotinas_diarias = [
            (self._reproducao.CADENCIA_HORA_CONFIG, self._reproducao.processar_concepcao),
            (self._ciclo_de_vida.CADENCIA_HORA_CONFIG, self._ciclo_de_vida.processar_crescimento),
            (self._habitacao.CADENCIA_HORA_CONFIG, self._habitacao.processar_habitacao),
            (self._urbanismo.CADENCIA_HORA_CONFIG, self._urbanismo.processar_urbanismo),
            (self._reino.CADENCIA_HORA_CONFIG, self._reino.processar_pagamentos_reino),
            ("eventos_poda_hora", self._podar_eventos_antigos),
        ]

    def executar_tick(self):
        """Executa um tick completo da simulação social, biológica e econômica do reino."""
        self._avancar_relogio()
        eventos_globais = self._atualizar_eventos_globais()
        self._executar_rotinas_agendadas()

        # P03 (docs/PLANO_CIDADE_VIVA.md) + A04 (docs/PLANO_POPULACAO_E_ESCALA.md):
        # antes recalculado do zero aqui, todo tick (17,3 ms com 25.000 NPCs, metade
        # do "piso" medido em A00). Agora é o índice MANTIDO de `EstadoDoMundo` —
        # atualizado incrementalmente por `mover_npc`/`mudar_casa`/`registrar_npc`/
        # `remover_npc`, nunca reconstruído aqui.
        npcs_por_casa = self._mundo.npcs_por_casa

        maes_em_parto = []
        npcs_alterados = []
        agora = self._mundo.data_simulada

        # H01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 13): os "devidos" agora
        # vêm da agenda de baldes, não de uma varredura de `self._mundo.npcs` inteiro
        # perguntando "você está em dia?" a cada um — o balde de "agora", mais
        # qualquer balde deixado pra trás (raro: um `acordar` no meio de um tick, ou
        # um salto do Mestre), mais o conjunto de consequência (nunca pula, sempre
        # reavaliado). `.values()` é materializado pela `extend` ANTES de qualquer
        # mutação (marcar_consequencia/agendar_decisao) acontecer mais abaixo.
        baldes = self._mundo.baldes_decisao
        devidos = baldes.pop(agora, [])
        if baldes:
            for instante in [k for k in baldes if k <= agora]:
                devidos.extend(baldes.pop(instante))
        devidos.extend(self._mundo.npcs_em_consequencia.values())
        devidos.extend(self._mundo.npcs_sem_agenda.values())

        decisoes_avaliadas = 0
        for npc in devidos:
            if not npc.esta_vivo():
                continue
            decisoes_avaliadas += 1

            # O tempo desde a última vez que ESTE NPC foi processado pode ser maior
            # que 1 minuto (foi pulado). Os minutos "extras" (tudo menos o último)
            # são aplicados de uma vez, com a ação que já estava em andamento — só
            # o ÚLTIMO minuto passa pelo ciclo normal (metabolismo -> decidir ->
            # agir), exatamente como antes de A02. Isso preserva, minuto a minuto, a
            # MESMA sequência de hoje; só deixa de repeti-la de verdade pros minutos
            # em que nada mudaria.
            minutos_totais = agenda.minutos_desde_ultima_avaliacao(npc, agora)
            minutos_extras = minutos_totais - 1
            if minutos_extras > 0:
                self._aplicar_metabolismo(npc, minutos_extras, maes_em_parto)
                self._aplicar_efeito_continuo(npc, minutos_extras)

            self._aplicar_metabolismo(npc, 1, maes_em_parto)
            self._decidir_e_executar(npc, eventos_globais, npcs_por_casa)
            self._aplicar_consequencias_de_saude(npc)
            npc.normalizar_necessidades()
            self._humor.processar_humor(npc, minutos_totais)

            if npc.saude <= 0:
                self._ciclo_de_vida.processar_morte(npc)
                continue

            npc.ultima_avaliacao = agora
            # H01: a classificação "nunca pula" (armadilha 11) passa a decidir se o
            # NPC volta pra um balde ou fica no conjunto de consequência — as duas
            # portas de `EstadoDoMundo` (nunca atribuição direta em
            # `proximo_instante_decisao`, senão a agenda desincroniza em silêncio,
            # mesma armadilha 12 de A04).
            if agenda.em_consequencia(npc, self._cfg_bio):
                self._mundo.marcar_consequencia(npc)
            else:
                proximo = agenda.calcular_proximo_instante(npc, agora, self._config)
                self._mundo.agendar_decisao(npc, proximo)
            npcs_alterados.append(npc)

        self.decisoes_avaliadas_no_ultimo_tick = decisoes_avaliadas

        self._remover_falecidos()
        self._processar_partos(maes_em_parto)
        # P05 (docs/PLANO_CIDADE_VIVA.md): UMA transação pro tick inteiro, não um
        # commit por NPC. N02 (docs/PLANO_POPULACAO_E_ESCALA.md): `salvar_muitos` só
        # regrava as colunas que mudam todo minuto (energia, fome, social, saude,
        # humor, acao_atual, localizacao_atual_id) — as colunas frias (relacionamentos,
        # genealogia etc.) já foram gravadas por `salvar_completo` no ponto do evento
        # que as mudou (parto, morte, casamento...). Depois de partos/mortes de
        # propósito: `processar_parto` pode ter mutado mãe/pai (que já estão em
        # `npcs_alterados`, por referência) — salvar depois pega o estado mais
        # recente, não uma foto de antes do parto. O recém-nascido em si NÃO está em
        # `npcs_alterados` (não existia no início do laço) e já foi gravado por inteiro
        # dentro de `processar_parto`, então este `UPDATE` nunca o alcança achando uma
        # linha inexistente. NPC morto nunca entra na lista (o `continue` acima pula),
        # então nunca é regravado vivo.
        self._mundo.db.npcs.salvar_muitos(npcs_alterados)
        self._social.processar_interacoes()
        self._atualizar_dependentes()

    def _avancar_relogio(self):
        self._mundo.tick_count += 1
        self._mundo.data_simulada += timedelta(minutes=1)
        hora_formatada = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
        self._mundo.db.meta.salvar(MetaChave.HORA_ISO, self._mundo.data_simulada.isoformat())
        self._mundo.db.meta.salvar(MetaChave.HORA_FORMATADA, hora_formatada)
        WorldLogger.info(f"\n--- Tick {self._mundo.tick_count} | {hora_formatada} ---")

    def _atualizar_eventos_globais(self) -> list:
        self._eventos_globais.atualizar_eventos_globais()
        return self._mundo.db.eventos.carregar_globais_ativos()

    def _executar_rotinas_agendadas(self):
        """Gatilhos baseados no relógio do jogo, disparados uma vez na hora exata
        (minuto 0) — concepção noturna, crescimento, expansão urbana, pensões.

        A06: despacha por `self._rotinas_diarias` (montado no `__init__` a partir da
        cadência que cada mecânica declara) — este método nunca muda pra acrescentar
        uma rotina nova."""
        if self._mundo.data_simulada.minute != 0:
            return
        hora = self._mundo.data_simulada.hour

        for chave_hora, rotina in self._rotinas_diarias:
            if cfg_get(self._cfg_bio, chave_hora) == hora:
                rotina()

    def _aplicar_metabolismo(self, npc: NPC, minutos: int, maes_em_parto: list):
        """Perda/ganho passivo de energia/fome/social, e o consumo extra de gestação —
        função do TEMPO DECORRIDO (`minutos`), não do passo (A01, docs/
        PLANO_POPULACAO_E_ESCALA.md). É exato pra energia/fome/social: a taxa não
        depende do valor atual, então multiplicar por `minutos` e grampear no fim
        (`normalizar_necessidades`) dá o mesmo resultado que dar `minutos` passos de um
        minuto (armadilha 11) — hoje `minutos` é sempre 1 (a agenda de decisões, A02,
        ainda não existe), mas a função já está pronta pra receber saltos maiores.

        O sorteio de fome/social é UM sorteio multiplicado por `minutos`, não `minutos`
        sorteios — reduz a variância de propósito (um salto de 8h não soma 480 ruídos
        independentes), em troca de custar O(1) por salto em vez de O(minutos).

        `num_dependentes` (campo derivado, ver `models.NPC`) NÃO é recalculado aqui —
        `_atualizar_dependentes` (N04) cuida disso, uma vez por tick, só pras casas
        cuja composição de fato mudou."""
        cfg_bio = self._cfg_bio
        meta = self._cfg_metabolismo
        energia_perda = cfg_get(meta, "energia_base_perda") * minutos
        fome_ganho = random.uniform(cfg_get(meta, "fome_base_ganho_min"), cfg_get(meta, "fome_base_ganho_max")) * minutos

        if npc.acao_atual == Acao.DORMIR:
            fome_ganho *= cfg_get(meta, "multiplicador_fome_dormindo")
            energia_perda *= cfg_get(meta, "multiplicador_energia_dormindo")

        if npc.genero == Genero.FEMININO.value and npc.gravidez_ticks > 0:
            energia_perda *= cfg_get(cfg_bio, "gravidez_multiplicador_perda_energia")
            fome_ganho *= cfg_get(cfg_bio, "gravidez_multiplicador_ganho_fome")
            # Cruzamento, não igualdade exata (armadilha 11): um salto de `minutos`
            # pode passar direto por cima de zero em vez de cair exatamente nele.
            gravidez_antes = npc.gravidez_ticks
            npc.gravidez_ticks = max(0, npc.gravidez_ticks - minutos)
            if gravidez_antes > 0 and npc.gravidez_ticks == 0:
                maes_em_parto.append(npc)

        npc.energia -= energia_perda
        npc.fome += fome_ganho
        npc.social -= random.uniform(cfg_get(meta, "social_base_perda_min"), cfg_get(meta, "social_base_perda_max")) * minutos

    def _aplicar_efeito_continuo(self, npc: NPC, minutos: int):
        """A02 (docs/PLANO_POPULACAO_E_ESCALA.md): o efeito, por minuto, de CONTINUAR
        fazendo a ação atual — a parte "linear" (sem estado interno próprio) do que
        `NPCActionManager.executar_acao` faria se rodasse a cada minuto. Só chamado
        para as ações em `agenda.ACOES_LOTEAVEIS` (dormir, trabalhar, ocioso): comer
        (parcelas), construir (integridade até 100%) e cuidar_prole nunca acumulam
        `minutos_extras` > 0 (ver `agenda.calcular_proximo_instante`), então nunca
        passam por aqui — o estado interno delas continua sendo conferido a cada
        minuto de verdade, sem risco de pular por cima de uma transição."""
        cfg_acoes = cfg_get(self._config, "acoes")
        if npc.acao_atual == Acao.DORMIR:
            cfg = cfg_get(cfg_acoes, "dormir")
            npc.energia += cfg_get(cfg, "energia_ganho") * minutos
        elif npc.acao_atual == Acao.TRABALHAR:
            cfg = cfg_get(cfg_acoes, "trabalhar")
            npc.energia -= cfg_get(cfg, "energia_perda") * minutos
            npc.dinheiro_total_pc += cfg_get(cfg, "salario_pc") * minutos
        elif npc.acao_atual == Acao.OCIOSO:
            cfg = cfg_get(cfg_acoes, "ocioso")
            npc.social -= cfg_get(cfg, "social_perda") * minutos

    def _decidir_e_executar(self, npc: NPC, eventos_globais: list, npcs_por_casa: dict):
        acao_anterior = npc.acao_atual
        casa_antes = npc.casa_id
        NPCBrain.decidir_acao(npc, self._mundo.data_simulada.hour, self._config,
                              self._mundo.locais, eventos_globais, self._mundo.indice)

        if npc.casa_id != casa_antes:
            # A04: a rede de segurança de `decidir_acao` (casa_id apontando pra um
            # local que não existe mais) reatribui o campo direto — `NPCBrain` é
            # estático e não tem `EstadoDoMundo` pra passar por `mudar_casa`. Só
            # reindexa (o campo já mudou; `reindexar_casa_do_npc` não muda de novo).
            self._mundo.reindexar_casa_do_npc(npc, casa_antes)

        if npc.acao_atual != acao_anterior:
            WorldLogger.debug(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}", npc=npc)

        self._acoes.executar_acao(npc, npcs_por_casa)

    def _aplicar_consequencias_de_saude(self, npc: NPC):
        cfg_bio = self._cfg_bio
        if npc.fome > cfg_get(cfg_bio, "inaniacao_fome_limiar"):
            npc.saude -= cfg_get(cfg_bio, "inaniacao_perda_saude")
            WorldLogger.warning(f"💔 [INANIÇÃO] {npc.nome} está perdendo saúde! (Saúde: {npc.saude})", npc=npc)
        elif npc.fome < cfg_get(cfg_bio, "recuperacao_sono_fome_maxima") and npc.acao_atual == Acao.DORMIR:
            if npc.saude < ESCALA_MAXIMA:
                npc.saude = min(ESCALA_MAXIMA, npc.saude + cfg_get(cfg_bio, "dormir_ganho_saude"))

    def _remover_falecidos(self):
        """Achado de A04: só reconstrói `mundo.npcs` quando `mundo.ha_falecidos_pendentes`
        está marcado (por `EstadoDoMundo.remover_npc`, chamado de dentro de
        `processar_morte`) — sem essa checagem, esta lista era recriada (um objeto
        NOVO) todo tick mesmo sem morte nenhuma, e `_atualizar_dependentes` (N04)
        interpretava a troca de identidade como "tudo mudou", recalculando o mundo
        inteiro a cada tick (medido: 108 dos 132 ms/tick com 25.000 NPCs)."""
        if not self._mundo.ha_falecidos_pendentes:
            return
        self._mundo.npcs = [n for n in self._mundo.npcs if n.saude > 0]
        self._mundo.ha_falecidos_pendentes = False

    def _podar_eventos_antigos(self):
        """E02 (docs/PLANO_POPULACAO_E_ESCALA.md): varredura diária — apaga da
        tabela `eventos` (não `eventos_globais`) tudo mais velho que
        `simulacao.eventos_retencao_dias_simulados` dias simulados. Com 25.000 NPCs
        são ~245.000 linhas de evento por dia; sem poda a tabela nunca para de
        crescer, e o Modo Mestre só lê os eventos recentes mesmo."""
        cfg_sim = cfg_get(self._config, "simulacao")
        retencao_dias = cfg_get(cfg_sim, "eventos_retencao_dias_simulados")
        dia_de_corte = RelogioMundo.dia_do_mundo(self._mundo.data_simulada) - retencao_dias
        if dia_de_corte <= 0:
            return
        apagadas = self._mundo.db.eventos.podar_por_idade(dia_de_corte)
        if apagadas:
            WorldLogger.info(f"🗑️ [PODA] {apagadas} eventos com mais de {retencao_dias} dias simulados removidos.")

    def _processar_partos(self, maes_em_parto: list):
        for mae in maes_em_parto:
            self._reproducao.processar_parto(mae)

    def _atualizar_dependentes(self):
        """N04 (docs/PLANO_POPULACAO_E_ESCALA.md): `num_dependentes` só é recalculado
        para as casas cuja composição mudou desde a última vez que este método rodou —
        medido em 0,47 s por tick com 25.000 NPCs quando recalculado pra todo mundo.

        Roda no FIM do tick, depois de partos, mortes e (via `processar_interacoes`)
        casamentos — todas as mutações de composição do tick já aconteceram, então o
        retrato de agora já reflete o efeito de todas elas (inclusive um parto neste
        mesmo tick: a mãe ganha o dependente a mais antes deste método terminar, via o
        índice `npcs_por_casa` mantido por `registrar_npc`)."""
        if self._mundo.npcs is not self._ultima_lista_de_npcs:
            # `recarregar_habitantes()` (fora do GameLoop, a cada 5h de jogo) troca
            # `mundo.npcs` por objetos NOVOS, com `num_dependentes` no default 0 — o
            # retrato sozinho não perceberia isso (o conteúdo relevante pode ser
            # idêntico ao de antes), daí forçar recálculo total sempre que a lista em
            # si for outro objeto (A04 já reconstrói os índices nesse caso; aqui só
            # falta este campo derivado).
            self._assinatura_casas_anterior = None

        npcs_por_casa = self._mundo.npcs_por_casa
        assinatura_atual = NPCUtils.assinatura_dependentes_por_casa(npcs_por_casa)
        anterior = self._assinatura_casas_anterior or {}
        for casa_id, assinatura in assinatura_atual.items():
            if anterior.get(casa_id) != assinatura:
                NPCUtils.recalcular_dependentes_da_casa(npcs_por_casa[casa_id])

        self._assinatura_casas_anterior = assinatura_atual
        self._ultima_lista_de_npcs = self._mundo.npcs
