"""
MODULE: marriage.py
FUNÇÃO: Gerenciamento de Casamento e Coabitação.

DESCRIÇÃO:
    Gerencia as uniões matrimoniais do simulador, incluindo verificação de
    critérios de elegibilidade biológica/social, formalização atômica do
    casamento no RPG, e a rotina cron de casamentos passivos.
"""
import random
from ..models import NPC, Evento, TipoEvento, EstadoCivil, VinculoSocial, ContadorMundo
from ..identificadores import PrefixoId, novo_id
from ..tempo import RelogioMundo
from ..logger import WorldLogger
from ..consultas_npc import NPCUtils
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo
from .housing import NPCHousingManager


class NPCMarriageManager:
    """Uniões matrimoniais e coabitação. Recebe o mundo e a config, não a engine
    (R-F01). O gerenciador de habitação é colaborador de domínio e entra pelo
    construtor para que um teste possa substituí-lo por um dublê e verificar a união
    sem disparar obra nenhuma.

    H02 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): `CADENCIA`/`CADENCIA_HORA_CONFIG` (A06)
    — `processar_coabitacao` deixou de ser chamada a cada tick (de dentro de
    `NPCSocialManager.processar_interacoes`, ~46% do piso medido) e passou a ser uma
    rotina diária despachada por `GameLoop`, como as outras cinco mecânicas já são.
    Casamento planejado não é um evento de minuto."""
    CADENCIA = "por_dia"
    CADENCIA_HORA_CONFIG = "casamento_hora"

    def __init__(self, mundo: EstadoDoMundo, config: dict, habitacao: NPCHousingManager = None):
        self._mundo = mundo
        self._config = config
        self._habitacao = habitacao or NPCHousingManager(mundo, config)

    def verificar_elegibilidade_casamento(self, n1: NPC, n2: NPC, afinidade: int) -> bool:
        """
        Verifica se dois NPCs atendem a todos os critérios biológicos, sociais
        e morais para serem elegíveis ao casamento.

        G02 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco G): a parte biológica (vivo, fértil,
        não-parente, afinidade mínima) é `NPCUtils.pode_conceber` — a MESMA checagem
        que `processar_concepcao` usa, pro mesmo motivo não divergir duas vezes
        (armadilha 12)."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        if not NPCUtils.pode_conceber(n1, n2, afinidade, cfg_bio):
            return False

        # Impedir uniões do mesmo gênero ou que já morem juntos
        if n1.genero == n2.genero or n1.casa_id == n2.casa_id:
            return False

        # Ambos devem ser solteiros
        if NPCUtils.tem_conjuge(n1) or NPCUtils.tem_conjuge(n2):
            return False

        return True

    def _filhos_para_mudar(self, pai_ou_mae: NPC, casa_origem: str, casa_destino: str) -> list:
        """G04 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco G): dependentes de `pai_ou_mae`
        que ficariam sozinhos na casa de origem se ele/ela se mudar sem eles — sem
        isto, o bebê ficava na casa antiga, virando o próprio pagador da refeição
        com 0 PC (§5.2 do documento, 10 casos num mundo real de 25 dias). Vazio se
        não muda de casa (`casa_origem == casa_destino`) ou não tinha casa."""
        if not casa_origem or casa_origem == casa_destino:
            return []
        # D02 (docs/16_PLANO_PAINEL_E_IA.md, armadilha 18 — o gêmeo): usava
        # `NPCUtils.obter_moradores_da_casa(self._mundo.npcs, ...)`, que varre
        # mundo.npcs inteiro pra achar quem mora numa casa. Índice já mantido
        # (A04), mesmo padrão que os vizinhos deste arquivo já usam (X04).
        moradores = self._mundo.npcs_por_casa.get(casa_origem, ())
        return [m for m in moradores if m.id != pai_ou_mae.id and m.eh_dependente()
                and (m.mae_id == pai_ou_mae.id or m.pai_id == pai_ou_mae.id)]

    def _ocupacao_apos_casamento(self, casa_destino: str, n1: NPC, n2: NPC, filhos: list) -> int:
        """G04: quantos moradores vivos a casa de destino teria DEPOIS do casamento
        — residentes atuais (exceto o próprio casal, que pode já morar lá) mais o
        casal e os filhos que vêm junto. Precisa contar os filhos ANTES de decidir
        se a casa está cheia — senão o destino parece ter espaço que some assim que
        a família chega inteira."""
        # D02 (docs/16_PLANO_PAINEL_E_IA.md, armadilha 18 - o mesmo gemeo de cima).
        atuais = self._mundo.npcs_por_casa.get(casa_destino, ())
        ids_exceto_casal = {m.id for m in atuais} - {n1.id, n2.id}
        return len(ids_exceto_casal) + 2 + len(filhos)

    def realizar_casamento(self, n1: NPC, n2: NPC, casa_escolhida: str, surpresa: bool = False) -> bool:
        """
        Formaliza o casamento entre dois NPCs, gerencia a alocação de sua moradia,
        registra o evento no universo do jogo e ajusta sua afinidade.
        """
        # Formalizar casamento
        n1.estado_civil = EstadoCivil.CASADO.value
        n1.conjuge_id = n2.id
        n2.estado_civil = EstadoCivil.CASADO.value
        n2.conjuge_id = n1.id

        # G04: quem vai casa de origem de cada um, capturado ANTES de qualquer
        # mudança — depois de mudar_casa, `n.casa_id` já é o destino.
        casa_origem_n1, casa_origem_n2 = n1.casa_id, n2.casa_id
        filhos_n1 = self._filhos_para_mudar(n1, casa_origem_n1, casa_escolhida)
        filhos_n2 = self._filhos_para_mudar(n2, casa_origem_n2, casa_escolhida)

        # Verificar se a casa de destino ficaria cheia — DEPOIS de contar os
        # filhos que vêm junto, não antes (G04).
        casa_obj = self._mundo.locais.get(casa_escolhida)
        capacidade = casa_obj.capacidade if casa_obj else 0
        casa_cheia = self._ocupacao_apos_casamento(casa_escolhida, n1, n2, filhos_n1 + filhos_n2) > capacidade

        teve_nova_casa = False
        casa_final = casa_escolhida
        if casa_cheia:
            # 1. Procurar uma casa totalmente vazia na cidade
            casas_vazias = NPCUtils.obter_casas_vazias(self._mundo, n1.cidade_id, ignorar_id=casa_escolhida)

            if casas_vazias:
                casa_alvo = random.choice(casas_vazias)
                casa_final = casa_alvo.id
                teve_nova_casa = True
                casa_obj = casa_alvo # Atualiza para o log abaixo
                # Casa vazia — recalcula quem vem junto (a origem não é mais
                # `casa_escolhida`, é a casa vazia nova, então TODOS os filhos de
                # cada origem original vêm, sem exceção).
                filhos_n1 = self._filhos_para_mudar(n1, casa_origem_n1, casa_final)
                filhos_n2 = self._filhos_para_mudar(n2, casa_origem_n2, casa_final)

                prefixo = "SURPRESA" if surpresa else "PLANEJADO"
                WorldLogger.evento_mundo(
                    f"🏠 [NOVO LAR {prefixo}] Recém-casados {n1.nome} e {n2.nome} mudaram-se para {casa_alvo.nome} que tinha espaço disponível!",
                    npc=n1
                )
            else:
                # 2. Se não tem casa com espaço, tenta construir uma nova obra —
                # ninguém se muda ainda (mora onde já está até a obra terminar),
                # então nenhum filho muda de casa nesta rodada.
                if self._habitacao.iniciar_obra_para_casal(n1, n2):
                    teve_nova_casa = True
                    casa_final = None
                    filhos_n1, filhos_n2 = [], []
                    prefixo = "SURPRESA" if surpresa else "PLANEJADO"
                    WorldLogger.evento_mundo(
                        f"🏗️ [NOVO LAR {prefixo}] Recém-casados {n1.nome} e {n2.nome} iniciaram a "
                        f"construção de sua própria casa por falta de espaço na moradia dos pais!",
                        npc=n1
                    )

        if not teve_nova_casa:
            # Se a casa tem espaço (ou se falhou a alocação e não achou vazia), moram juntos na casa escolhida
            self._mundo.mudar_casa(n1, casa_escolhida)
            self._mundo.mover_npc(n1, casa_escolhida)
            self._mundo.mudar_casa(n2, casa_escolhida)
            self._mundo.mover_npc(n2, casa_escolhida)
        elif casa_final:
            self._mundo.mudar_casa(n1, casa_final)
            self._mundo.mover_npc(n1, casa_final)
            self._mundo.mudar_casa(n2, casa_final)
            self._mundo.mover_npc(n2, casa_final)

        # G04: os filhos vão junto — pelas mesmas portas (`mudar_casa`/`mover_npc`),
        # nunca atribuição direta (os índices desincronizam em silêncio).
        if casa_final:
            for filho in filhos_n1 + filhos_n2:
                self._mundo.mudar_casa(filho, casa_final)
                self._mundo.mover_npc(filho, casa_final)
                self._mundo.db.npcs.salvar(filho)
                self._mundo.acordar(filho)
            casa_escolhida = casa_final

        # Salvar NPCs no banco
        self._mundo.db.npcs.salvar(n1)
        self._mundo.db.npcs.salvar(n2)
        # A03: casamento (e possível mudança de casa) muda o que os dois querem —
        # reavaliar agora, sem esperar o próximo instante que a agenda (A02) já
        # tivesse calculado pra eles antes de casarem.
        self._mundo.acordar(n1)
        self._mundo.acordar(n2)

        # Registrar Evento de União no RPG
        timestamp_rpg = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
        nome_casa = casa_obj.nome if casa_obj else "uma nova moradia"

        if surpresa:
            resumo = f"💍 CASAMENTO SURPRESA! {n1.nome} e {n2.nome} apaixonaram-se tanto durante a conversa que se casaram e vão morar juntos em {nome_casa}!"
            bonus_afinidade = 50
        else:
            resumo = f"💍 Casamento! {n1.nome} e {n2.nome} trocaram votos e decidiram morar juntos em {nome_casa}."
            bonus_afinidade = 30

        evento = Evento(
            id=novo_id(PrefixoId.EVENTO_UNIAO),
            timestamp=timestamp_rpg,
            local_id=casa_escolhida,
            envolvidos=[n1.id, n2.id],
            tipo_evento=TipoEvento.UNIAO.value,
            modificador_afinidade=bonus_afinidade,
            resumo_estruturado=resumo
        )
        self._mundo.db.eventos.salvar(evento)
        self._mundo.contar(ContadorMundo.CASAMENTO)  # O02 (docs/16_PLANO_PAINEL_E_IA.md)

        # Aumentar afinidade e salvar o relacionamento no banco
        n1.relacionamentos[n2.id] = min(1000, n1.relacionamentos.get(n2.id, 0) + bonus_afinidade)
        n2.relacionamentos[n1.id] = min(1000, n2.relacionamentos.get(n1.id, 0) + bonus_afinidade)
        self._mundo.db.npcs.salvar_relacionamento(n1.id, n2.id, n1.relacionamentos[n2.id], VinculoSocial.ALIADO.value)

        # Emitir logs oficiais do simulador
        WorldLogger.evento_mundo(f"❤️ [UNIÃO] {resumo}", npc=n1)
        WorldLogger.queue_db_log(n2, "INFO", f"❤️ [UNIÃO] {resumo}")  # A07: evento_mundo já grava n1; n2 só precisa do registro no banco

        return teve_nova_casa

    def processar_coabitacao(self):
        """
        Executa a rotina periódica (offline/background) de casamentos planejados e coabitação.
        
        Essa rotina varre o banco de dados de NPCs solteiros em busca de casais de alta 
        afinidade acumulada que atendam a todas as restrições biológicas e sociais de união. 
        Ao encontrar um par elegível, há uma chance aleatória de eles formalizarem a união,
        se mudarem para o mesmo lar e, caso a moradia de destino esteja cheia, iniciarem a 
        construção de uma residência independente para aliviar a superlotação.
        """
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        # Carrega a chance de casamento passivo de forma configurável
        chance_uniao = cfg_get(cfg_bio, "casamento_chance_coabitacao")

        # Filtra apenas NPCs solteiros ativos (vivos), agrupados por CIDADE — casar
        # gente de cidades diferentes nunca fez sentido (P03/P04, docs/
        # 12_PLANO_CIDADE_VIVA.md: mesmo raciocínio de "NPC não atravessa o mundo pra ir
        # à taverna").
        solteiros_por_cidade = {}
        for n in self._mundo.npcs:
            if n.esta_vivo() and not NPCUtils.tem_conjuge(n):
                solteiros_por_cidade.setdefault(n.cidade_id, []).append(n)

        # N01 (docs/13_PLANO_POPULACAO_E_ESCALA.md): um casamento exige afinidade
        # acumulada, e afinidade só existe entre quem já se encontrou —
        # `n1.relacionamentos` já é exatamente esse conjunto, e é pequeno. Percorrê-lo
        # em vez da cidade inteira troca O(N²) por O(N × conhecidos).
        # G03 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco G): no máximo UM casamento
        # planejado por CIDADE por dia — cada cidade processada independente das
        # outras (antes desta tarefa, um `return` saía do método inteiro no
        # primeiro casamento de QUALQUER cidade: bug herdado de quando a rotina
        # rodava por tick, não design — desde H02 (doc 3) mudou a cadência pra
        # diária, isso tinha virado "1 casamento no mundo inteiro por dia").
        for solteiros in solteiros_por_cidade.values():
            self._tentar_casamento_na_cidade(solteiros, chance_uniao)

    def _tentar_casamento_na_cidade(self, solteiros: list, chance_uniao: float) -> bool:
        """A varredura de uma única cidade — para no primeiro casal que casar
        (`break` da própria cidade, não do mundo). Devolve True se casou alguém."""
        indice_solteiros = {n.id: n for n in solteiros}
        ordem = list(solteiros)
        # Sem embaralhar, o primeiro solteiro da lista teria prioridade permanente
        # sobre todos os outros.
        random.shuffle(ordem)
        for n1 in ordem:
            for id_conhecido, afinidade in n1.relacionamentos.items():
                n2 = indice_solteiros.get(id_conhecido)
                if n2 is None:
                    continue

                # A validação biológica completa e de consanguinidade é delegada à função central
                if self.verificar_elegibilidade_casamento(n1, n2, afinidade):
                    if random.random() < chance_uniao:
                        casa_escolhida = n1.casa_id or n2.casa_id
                        if casa_escolhida:
                            # Realizar casamento completo e atômico
                            self.realizar_casamento(n1, n2, casa_escolhida, surpresa=False)
                            return True
        return False
