"""
MODULE: loop.py
FUNÇÃO: Motor do Ciclo de Simulação (GameLoop).

DESCRIÇÃO:
    Orquestra cada tick: avança o relógio, atualiza eventos globais, dispara rotinas
    agendadas por hora, e processa cada NPC vivo (metabolismo, decisão, ação,
    consequências de saúde, humor, morte). `GameLoop` só orquestra — a regra de cada
    etapa mora no gerenciador especializado (R-D02: antes um único método de 123 linhas
    fazia tudo isso inline).
"""
import random
from datetime import timedelta
from .models import NPC, Acao, Genero, MetaChave, ESCALA_MAXIMA
from .logger import WorldLogger
from .consultas_npc import NPCUtils
from .config_loader import cfg_get
from .tempo import RelogioMundo
from .mechanics import NPCBrain, NPCActionManager
from .mechanics.reproduction import NPCReproductionManager
from .mechanics.lifecycle import NPCLifecycleManager
from .mechanics.housing import NPCHousingManager
from .mechanics.kingdom import KingdomManager
from .mechanics.social import NPCSocialManager
from .mechanics.events import GlobalEventManager
from .mechanics.mood import NPCMoodManager


class GameLoop:
    @staticmethod
    def executar_tick(engine):
        """Executa um tick completo da simulação social, biológica e econômica do reino."""
        GameLoop._avancar_relogio(engine)
        eventos_globais = GameLoop._atualizar_eventos_globais(engine)
        GameLoop._executar_rotinas_agendadas(engine)

        maes_em_parto = []
        for npc in engine.npcs:
            if not npc.esta_vivo():
                continue

            GameLoop._aplicar_metabolismo(engine, npc, maes_em_parto)
            GameLoop._decidir_e_executar(engine, npc, eventos_globais)
            GameLoop._aplicar_consequencias_de_saude(engine, npc)
            npc.normalizar_necessidades()
            NPCMoodManager.processar_humor(engine, npc)

            if npc.saude <= 0:
                NPCLifecycleManager.processar_morte(engine, npc)
                continue
            engine.db.salvar_npc(npc)

        GameLoop._remover_falecidos(engine)
        GameLoop._processar_partos(engine, maes_em_parto)
        NPCSocialManager.processar_interacoes(engine)

    @staticmethod
    def _avancar_relogio(engine):
        engine.tick_count += 1
        engine.data_simulada += timedelta(minutes=1)
        hora_formatada = RelogioMundo.timestamp_rpg(engine.data_simulada)
        engine.db.salvar_meta(MetaChave.HORA_ISO, engine.data_simulada.isoformat())
        engine.db.salvar_meta(MetaChave.HORA_FORMATADA, hora_formatada)
        WorldLogger.info(f"\n--- Tick {engine.tick_count} | {hora_formatada} ---")

    @staticmethod
    def _atualizar_eventos_globais(engine) -> list:
        GlobalEventManager.atualizar_eventos_globais(engine)
        return engine.db.carregar_eventos_globais_ativos()

    @staticmethod
    def _executar_rotinas_agendadas(engine):
        """Gatilhos baseados no relógio do jogo, disparados uma vez na hora exata
        (minuto 0) — concepção noturna, crescimento, expansão urbana, pensões."""
        if engine.data_simulada.minute != 0:
            return
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        hora = engine.data_simulada.hour

        if hora == cfg_get(cfg_bio, "concepcao_hora"):
            NPCReproductionManager.processar_concepcao(engine)
        if hora == cfg_get(cfg_bio, "crescimento_hora"):
            NPCLifecycleManager.processar_crescimento(engine)
        if hora == cfg_get(cfg_bio, "habitacao_hora"):
            NPCHousingManager.processar_habitacao(engine)
        if hora == cfg_get(cfg_bio, "pagamento_reino_hora"):
            KingdomManager.processar_pagamentos_reino(engine)

    @staticmethod
    def _aplicar_metabolismo(engine, npc: NPC, maes_em_parto: list):
        """Perda/ganho passivo de energia/fome/social, e o consumo extra de gestação.
        Também recalcula `num_dependentes` (campo derivado, ver `models.NPC`)."""
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        meta = cfg_get(engine.config, "metabolismo")
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

        npc.num_dependentes = NPCUtils.contar_dependentes_na_casa(engine.npcs, npc)

    @staticmethod
    def _decidir_e_executar(engine, npc: NPC, eventos_globais: list):
        acao_anterior = npc.acao_atual
        NPCBrain.decidir_acao(npc, engine.data_simulada.hour, engine.config, engine.locais, eventos_globais)

        if npc.acao_atual != acao_anterior:
            WorldLogger.debug(f"[NPC] {npc.nome} mudou de {acao_anterior.value} para {npc.acao_atual.value}", npc=npc)

        NPCActionManager.executar_acao(engine, npc)

    @staticmethod
    def _aplicar_consequencias_de_saude(engine, npc: NPC):
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        if npc.fome > cfg_get(cfg_bio, "inaniacao_fome_limiar"):
            npc.saude -= cfg_get(cfg_bio, "inaniacao_perda_saude")
            WorldLogger.warning(f"💔 [INANIÇÃO] {npc.nome} está perdendo saúde! (Saúde: {npc.saude})", npc=npc)
        elif npc.fome < cfg_get(cfg_bio, "recuperacao_sono_fome_maxima") and npc.acao_atual == Acao.DORMIR:
            if npc.saude < ESCALA_MAXIMA:
                npc.saude = min(ESCALA_MAXIMA, npc.saude + cfg_get(cfg_bio, "dormir_ganho_saude"))

    @staticmethod
    def _remover_falecidos(engine):
        engine.npcs = [n for n in engine.npcs if n.saude > 0]

    @staticmethod
    def _processar_partos(engine, maes_em_parto: list):
        for mae in maes_em_parto:
            NPCReproductionManager.processar_parto(engine, mae)
