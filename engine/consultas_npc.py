from typing import List, Dict
from datetime import datetime
from .models import NPC, Local, MetaChave, TipoLocal, Acao, EstadoCivil
from .tempo import RelogioMundo


class NPCUtils:
    @staticmethod
    def agrupar_npcs_por_localizacao(npcs: List[NPC], ignorar_dormindo: bool = True) -> Dict[str, List[NPC]]:
        """
        Agrupa os NPCs ativos/vivos pela sua localização atual.
        """
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
    def contar_dependentes_na_casa(npcs: List[NPC], npc: NPC) -> int:
        """Quantos filhos dependentes (bebê/criança/marcado dependente) de `npc` moram
        na mesma casa (R-D02) — a mesma contagem estava copiada quase idêntica em
        `loop.py` (recálculo de `num_dependentes` a cada tick) e `actions.py`
        (multiplicador de custo da refeição)."""
        moradores = NPCUtils.obter_moradores_da_casa(npcs, npc.casa_id, apenas_vivos=True)
        return sum(
            1 for n in moradores
            if n.id != npc.id and (n.mae_id == npc.id or n.pai_id == npc.id) and n.eh_dependente()
        )

    @staticmethod
    def is_casa_superlotada(locais: Dict[str, 'Local'], npcs: List[NPC], casa_id: str) -> bool:
        """
        Retorna True se a quantidade de moradores vivos na casa exceder ou igualar a capacidade do local.
        """
        if not casa_id or not locais:
            return False
        casa = locais.get(casa_id)
        if not casa:
            return False

        moradores_vivos = NPCUtils.obter_moradores_da_casa(npcs, casa_id, apenas_vivos=True)
        return len(moradores_vivos) >= casa.capacidade

    @staticmethod
    def obter_casas_vazias(locais: Dict[str, 'Local'], npcs: List['NPC'], ignorar_id: str = "") -> List['Local']:
        """
        Retorna uma lista de residências ativas (status=1) que estão completamente vazias (zero moradores vivos).
        """
        if not locais:
            return []

        casas_vazias = []
        for local_id, local in locais.items():
            if local.categoria.lower() == "residencia" and local.status == 1:
                if local_id == ignorar_id:
                    continue
                moradores = NPCUtils.obter_moradores_da_casa(npcs, local_id, apenas_vivos=True)
                if len(moradores) == 0:
                    casas_vazias.append(local)
        return casas_vazias

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
        Retorna a obra (Local em construção, status=0) cujo dono é o NPC ou seu
        cônjuge (R-C03). Antes, o dono era gravado como texto livre dentro de
        `descricao` (f"Dono: {id}") e recuperado com `npc.id in descricao` — uma busca
        por substring que casava `npc_01` dentro de `npc_012`. `Local.dono_npc_id` já
        existia no dataclass e no schema, só não era usado aqui.
        """
        if not locais: return None
        donos = {npc.id}
        if npc.conjuge_id:
            donos.add(npc.conjuge_id)
        for l in locais.values():
            if l.tipo == TipoLocal.CASA.value and l.status == 0 and l.dono_npc_id in donos:
                return l
        return None

    @staticmethod
    def obter_data_nascimento_valida(npc: NPC):
        """
        Retorna um objeto datetime correspondente à data de nascimento do NPC.
        Se for inválida ou vazia, retorna datetime.min para ordenação uniforme.
        """
        if not npc.data_nascimento:
            return datetime.min
        try:
            return datetime.fromisoformat(npc.data_nascimento.replace(' ', 'T'))
        except ValueError:
            return datetime.min

    @staticmethod
    def obter_data_simulada_inicial(db) -> datetime:
        """
        Carrega a data simulada do banco de dados (meta) ou retorna o valor inicial padrão (Dia 1, 06:00).
        """
        hora_salva = db.meta.carregar(MetaChave.HORA_ISO)
        if hora_salva:
            try:
                return datetime.fromisoformat(hora_salva)
            except ValueError:
                pass
        return RelogioMundo.HORA_INICIAL_PADRAO
