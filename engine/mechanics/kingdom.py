"""
MODULE: kingdom.py
FUNÇÃO: Políticas sociais do reino (pensão por idade e sopão comunitário).

DESCRIÇÃO:
    Recebe o mundo e a config, não a engine (R-F01): precisa da lista de NPCs, do
    contador de ticks (para a amostragem de log) e dos parâmetros do bloco `reino`.
"""
from ..models import NPC, EstagioVida
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..mundo import EstadoDoMundo


class KingdomManager:
    """A06 (docs/13_PLANO_POPULACAO_E_ESCALA.md): cadência declarada pela própria
    mecânica — a hora vem de `biologia_e_sociedade.pagamento_reino_hora`, não de um
    bloco `reino` próprio (histórico, não vale a pena mover só por isto)."""
    CADENCIA = "por_dia"
    CADENCIA_HORA_CONFIG = "pagamento_reino_hora"

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config
        # N04 (docs/15_PLANO_MUNDO_CRIVEL.md, Bloco N): `dict[cidade_id] -> rações de
        # sopão restantes HOJE` — zerado 1x/dia em `processar_pagamentos_reino`,
        # decrementado só dentro de `fornecer_sopao` (que só roda quando um NPC
        # tenta comer sem dinheiro). Nenhuma varredura extra por tick.
        self._racoes_sopao_restantes = {}

    def processar_pagamentos_reino(self):
        """Varredura diária (ex: 08:00) para pagar aposentadorias do reino aos idosos
        E reabastecer a cota diária de sopão (N04) — a MESMA passada pelos NPCs vivos
        serve às duas coisas (população por cidade sai de graça de quem já paga
        pensão), sem laço extra."""
        cfg_reino = cfg_get(self._config, "reino")
        pensao_diaria = cfg_get(cfg_reino, "pensao_aposentadoria")
        racoes_por_habitante = cfg_get(cfg_reino, "sopao_racoes_por_habitante_dia")

        pagos = 0
        populacao_por_cidade = {}
        for npc in self._mundo.npcs:
            if not npc.esta_vivo():
                continue
            populacao_por_cidade[npc.cidade_id] = populacao_por_cidade.get(npc.cidade_id, 0) + 1
            if npc.is_idoso():
                npc.dinheiro_total_pc += pensao_diaria
                pagos += 1

        self._racoes_sopao_restantes = {
            cidade_id: racoes_por_habitante * populacao
            for cidade_id, populacao in populacao_por_cidade.items()
        }

        if pagos > 0:
            WorldLogger.info(f"👑 [REINO] O Rei pagou aposentadoria de {pensao_diaria} PC para {pagos} anciões da vila.")

    def fornecer_sopao(self, npc: NPC, fome_rec_do_tick: float, energia_ganho_do_tick: float):
        """Fornece alimento gratuito para cidadãos na miséria — até a cota diária da
        cidade (N04) acabar. Sem cota restante, devolve `False` e a inanição
        acontece de verdade (decisão ❶: é o objetivo)."""
        cfg_reino = cfg_get(self._config, "reino")
        if not cfg_get(cfg_reino, "fornecer_sopao"):
            return False

        # Permitir sopão se o NPC for idoso OU se estiver em extrema miséria e fome sem dinheiro
        limiar_miseria = cfg_get(cfg_reino, "sopao_fome_limiar_miseria")
        fator = cfg_get(cfg_reino, "sopao_fator_potencia")
        extremamente_pobre = npc.dinheiro_total_pc <= 0 and npc.fome > limiar_miseria
        if not npc.is_idoso() and not extremamente_pobre:
            return False

        restante = self._racoes_sopao_restantes.get(npc.cidade_id, 0.0)
        if restante <= 0:
            return False
        self._racoes_sopao_restantes[npc.cidade_id] = restante - 1

        npc.fome -= (fome_rec_do_tick * fator)  # Sopão alimenta menos que refeição paga
        npc.energia += (energia_ganho_do_tick * fator)

        if WorldLogger.deve_logar_amostra(self._mundo.tick_count, self._config):
            WorldLogger.info(f"🍲 [SOPÃO COMUNITÁRIO] O reino forneceu um sopão para {npc.nome}, evitando a inanição.", npc=npc)
        return True
