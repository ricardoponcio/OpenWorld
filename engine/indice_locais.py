"""
MODULE: indice_locais.py
FUNÇÃO: Índices de leitura sobre os locais, por cidade e por papel (P01, docs/
        12_PLANO_CIDADE_VIVA.md).

DESCRIÇÃO:
    Existe porque cada consulta de movimento (`mover_para_social`,
    `mover_para_restaurante`, `mover_aleatoriamente`) e `NPCUtils.obter_obra_do_npc`
    varriam a lista INTEIRA de locais, por NPC, por tick — o que fazia o custo do tick
    ser NPCs × locais (Seção 1.6 do plano: 53,8 ms com 20 NPCs e 24 mil locais, contra
    2,9 ms com mil locais).

    Vocabulário e estrutura de leitura (camada de MODELO, 11_ARQUITETURA.md) — nenhuma
    regra de simulação mora aqui, só a pergunta "que locais deste papel existem nesta
    cidade", já respondida na carga.

    Quem muda um local (criar, desativar, concluir obra) é obrigado a avisar o índice
    — por isso `registrar`/`remover` são públicos. P02 garante que todo caminho de
    escrita de local passa por aqui; até lá, um local criado/desativado fora de
    `EstadoDoMundo.registrar_local`/`desativar_local` deixa o índice desatualizado.
"""
import collections

from .models import Local, CategoriaLocal, TipoLocal
from .consultas_local import LocationUtils


class IndiceDeLocais:
    def __init__(self, locais: dict):
        # dict[cidade_id, list[local_id]] — um por papel, como o plano pede.
        self._sociais = collections.defaultdict(list)
        self._sociais_publicos = collections.defaultdict(list)
        self._comida = collections.defaultdict(list)
        self._passeio = collections.defaultdict(list)
        self._residencias_ativas = collections.defaultdict(list)
        # dict[cidade_id, dict[categoria, list[local_id]]] — vagas de trabalho por tipo.
        self._trabalho_por_categoria = collections.defaultdict(lambda: collections.defaultdict(list))
        # dict[npc_id, local_id] — obra em andamento cujo dono é aquele NPC.
        self.obra_por_dono = {}
        # dict[local_id, Local] — acesso por id, sem depender de `EstadoDoMundo.locais`.
        self.por_id = {}
        for local_id, local in locais.items():
            self.registrar(local_id, local)

    # ------------------------------------------------------------------
    def registrar(self, local_id: str, local: Local) -> None:
        """Roda uma vez por local, na carga (ou quando um local novo nasce, P02) — os
        predicados (`is_local_comida`/`is_local_publico`) são calculados AQUI, não a
        cada consulta (antes: `is_local_publico` chamava `carregar_config_global()`
        dentro do laço de cada NPC, todo tick)."""
        self.por_id[local_id] = local
        cidade_id = local.cidade_id

        if local.tipo == TipoLocal.CASA.value and local.status == 0 and local.dono_npc_id:
            self.obra_por_dono[local.dono_npc_id] = local_id

        if local.status != 1:
            return  # inativo/em obra não entra em nenhum índice de "disponível agora"

        if local.tipo == TipoLocal.SOCIAL.value:
            self._sociais[cidade_id].append(local_id)
            if LocationUtils.is_local_publico(local):
                self._sociais_publicos[cidade_id].append(local_id)
        if LocationUtils.is_local_comida(local):
            self._comida[cidade_id].append(local_id)
        if local.tipo in (TipoLocal.SOCIAL.value, TipoLocal.LOJA.value):
            self._passeio[cidade_id].append(local_id)
        if local.categoria == CategoriaLocal.RESIDENCIA.value:
            self._residencias_ativas[cidade_id].append(local_id)
        self._trabalho_por_categoria[cidade_id][local.categoria].append(local_id)

    def remover(self, local_id: str) -> None:
        """P02: tira o local de todo índice de "disponível agora" — usado tanto por
        `EstadoDoMundo.desativar_local` (status vira 0 pra valer) quanto por
        `registrar_local` re-registrando um local que já existia (limpa o estado
        antigo antes de reindexar do zero, ex.: obra concluída não pode continuar em
        `obra_por_dono` como se ainda estivesse em construção)."""
        local = self.por_id.get(local_id)
        if local is None:
            return
        cidade_id = local.cidade_id
        for indice in (self._sociais, self._sociais_publicos, self._comida,
                       self._passeio, self._residencias_ativas):
            lista = indice.get(cidade_id)
            if lista and local_id in lista:
                lista.remove(local_id)
        cat_lista = self._trabalho_por_categoria.get(cidade_id, {}).get(local.categoria)
        if cat_lista and local_id in cat_lista:
            cat_lista.remove(local_id)
        if self.obra_por_dono.get(local.dono_npc_id) == local_id:
            del self.obra_por_dono[local.dono_npc_id]

    # ------------------------------------------------------------------
    # Consultas por papel — todas devolvem lista vazia pra cidade sem local daquele
    # papel, nunca KeyError (é estado normal, não config ausente).
    # ------------------------------------------------------------------
    def sociais(self, cidade_id) -> list:
        return self._sociais.get(cidade_id, [])

    def sociais_publicos(self, cidade_id) -> list:
        return self._sociais_publicos.get(cidade_id, [])

    def comida(self, cidade_id) -> list:
        return self._comida.get(cidade_id, [])

    def passeio(self, cidade_id) -> list:
        return self._passeio.get(cidade_id, [])

    def residencias_ativas(self, cidade_id) -> list:
        return self._residencias_ativas.get(cidade_id, [])

    def trabalho_por_categoria(self, cidade_id, categoria) -> list:
        return self._trabalho_por_categoria.get(cidade_id, {}).get(categoria, [])
