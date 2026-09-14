"""
MODULE: social.py
FUNÇÃO: Gerenciamento de Interações Sociais Gerais.

DESCRIÇÃO:
    Gerencia encontros físicos dinâmicos entre NPCs e calcula os ticks de
    interação ativa do simulador.

    Recebe o mundo e a config, não a engine (R-F01). O gerenciador de casamento entra
    pelo construtor: um teste de interação social pode passar um dublê e medir só a
    afinidade, sem que um romance surpresa altere o resultado.
"""
import time
import random
from ..models import NPC, Acao, Evento, TipoEvento, VinculoSocial
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..tempo import RelogioMundo
from ..mundo import EstadoDoMundo
from .marriage import NPCMarriageManager


class NPCSocialManager:
    # H05 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): cadência diária (A06) — não é o que
    # trava D13 (medido: mediana de relacionamentos/NPC é 0, máximo 14 num dia), mas
    # `npc.relacionamentos` só cresce, nunca decai, e num mundo que roda meses vira
    # memória e custo em `salvar_completo`.
    CADENCIA = "por_dia"
    CADENCIA_HORA_CONFIG = "relacionamentos_poda_hora"

    def __init__(self, mundo: EstadoDoMundo, config: dict, casamento: NPCMarriageManager = None):
        self._mundo = mundo
        self._config = config
        self._casamento = casamento or NPCMarriageManager(mundo, config)

    def processar_interacoes(self):
        """
        Varre todos os locais do mapa à procura de NPCs presentes e gera eventos
        de interação social ativa e romance dinâmico entre eles.

        E01 (docs/PLANO_POPULACAO_E_ESCALA.md): computa todas as interações do tick
        SEM gravar (`_computar_interacao`), e grava eventos/relacionamentos numa
        transação só no final — antes cada interação abria a própria conexão duas
        vezes (evento + relacionamento), ~170 interações/tick com 25.000 NPCs
        (~340 commits/tick medidos).

        H02 (docs/PLANO_AVANCO_E_CALIBRAGEM.md, armadilha 15): usa o índice mantido
        `mundo.npcs_por_localizacao` (A04) em vez de `NPCUtils.
        agrupar_npcs_por_localizacao(mundo.npcs, ...)`, que reconstruía um dicionário
        do zero varrendo os 25.000 NPCs todo tick (~12% do piso medido) pra um
        agrupamento que o índice já mantém incrementalmente. Quem dorme é filtrado
        DENTRO de cada balde (pequeno) — e só pros locais que já passaram do filtro
        `len(moradores) >= 2`, que descarta de cara a maioria (casas com 1 morador)
        sem alocar lista nenhuma pra elas."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        chance_interacao = cfg_get(cfg_bio, "interacao_chance")

        eventos = []
        pares_de_relacionamento = []
        for loc_id, moradores in self._mundo.npcs_por_localizacao.items():
            if len(moradores) < 2:
                continue
            acordados = [n for n in moradores if n.acao_atual != Acao.DORMIR]
            if len(acordados) >= 2 and random.random() < chance_interacao:
                n1, n2 = random.sample(acordados, 2)
                if n1.id != n2.id:
                    evento, par = self._computar_interacao(n1, n2, loc_id)
                    if evento is not None:
                        eventos.append(evento)
                    pares_de_relacionamento.append(par)

        self._mundo.db.eventos.salvar_muitos(eventos)
        self._mundo.db.npcs.salvar_relacionamentos_muitos(pares_de_relacionamento)

        # H02 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): `processar_coabitacao` NÃO é mais
        # chamada daqui — ganhou cadência diária própria (A06) e é despachada por
        # `GameLoop._rotinas_diarias`. As duas chamadas coexistindo casariam o dobro
        # do calibrado (a rotina roda cadenciada E aqui de novo, todo tick).

    def processar_interacao_social(self, n1: NPC, n2: NPC, loc_id: str):
        """Uma interação isolada, gravada IMEDIATAMENTE — uso pontual/teste. O laço de
        `processar_interacoes` usa `_computar_interacao` (mesma regra, sem gravar) e
        escreve em lote (E01)."""
        evento, par = self._computar_interacao(n1, n2, loc_id)
        if evento is not None:
            self._mundo.db.eventos.salvar(evento)
        self._mundo.db.npcs.salvar_relacionamento(*par)
        return evento, par

    def _computar_interacao(self, n1: NPC, n2: NPC, loc_id: str):
        """
        Calcula o efeito de um encontro físico entre dois NPCs em um local — ajusta
        afinidade/relacionamentos EM MEMÓRIA e decide o vínculo RPG, mas NÃO grava
        nada: devolve `(Evento, par_de_relacionamento)` pro chamador gravar (sozinho,
        ou em lote com outras interações do mesmo tick). Também avalia a chance de
        romance físico surpresa — isso continua imediato, é uma decisão de domínio
        (`realizar_casamento`) e não faz parte da escrita que E01 agrupa.
        """
        local_nome = self._mundo.locais[loc_id].nome if loc_id in self._mundo.locais else loc_id

        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        ganhos = cfg_get(cfg_bio, "interacao_afinidade_ganhos")
        mod = random.choice(ganhos)
        afinidade_antiga = n1.relacionamentos.get(n2.id, 0)
        nova_afinidade = afinidade_antiga + mod

        n1.relacionamentos[n2.id] = nova_afinidade
        n2.relacionamentos[n1.id] = nova_afinidade

        # Determinar Vínculo
        vinculo_antigo = NPCSocialManager._classificar_vinculo(afinidade_antiga, cfg_bio)
        vinculo_novo = NPCSocialManager._classificar_vinculo(nova_afinidade, cfg_bio)
        vinculo = vinculo_novo.value

        # M02 (docs/PLANO_MUNDO_CRIVEL.md, Bloco M): só vira LINHA NO BANCO se o
        # vínculo mudou de FAIXA — com `interacao_chance=0,0452`, 5.758 eventos/dia
        # (840 NPCs) eram 99,1% "tiveram uma conversa", ruído que enterrava os 10
        # últimos fatos de `resumos_recentes` embaixo de fofoca. A afinidade em
        # memória (acima) e o par de relacionamento (abaixo, sempre devolvido)
        # continuam ajustando a cada interação — só o EVENTO fica condicional.
        evento = None
        if vinculo_novo != vinculo_antigo:
            tipo = "CONVERSA" if mod >= 0 else "DISCUSSAO"
            resumo = f"{n1.nome} e {n2.nome} tiveram uma {tipo} em {local_nome}."
            timestamp_rpg = RelogioMundo.timestamp_rpg(self._mundo.data_simulada)
            evento = Evento(f"evt_{int(time.time())}_{random.randint(0,999)}",
                            timestamp_rpg, loc_id, [n1.id, n2.id], tipo, mod, resumo)
            WorldLogger.debug(f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})", npc=n1)
            WorldLogger.queue_db_log(n2, "DEBUG", f"  >> EVENTO: {resumo} (Afinidade: {nova_afinidade} | {vinculo})")

        # --- ROMANCE FÍSICO: Decisão de coabitação durante conversa real ---
        # Carrega a chance de romance surpresa físico de forma configurável
        chance_romance = cfg_get(cfg_bio, "casamento_chance_romance_fisico")

        if self._casamento.verificar_elegibilidade_casamento(n1, n2, nova_afinidade):
            if random.random() < chance_romance:
                casa_escolhida = n1.casa_id or n2.casa_id
                if casa_escolhida:
                    # Realizar casamento completo e atômico no gerenciador de casamentos
                    self._casamento.realizar_casamento(n1, n2, casa_escolhida, surpresa=True)

        return evento, (n1.id, n2.id, nova_afinidade, vinculo)

    def processar_poda_de_relacionamentos(self):
        """H05 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): decai afinidades não protegidas
        em direção a zero (esquecendo quem não foi reencontrado) e, se ainda assim
        passar do teto (`relacionamentos_max_por_npc`, número de Dunbar), descarta
        as mais fracas primeiro. NUNCA descarta/decai cônjuge, pais, filhos, ou quem
        tiver vínculo forte (`afinidade >= vinculo_limiar_amigo`) — uma pessoa
        esquece um conhecido de taverna, não a própria irmã."""
        cfg_sim = cfg_get(self._config, "simulacao")
        teto = cfg_get(cfg_sim, "relacionamentos_max_por_npc")
        decaimento = cfg_get(cfg_sim, "relacionamentos_decaimento_por_dia")
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        limiar_forte = cfg_get(cfg_bio, "vinculo_limiar_amigo")

        id_para_npc = {n.id: n for n in self._mundo.npcs if n.esta_vivo()}
        mudados = []
        for npc in self._mundo.npcs:
            if not npc.esta_vivo() or not npc.relacionamentos:
                continue
            protegidos = self._ids_protegidos(npc, id_para_npc)
            if self._decair_e_podar(npc, protegidos, limiar_forte, decaimento, teto):
                mudados.append(npc)

        if mudados:
            self._mundo.db.npcs.salvar_completo(mudados)

    @staticmethod
    def _ids_protegidos(npc: NPC, id_para_npc: dict) -> set:
        """Cônjuge, pais (já estão no próprio NPC) e filhos (só descobertos olhando
        o `mae_id`/`pai_id` de quem está do outro lado da relação — por isso precisa
        de `id_para_npc`, não dá pra saber só com o `npc.relacionamentos` dele)."""
        protegidos = set()
        for chave in (npc.conjuge_id, npc.mae_id, npc.pai_id):
            if chave:
                protegidos.add(chave)
        for outro_id in npc.relacionamentos:
            outro = id_para_npc.get(outro_id)
            if outro and (outro.mae_id == npc.id or outro.pai_id == npc.id):
                protegidos.add(outro_id)
        return protegidos

    @staticmethod
    def _decair_e_podar(npc: NPC, protegidos: set, limiar_forte: float,
                         decaimento: float, teto: int) -> bool:
        mudou = False
        for outro_id in list(npc.relacionamentos):
            afinidade = npc.relacionamentos[outro_id]
            if outro_id in protegidos or afinidade >= limiar_forte:
                continue
            if afinidade > 0:
                nova = afinidade - decaimento
            elif afinidade < 0:
                nova = afinidade + decaimento
            else:
                nova = 0
            if (afinidade > 0 and nova <= 0) or (afinidade < 0 and nova >= 0) or afinidade == 0:
                del npc.relacionamentos[outro_id]
            else:
                npc.relacionamentos[outro_id] = nova
            mudou = True

        excedente = len(npc.relacionamentos) - teto
        if excedente > 0:
            podaveis = sorted(
                (oid for oid in npc.relacionamentos
                 if oid not in protegidos and npc.relacionamentos[oid] < limiar_forte),
                key=lambda oid: abs(npc.relacionamentos[oid]))
            for oid in podaveis[:excedente]:
                del npc.relacionamentos[oid]
                mudou = True

        return mudou

    @staticmethod
    def _classificar_vinculo(afinidade: float, cfg_bio: dict) -> VinculoSocial:
        """Classifica o vínculo pela afinidade acumulada. Testa os limiares negativos
        do mais extremo pro menos extremo (R-B01) — a ordem inversa deixava INIMIGO
        inalcançável: qualquer afinidade abaixo de -50 já satisfazia '< limiar_rival'
        (-20) primeiro e nunca chegava a checar '< limiar_inimigo'."""
        if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_aliado"):
            return VinculoSocial.ALIADO
        if afinidade >= cfg_get(cfg_bio, "vinculo_limiar_amigo"):
            return VinculoSocial.AMIGO
        if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_inimigo"):
            return VinculoSocial.INIMIGO
        if afinidade <= cfg_get(cfg_bio, "vinculo_limiar_rival"):
            return VinculoSocial.RIVAL
        return VinculoSocial.CONHECIDO
