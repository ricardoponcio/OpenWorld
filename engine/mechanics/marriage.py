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
from datetime import datetime
from ..models import NPC, Evento, TipoEvento, EstadoCivil
from ..logger import WorldLogger
from ..utils import NPCUtils
from ..config_loader import cfg_get
from .housing import NPCHousingManager


class NPCMarriageManager:
    @staticmethod
    def verificar_elegibilidade_casamento(engine, n1: NPC, n2: NPC, afinidade: int) -> bool:
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
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        limiar_uniao = cfg_get(cfg_bio, "concepcao_afinidade_minima")
        if afinidade < limiar_uniao:
            return False

        return True

    @staticmethod
    def realizar_casamento(engine, n1: NPC, n2: NPC, casa_escolhida: str, surpresa: bool = False) -> bool:
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
        casa_obj = engine.locais.get(casa_escolhida)
        moradores_casa = NPCUtils.obter_moradores_da_casa(engine.npcs, casa_escolhida, apenas_vivos=True)
        casa_cheia = casa_obj and len(moradores_casa) >= casa_obj.capacidade

        teve_nova_casa = False
        if casa_cheia:
            if NPCHousingManager.iniciar_obra_para_casal(engine, n1, n2):
                teve_nova_casa = True
                prefixo = "SURPRESA" if surpresa else "PLANEJADO"
                WorldLogger.info(
                    f"🏗️ [NOVO LAR {prefixo}] Recém-casados {n1.nome} e {n2.nome} iniciaram a "
                    f"construção de sua própria casa por falta de espaço na moradia dos pais!",
                    npc=n1
                )

        if not teve_nova_casa:
            # Se a casa tem espaço (ou se falhou a alocação), moram juntos na casa escolhida
            n2.casa_id = casa_escolhida
            n2.localizacao_atual_id = casa_escolhida

        # Salvar NPCs no banco
        engine.db.salvar_npc(n1)
        engine.db.salvar_npc(n2)

        # Registrar Evento de União no RPG
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
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
        engine.db.salvar_evento(evento)

        # Aumentar afinidade e salvar o relacionamento no banco
        n1.relacionamentos[n2.id] = min(1000, n1.relacionamentos.get(n2.id, 0) + bonus_afinidade)
        n2.relacionamentos[n1.id] = min(1000, n2.relacionamentos.get(n1.id, 0) + bonus_afinidade)
        engine.db.salvar_relacionamento(n1.id, n2.id, n1.relacionamentos[n2.id], "Aliado")

        # Emitir logs oficiais do simulador
        WorldLogger.info(f"❤️ [UNIÃO] {resumo}", npc=n1)
        WorldLogger.queue_db_log(n2, "INFO", f"❤️ [UNIÃO] {resumo}")

        return teve_nova_casa

    @staticmethod
    def processar_coabitacao(engine):
        """
        Executa a rotina periódica (offline/background) de casamentos planejados e coabitação.
        
        Essa rotina varre o banco de dados de NPCs solteiros em busca de casais de alta 
        afinidade acumulada que atendam a todas as restrições biológicas e sociais de união. 
        Ao encontrar um par elegível, há uma chance aleatória de eles formalizarem a união,
        se mudarem para o mesmo lar e, caso a moradia de destino esteja cheia, iniciarem a 
        construção de uma residência independente para aliviar a superlotação.
        """
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        # Carrega a chance de casamento passivo de forma configurável
        chance_uniao = cfg_get(cfg_bio, "casamento_chance_coabitacao")
        
        # Filtra apenas NPCs solteiros ativos (vivos)
        solteiros = [n for n in engine.npcs if n.esta_vivo() and not NPCUtils.tem_conjuge(n)]
        
        for n1 in solteiros:
            for n2 in solteiros:
                if n1.id == n2.id:
                    continue
                
                # A validação biológica completa e de consanguinidade é delegada à função central
                afinidade = n1.relacionamentos.get(n2.id, 0)
                if NPCMarriageManager.verificar_elegibilidade_casamento(engine, n1, n2, afinidade):
                    if random.random() < chance_uniao:
                        casa_escolhida = n1.casa_id or n2.casa_id
                        if casa_escolhida:
                            # Realizar casamento completo e atômico
                            NPCMarriageManager.realizar_casamento(engine, n1, n2, casa_escolhida, surpresa=False)
                            
                            # Retorna para evitar processar mais de uma união no mesmo tick
                            return
