import time
import random
from datetime import datetime
from ..models import NPC, Evento, EstagioVida, TipoEvento, Acao
from ..logger import WorldLogger
from ..config_loader import cfg_get

class NPCLifecycleManager:
    @staticmethod
    def processar_crescimento(engine):
        """Varredura diária para processar o crescimento e transição de estágios de vida dos NPCs."""
        cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"

        for npc in engine.npcs:
            if not npc.esta_vivo() or not npc.data_nascimento:
                continue
            
            try:
                dt_str = npc.data_nascimento.replace(' ', 'T')
                birth = datetime.fromisoformat(dt_str)
                idade_dias = (engine.data_simulada - birth).days
            except Exception as e:
                continue

            # Bebê -> Criança
            limiar_crianca = cfg_get(cfg_bio, "crescimento_dias_bebe_para_crianca")
            if npc.estagio_vida == EstagioVida.BEBE.value and idade_dias >= limiar_crianca:
                npc.estagio_vida = EstagioVida.CRIANCA.value
                
                resumo = f"Crescimento: O pequeno bebê {npc.nome} deu seus primeiros passos e agora é uma linda criança!"
                WorldLogger.info(f"🌱 [CRESCIMENTO] {resumo}", npc=npc)
                
                evento = Evento(
                    id=f"evt_crescer_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.CRESCIMENTO.value,
                    modificador_afinidade=15,
                    resumo_estruturado=resumo
                )
                engine.db.salvar_evento(evento)
                engine.db.salvar_npc(npc)

            # Criança -> Adulto
            elif npc.estagio_vida == EstagioVida.CRIANCA.value and idade_dias >= cfg_get(cfg_bio, "crescimento_dias_crianca_para_adulto"):
                npc.estagio_vida = EstagioVida.ADULTO.value
                npc.local_trabalho_id = None
                npc.profissao_id = 'ocioso'
                npc.profissao = 'Desempregado'

                resumo = f"Maioridade: {npc.nome} atingiu a maioridade, tornando-se adulto(a) e iniciando sua busca por oportunidades!"
                WorldLogger.info(f"🌱 [MAIORIDADE] {resumo}", npc=npc)

                evento = Evento(
                    id=f"evt_adulto_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.MAIORIDADE.value,
                    modificador_afinidade=20,
                    resumo_estruturado=resumo
                )
                engine.db.salvar_evento(evento)
                engine.db.salvar_npc(npc)

            # Adulto -> Idoso
            elif npc.estagio_vida == EstagioVida.ADULTO.value and idade_dias >= cfg_get(cfg_bio, "crescimento_dias_adulto_para_idoso"):
                npc.estagio_vida = EstagioVida.IDOSO.value
                
                # Aposentadoria — desvincula do trabalho com None (não string vazia)
                npc.local_trabalho_id = None
                npc.profissao = "Aposentado(a)"
                
                resumo = f"Envelhecimento: {npc.nome} entrou na terceira idade, tornando-se um sábio ancião aposentado da vila!"
                WorldLogger.info(f"👵 [ENVELHECIMENTO] {resumo}", npc=npc)

                evento = Evento(
                    id=f"evt_idoso_{int(time.time())}_{random.randint(0,999)}",
                    timestamp=timestamp_rpg,
                    local_id=npc.casa_id or "rua",
                    envolvidos=[npc.id],
                    tipo_evento=TipoEvento.CRESCIMENTO.value,
                    modificador_afinidade=10,
                    resumo_estruturado=resumo
                )
                engine.db.salvar_evento(evento)
                engine.db.salvar_npc(npc)

            # Idoso -> Morto por Velhice
            elif npc.estagio_vida == EstagioVida.IDOSO.value and idade_dias >= cfg_get(cfg_bio, "crescimento_dias_idoso_para_morte"):
                npc.saude = 0
                NPCLifecycleManager.processar_morte(engine, npc)

    @staticmethod
    def processar_morte(engine, npc: NPC):
        """Processa o falecimento biológico de um NPC, liberando seus recursos e acionando o testamento financeiro."""
        from ..models import Acao, EstagioVida, Evento, TipoEvento
        
        # 1. Registrar o óbito no banco para consistência histórica
        dia = (engine.data_simulada - datetime(1200, 1, 1, 0, 0)).days + 1
        timestamp_rpg = f"Dia {dia}, {engine.data_simulada.strftime('%H:%M')}"
        
        idade_anos = 0
        if npc.data_nascimento:
            try:
                cfg_bio = cfg_get(engine.config, "biologia_e_sociedade")
                limiar_morte = cfg_get(cfg_bio, "crescimento_dias_idoso_para_morte")
                
                dt_str = npc.data_nascimento.replace(' ', 'T')
                birth = datetime.fromisoformat(dt_str)
                idade_dias = (engine.data_simulada - birth).days
                idade_anos = int((idade_dias / limiar_morte) * 80.0)
            except:
                pass
                
        idade_str = f" aos {idade_anos} anos" if idade_anos > 0 else ""
        if npc.estagio_vida == EstagioVida.IDOSO.value:
            resumo = f"Luto na Vila: O ancião {npc.nome} faleceu{idade_str} pacificamente de velhice."
        else:
            resumo = f"Luto na Vila: O habitante {npc.nome} faleceu{idade_str} devido a problemas de saúde/inanição."
        
        evento = Evento(
            id=f"evt_morte_{int(time.time())}_{random.randint(0,999)}",
            timestamp=timestamp_rpg,
            local_id=npc.casa_id or "rua",
            envolvidos=[npc.id],
            tipo_evento=TipoEvento.OBITO.value,
            modificador_afinidade=0,
            resumo_estruturado=resumo
        )
        engine.db.salvar_evento(evento)
        WorldLogger.info(f"💀 [ÓBITO] {resumo}", npc=npc)
        
        # --- FASE GERACIONAL FINANCEIRA: Testamento/Herança ---
        from .finance import NPCLegacyManager
        NPCLegacyManager.processar_heranca(engine, npc, timestamp_rpg)
        
        # --- FASE BIOLÓGICA/SOCIAL: Desvinculação ---
        npc.casa_id = ""
        npc.local_trabalho_id = ""
        npc.localizacao_atual_id = ""
        npc.acao_atual = Acao.OCIOSO
        npc.estagio_vida = EstagioVida.MORTO.value
        npc.saude = 0
        
        # Salvar as alterações finais do NPC falecido
        engine.db.salvar_npc(npc)
