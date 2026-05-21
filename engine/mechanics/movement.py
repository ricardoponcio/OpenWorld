import random
from ..models import NPC, Acao
from ..logger import WorldLogger
from ..config_loader import cfg_get
from ..utils import LocationUtils

class NPCMovementManager:
    @staticmethod
    def mover_para(engine, npc: NPC, local_id: str):
        """Move o NPC para um local específico com validação de segurança."""
        locais = engine.locais
        
        # Se for bebê ou dependente, ele deve SEMPRE ficar em sua própria residência!
        if getattr(npc, 'estagio_vida', '') == 'bebe' or npc.profissao == 'dependente':
            local_id = npc.casa_id
            
        # Se o local de destino não existe ou está inativo (status=0), volta para casa
        local_destino = locais.get(local_id) if locais else None
        if not local_destino or getattr(local_destino, 'status', 1) != 1:
            local_id = npc.casa_id
            
        # Garante que a casa existe, caso contrário tenta a primeira casa ativa
        if local_id not in locais:
            casas_disponiveis = [l_id for l_id, l in locais.items() if l.tipo == 'Casa' or getattr(l, 'categoria', '') == 'residencia']
            if casas_disponiveis:
                local_id = casas_disponiveis[0]
                
        # Se mudou de localização, atualiza
        if npc.localizacao_atual_id != local_id:
            nome_local = locais[local_id].nome if local_id in locais else local_id
            WorldLogger.debug(f"🚶 {npc.nome} deslocou-se para {nome_local}.", npc=npc)
            npc.localizacao_atual_id = local_id

    @staticmethod
    def mover_para_casa(engine, npc: NPC):
        """Move o NPC para sua residência oficial."""
        NPCMovementManager.mover_para(engine, npc, npc.casa_id)

    @staticmethod
    def mover_para_obra(engine, npc: NPC, obra_id: str):
        """Move o NPC para uma obra em andamento (status 0)."""
        if getattr(npc, 'estagio_vida', '') == 'bebe' or npc.profissao == 'dependente':
            local_id = npc.casa_id
        else:
            local_id = obra_id
            
        if npc.localizacao_atual_id != local_id:
            nome_local = engine.locais[local_id].nome if engine.locais and local_id in engine.locais else local_id
            WorldLogger.debug(f"🚶 {npc.nome} deslocou-se para a {nome_local}.", npc=npc)
            npc.localizacao_atual_id = local_id

    @staticmethod
    def mover_para_trabalho(engine, npc: NPC):
        """Move o NPC para seu local de trabalho se ativo, senão vai para casa e fica ocioso."""
        locais = engine.locais
        loc_trab = locais.get(npc.local_trabalho_id) if locais else None
        
        if loc_trab and getattr(loc_trab, 'status', 1) == 1:
            NPCMovementManager.mover_para(engine, npc, npc.local_trabalho_id)
        else:
            NPCMovementManager.mover_para_casa(engine, npc)
            npc.acao_atual = Acao.OCIOSO

    @staticmethod
    def mover_para_social(engine, npc: NPC):
        """Move o NPC para um local social ativo ou para casa se tiver dependentes/nenhum local."""
        locais = engine.locais
        sociais = [l_id for l_id, l in locais.items() if l.tipo == 'Social' and getattr(l, 'status', 1) == 1] if locais else []
        
        num_dep = getattr(npc, 'num_dependentes', 0)
        if num_dep > 0 and random.random() < 0.50:
            NPCMovementManager.mover_para_casa(engine, npc)
        elif sociais:
            # NPCs com menos de limiar_pobreza dão preferência a locais públicos/gratuitos (praças, parques, arenas, etc.)
            cfg_dec = cfg_get(engine.config, "ia_decisao")
            limiar_pobreza = cfg_get(cfg_dec, "limiar_pobreza_pc")
            
            if npc.dinheiro_total_pc < limiar_pobreza:
                sociais_gratuitos = [
                    l_id for l_id in sociais 
                    if LocationUtils.is_local_publico(locais[l_id])
                ]
                if sociais_gratuitos:
                    NPCMovementManager.mover_para(engine, npc, random.choice(sociais_gratuitos))
                    return
            
            NPCMovementManager.mover_para(engine, npc, random.choice(sociais))
        else:
            NPCMovementManager.mover_para_casa(engine, npc)

    @staticmethod
    def mover_para_restaurante(engine, npc: NPC):
        """Move o NPC para uma taverna/praça ativa, ou casa em último caso."""
        locais = engine.locais
        locais_comida = []
        if locais:
            for l_id, l in locais.items():
                if getattr(l, 'status', 1) != 1: continue
                if LocationUtils.is_local_comida(l):
                    locais_comida.append(l_id)
        
        # 50% de chance de comer em casa para economizar e reduzir superlotação de restaurantes
        if locais_comida and random.random() < 0.5:
            NPCMovementManager.mover_para(engine, npc, random.choice(locais_comida))
        else:
            NPCMovementManager.mover_para_casa(engine, npc)

    @staticmethod
    def mover_para_local_social(engine, npc: NPC):
        """Redireciona para mover_para_social para compatibilidade externa."""
        NPCMovementManager.mover_para_social(engine, npc)

    @staticmethod
    def mover_aleatoriamente(engine, npc: NPC):
        """Move o NPC aleatoriamente entre locais públicos/sociais ou sua casa."""
        locais_permitidos = []
        if engine.locais:
            for l_id, l in engine.locais.items():
                if getattr(l, 'status', 1) != 1: continue
                # Permite apenas locais Sociais, Lojas comerciais, ou a própria casa do NPC (evita que ociosos invadam quartéis e fazendas)
                if LocationUtils.is_local_passeio(l, npc.casa_id):
                    locais_permitidos.append(l_id)
                    
        if locais_permitidos:
            NPCMovementManager.mover_para(engine, npc, random.choice(locais_permitidos))
        else:
            NPCMovementManager.mover_para_casa(engine, npc)
