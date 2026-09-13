"""
MODULE: marriage.py
FUNÇÃO: Gerenciamento de Casamento e Coabitação.

DESCRIÇÃO:
    Gerencia as uniões matrimoniais do simulador, incluindo verificação de
    critérios de elegibilidade biológica/social, formalização atômica do
    casamento no RPG, e a rotina cron de casamentos passivos.
"""
import time
import random
from ..models import NPC, Evento, TipoEvento, EstadoCivil, VinculoSocial
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

    H02 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): `CADENCIA`/`CADENCIA_HORA_CONFIG` (A06)
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
        """
        # Critérios Biológicos e de Sobrevivência
        if not n1.esta_vivo() or not n1.pode_procriar():
            return False
        if not n2.esta_vivo() or not n2.pode_procriar():
            return False

        # Impedir uniões do mesmo gênero ou que já morem juntos
        if n1.genero == n2.genero or n1.casa_id == n2.casa_id:
            return False

        # Ambos devem ser solteiros
        if NPCUtils.tem_conjuge(n1) or NPCUtils.tem_conjuge(n2):
            return False

        # Evitar casamentos incestuosos
        if NPCUtils.sao_parentes(n1, n2):
            return False

        # Verificar afinidade mínima requerida
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        limiar_uniao = cfg_get(cfg_bio, "concepcao_afinidade_minima")
        if afinidade < limiar_uniao:
            return False

        return True

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

        # Verificar se a casa de destino está cheia
        casa_obj = self._mundo.locais.get(casa_escolhida)
        casa_cheia = NPCUtils.is_casa_superlotada(self._mundo.locais, self._mundo.npcs, casa_escolhida)

        teve_nova_casa = False
        if casa_cheia:
            # 1. Procurar uma casa totalmente vazia na cidade
            casas_vazias = NPCUtils.obter_casas_vazias(self._mundo, n1.cidade_id, ignorar_id=casa_escolhida)

            if casas_vazias:
                casa_alvo = random.choice(casas_vazias)
                
                self._mundo.mudar_casa(n1, casa_alvo.id)
                self._mundo.mover_npc(n1, casa_alvo.id)
                self._mundo.mudar_casa(n2, casa_alvo.id)
                self._mundo.mover_npc(n2, casa_alvo.id)
                casa_escolhida = casa_alvo.id
                teve_nova_casa = True
                casa_obj = casa_alvo # Atualiza para o log abaixo
                
                prefixo = "SURPRESA" if surpresa else "PLANEJADO"
                WorldLogger.evento_mundo(
                    f"🏠 [NOVO LAR {prefixo}] Recém-casados {n1.nome} e {n2.nome} mudaram-se para {casa_alvo.nome} que tinha espaço disponível!",
                    npc=n1
                )
            else:
                # 2. Se não tem casa com espaço, tenta construir uma nova obra
                if self._habitacao.iniciar_obra_para_casal(n1, n2):
                    teve_nova_casa = True
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
            id=f"evt_uniao_{int(time.time())}_{random.randint(0,999)}",
            timestamp=timestamp_rpg,
            local_id=casa_escolhida,
            envolvidos=[n1.id, n2.id],
            tipo_evento=TipoEvento.CONVERSA.value,
            modificador_afinidade=bonus_afinidade,
            resumo_estruturado=resumo
        )
        self._mundo.db.eventos.salvar(evento)

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
        # PLANO_CIDADE_VIVA.md: mesmo raciocínio de "NPC não atravessa o mundo pra ir
        # à taverna").
        solteiros_por_cidade = {}
        for n in self._mundo.npcs:
            if n.esta_vivo() and not NPCUtils.tem_conjuge(n):
                solteiros_por_cidade.setdefault(n.cidade_id, []).append(n)

        # N01 (docs/PLANO_POPULACAO_E_ESCALA.md): um casamento exige afinidade
        # acumulada, e afinidade só existe entre quem já se encontrou —
        # `n1.relacionamentos` já é exatamente esse conjunto, e é pequeno. Percorrê-lo
        # em vez da cidade inteira troca O(N²) por O(N × conhecidos).
        for solteiros in solteiros_por_cidade.values():
            indice_solteiros = {n.id: n for n in solteiros}
            ordem = list(solteiros)
            # O laço termina no primeiro casamento — sem embaralhar, o primeiro
            # solteiro da lista teria prioridade permanente sobre todos os outros.
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

                                # Retorna para evitar processar mais de uma união no mesmo tick
                                return
