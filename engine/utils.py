from typing import List, Dict
from .models import NPC, Local

class NPCUtils:
    @staticmethod
    def agrupar_npcs_por_localizacao(npcs: List[NPC], ignorar_dormindo: bool = True) -> Dict[str, List[NPC]]:
        """
        Agrupa os NPCs ativos/vivos pela sua localização atual.
        """
        from .models import Acao
        por_local = {}
        for npc in npcs:
            if not npc.esta_vivo():
                continue
            if ignorar_dormindo and npc.acao_atual == Acao.DORMIR:
                continue
            loc_id = npc.localizacao_atual_id
            if not loc_id:
                continue
            if loc_id not in por_local:
                por_local[loc_id] = []
            por_local[loc_id].append(npc)
        return por_local

    @staticmethod
    def agrupar_por_casa(npcs: List[NPC]) -> Dict[str, List[NPC]]:
        """
        Agrupa todos os NPCs vivos pelas suas respectivas casas (onde moram).
        """
        por_casa = {}
        for npc in npcs:
            if not npc.esta_vivo() or not npc.casa_id:
                continue
            if npc.casa_id not in por_casa:
                por_casa[npc.casa_id] = []
            por_casa[npc.casa_id].append(npc)
        return por_casa

    @staticmethod
    def obter_moradores_da_casa(npcs: List[NPC], casa_id: str, apenas_vivos: bool = True) -> List[NPC]:
        """
        Retorna todos os NPCs que moram na casa especificada.
        """
        if not casa_id:
            return []
        moradores = []
        for npc in npcs:
            if npc.casa_id == casa_id:
                if apenas_vivos and not npc.esta_vivo():
                    continue
                moradores.append(npc)
        return moradores

    @staticmethod
    def obter_parceiros_adultos_na_casa(npcs: List[NPC], npc: NPC) -> List[NPC]:
        """
        Retorna a lista de outros parceiros adultos vivos que residem na mesma casa do NPC.
        """
        if not npc.casa_id:
            return []
        return [
            n for n in npcs 
            if n.id != npc.id 
            and n.esta_vivo() 
            and n.casa_id == npc.casa_id 
            and n.is_adulto()
        ]

    @staticmethod
    def tem_conjuge(npc: NPC) -> bool:
        """
        Verifica se o NPC é formalmente casado com alguém usando o novo status civil.
        """
        from .models import EstadoCivil
        return npc.estado_civil == EstadoCivil.CASADO.value and npc.conjuge_id != ""

    @staticmethod
    def sao_parentes(n1: NPC, n2: NPC) -> bool:
        """
        Verifica se dois NPCs são parentes diretos (pais, filhos, ou irmãos)
        para impedir casamentos incestuosos.
        """
        # Verifica se n1 é pai/mãe de n2
        if n1.id in n2.genealogia or n1.id == n2.pai_id or n1.id == n2.mae_id:
            return True
        # Verifica se n2 é pai/mãe de n1
        if n2.id in n1.genealogia or n2.id == n1.pai_id or n2.id == n1.mae_id:
            return True
            
        # Verifica se são irmãos (possuem pais em comum que não sejam nulos)
        pais_n1 = set(n1.genealogia + ([n1.pai_id, n1.mae_id]))
        pais_n1.discard("")
        
        pais_n2 = set(n2.genealogia + ([n2.pai_id, n2.mae_id]))
        pais_n2.discard("")
        
        
        if len(pais_n1.intersection(pais_n2)) > 0:
            return True
            
        return False

    @staticmethod
    def obter_obra_do_npc(locais: Dict[str, 'Local'], npc: NPC):
        """
        Retorna a obra (Local em construção) que pertence ao NPC ou seu cônjuge.
        """
        if not locais: return None
        for l in locais.values():
            if l.tipo == "Casa" and l.status == 0:
                if npc.id in getattr(l, 'descricao', '') or (npc.conjuge_id and npc.conjuge_id in getattr(l, 'descricao', '')):
                    return l
        return None

class LocationUtils:
    @staticmethod
    def is_local_publico(local: 'Local') -> bool:
        """
        Verifica se um local é público/gratuito (ex: praça, parque, etc.).
        """
        if not local:
            return False
        from .models import CategoriaLocal
        if local.categoria == CategoriaLocal.PUBLICO.value:
            return True
        palavras_publicas = ['praça', 'praca', 'parque', 'jardim', 'rua', 'largo', 'campo', 'arena']
        nome_lower = local.nome.lower()
        return any(p in nome_lower for p in palavras_publicas)
