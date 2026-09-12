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
        (multiplicador de custo da refeição).

        ⚠️ O(NPCs) por chamada (`obter_moradores_da_casa` varre todo mundo.npcs) — P03
        (docs/PLANO_CIDADE_VIVA.md): com 750 NPCs chamados por NPC por tick isso é
        O(NPCs²). Só pra teste/uso pontual; no laço de tick use
        `contar_dependentes_na_casa_agrupado` com `agrupar_por_casa` pré-calculado."""
        moradores = NPCUtils.obter_moradores_da_casa(npcs, npc.casa_id, apenas_vivos=True)
        return sum(
            1 for n in moradores
            if n.id != npc.id and (n.mae_id == npc.id or n.pai_id == npc.id) and n.eh_dependente()
        )

    @staticmethod
    def contar_dependentes_na_casa_agrupado(npc: NPC, npcs_por_casa: Dict[str, List[NPC]]) -> int:
        """Mesma conta de `contar_dependentes_na_casa` (P03), recebendo os moradores JÁ
        agrupados por casa (`agrupar_por_casa`, calculado uma vez por tick) em vez de
        varrer `mundo.npcs` de novo pra cada NPC — é o que tira o laço principal do
        tick de O(NPCs²) pra O(NPCs)."""
        moradores = npcs_por_casa.get(npc.casa_id, [])
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
    def obter_casas_vazias(mundo, cidade_id, ignorar_id: str = "", npcs_por_casa: Dict[str, List['NPC']] = None) -> List['Local']:
        """
        Residências ativas (status=1) da CIDADE `cidade_id` que estão completamente
        vazias (zero moradores vivos).

        P03 (docs/PLANO_CIDADE_VIVA.md): consulta `mundo.indice.residencias_ativas`
        (por cidade) em vez de varrer TODOS os locais do mundo — O(locais x NPCs) virou
        O(residências da cidade). De quebra fecha o mesmo bug de "cidade errada" que P04
        corrige em movement.py: antes buscava em `locais.items()` sem filtrar cidade,
        então um casal podia ser realocado pra uma casa vazia do outro lado do mundo.

        `npcs_por_casa` pode vir pré-agrupado (o laço de tick já monta um, P03); se não
        vier, agrupa aqui — esta chamada é rara (só em casamento), o custo não importa.
        """
        if npcs_por_casa is None:
            npcs_por_casa = NPCUtils.agrupar_por_casa(mundo.npcs)

        casas_vazias = []
        for local_id in mundo.indice.residencias_ativas(cidade_id):
            if local_id == ignorar_id or npcs_por_casa.get(local_id):
                continue
            local = mundo.locais.get(local_id)
            if local:
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
    def obter_obra_do_npc(mundo, npc: NPC):
        """
        Retorna a obra (Local em construção, status=0) cujo dono é o NPC ou seu
        cônjuge (R-C03).

        P02 (docs/PLANO_CIDADE_VIVA.md): consulta `mundo.indice.obra_por_dono` (dict
        `npc_id -> local_id`, O(1)) em vez de varrer todos os locais — era a varredura
        mais cara do profiler (Seção 1.6), chamada por NPC, por tick. Antes disso, o
        dono era gravado como texto livre dentro de `descricao` (f"Dono: {id}") e
        recuperado com `npc.id in descricao` — uma busca por substring que casava
        `npc_01` dentro de `npc_012`; `Local.dono_npc_id` corrigiu isso, só não era
        indexado ainda.
        """
        local_id = mundo.indice.obra_por_dono.get(npc.id)
        if local_id is None and npc.conjuge_id:
            local_id = mundo.indice.obra_por_dono.get(npc.conjuge_id)
        return mundo.locais.get(local_id) if local_id else None

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
