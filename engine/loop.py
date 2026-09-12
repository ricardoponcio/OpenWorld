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
from .mechanics.kingdom import KingdomManager
from .mechanics.social import NPCSocialManager
from .mechanics.events import GlobalEventManager
from .mechanics.mood import NPCMoodManager


class GameLoop:
    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config

        self._acoes = NPCActionManager(mundo, config)
        self._reproducao = NPCReproductionManager(mundo, config)
        self._ciclo_de_vida = NPCLifecycleManager(mundo, config)
        self._habitacao = NPCHousingManager(mundo, config)
        self._reino = KingdomManager(mundo, config)
        self._social = NPCSocialManager(mundo, config)
        self._eventos_globais = GlobalEventManager(mundo)
        self._humor = NPCMoodManager(config)

    def executar_tick(self):
        """Executa um tick completo da simulação social, biológica e econômica do reino."""
        self._avancar_relogio()
        eventos_globais = self._atualizar_eventos_globais()
        self._executar_rotinas_agendadas()

        maes_em_parto = []
        for npc in self._mundo.npcs:
            if not npc.esta_vivo():
                continue

            self._aplicar_metabolismo(npc, maes_em_parto)
            self._decidir_e_executar(npc, eventos_globais)
            self._aplicar_consequencias_de_saude(npc)
            npc.normalizar_necessidades()
            self._humor.processar_humor(npc)

            if npc.saude <= 0:
                self._ciclo_de_vida.processar_morte(npc)
                continue
            self._mundo.db.npcs.salvar(npc)

        self._remover_falecidos()
        self._processar_partos(maes_em_parto)
        self._social.processar_interacoes()

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
        (minuto 0) — concepção noturna, crescimento, expansão urbana, pensões."""
        if self._mundo.data_simulada.minute != 0:
            return
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        hora = self._mundo.data_simulada.hour

        if hora == cfg_get(cfg_bio, "concepcao_hora"):
            self._reproducao.processar_concepcao()
        if hora == cfg_get(cfg_bio, "crescimento_hora"):
            self._ciclo_de_vida.processar_crescimento()
        if hora == cfg_get(cfg_bio, "habitacao_hora"):
            self._habitacao.processar_habitacao()
        if hora == cfg_get(cfg_bio, "pagamento_reino_hora"):
            self._reino.processar_pagamentos_reino()

    def _aplicar_metabolismo(self, npc: NPC, maes_em_parto: list):
        """Perda/ganho passivo de energia/fome/social, e o consumo extra de gestação.
        Também recalcula `num_dependentes` (campo derivado, ver `models.NPC`)."""
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        meta = cfg_get(self._config, "metabolismo")
        energia_perda = cfg_get(meta, "energia_base_perda")
        fome_ganho = random.uniform(cfg_get(meta, "fome_base_ganho_min"), cfg_get(meta, "fome_base_ganho_max"))

        if npc.acao_atual == Acao.DORMIR:
            fome_ganho *= cfg_get(meta, "multiplicador_fome_dormindo")
            energia_perda *= cfg_get(meta, "multiplicador_energia_dormindo")

        if npc.genero == Genero.FEMININO.value and npc.gravidez_ticks > 0:
            energia_perda *= cfg_get(cfg_bio, "gravidez_multiplicador_perda_energia")
            fome_ganho *= cfg_get(cfg_bio, "gravidez_multiplicador_ganho_fome")
            npc.gravidez_ticks -= 1
            if npc.gravidez_ticks == 0:
                maes_em_parto.append(npc)

        npc.energia -= energia_perda
        npc.fome += fome_ganho
        npc.social -= random.uniform(cfg_get(meta, "social_base_perda_min"), cfg_get(meta, "social_base_perda_max"))

        npc.num_dependentes = NPCUtils.contar_dependentes_na_casa(self._mundo.npcs, npc)

    def _decidir_e_executar(self, npc: NPC, eventos_globais: list):
        acao_anterior = npc.acao_atual
        NPCBrain.decidir_acao(npc, self._mundo.data_simulada.hour, self._config,
                              self._mundo.locais, eventos_globais)

        if npc.acao_atual != acao_anterior:
            WorldLogger.debug(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}", npc=npc)

        self._acoes.executar_acao(npc)

    def _aplicar_consequencias_de_saude(self, npc: NPC):
        cfg_bio = cfg_get(self._config, "biologia_e_sociedade")
        if npc.fome > cfg_get(cfg_bio, "inaniacao_fome_limiar"):
            npc.saude -= cfg_get(cfg_bio, "inaniacao_perda_saude")
            WorldLogger.warning(f"💔 [INANIÇÃO] {npc.nome} está perdendo saúde! (Saúde: {npc.saude})", npc=npc)
        elif npc.fome < cfg_get(cfg_bio, "recuperacao_sono_fome_maxima") and npc.acao_atual == Acao.DORMIR:
            if npc.saude < ESCALA_MAXIMA:
                npc.saude = min(ESCALA_MAXIMA, npc.saude + cfg_get(cfg_bio, "dormir_ganho_saude"))

    def _remover_falecidos(self):
        self._mundo.npcs = [n for n in self._mundo.npcs if n.saude > 0]

    def _processar_partos(self, maes_em_parto: list):
        for mae in maes_em_parto:
            self._reproducao.processar_parto(mae)
