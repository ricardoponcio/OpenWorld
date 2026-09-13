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
        nova_afinidade = n1.relacionamentos.get(n2.id, 0) + mod

        n1.relacionamentos[n2.id] = nova_afinidade
        n2.relacionamentos[n1.id] = nova_afinidade

        # Determinar Vínculo
        vinculo = NPCSocialManager._classificar_vinculo(nova_afinidade, cfg_bio).value

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
