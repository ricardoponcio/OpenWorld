"""
MODULE: criar_local.py
FUNÇÃO: Ação de mundo CRIAR_LOCAL do Modo Mestre.
"""
from datetime import datetime
from typing import List

from ....config_loader import carregar_config_global
from ....models import ComandoMestre, MetaChave, TipoLocal
from ....mundo import EstadoDoMundo
from ...urbanismo import GerenciadorUrbanismo
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class CriarLocal(AcaoDeMundo):
    comando = ComandoMestre.CRIAR_LOCAL

    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        """M02 (docs/PLANO_POPULACAO_E_ESCALA.md): reserva um LOTE real, do jeito que
        `abrir_obra` (O03) faz na simulação — o Mestre era o único caminho no projeto
        que fazia um edifício nascer fora de um lote (`GeoUtils.sortear_ponto_em_terra`,
        qualquer ponto em terra firme), furando a garantia de O03. O id do Local passa
        a SER o id do lote onde nasce (armadilha 3, docs/PLANO_CIDADE_VIVA.md).

        Sem cidade simulada não há lote pra reservar — a ação não cria nada (antes
        criava um Local "flutuante" com `cidade_id=None`; isso não é mais uma opção
        se todo edifício precisa nascer de um lote)."""
        d = acao.dados
        if not contexto.cidade_id_simulada:
            return []
        cidade_id = int(contexto.cidade_id_simulada)

        lote_id = db.lotes.reservar_livre(cidade_id=cidade_id, npc_id="")
        if lote_id is None:
            # X01: a cidade saturou entre duas varreduras diárias — a mesma
            # avaliação de auto-expansão que a simulação usa, chamada daqui de fora.
            _avaliar_expansao_fora_do_processo(db, cidade_id)
            lote_id = db.lotes.reservar_livre(cidade_id=cidade_id, npc_id="")
            if lote_id is None:
                return [f"⚠️ Sem lote livre em cidade {cidade_id} mesmo após avaliar expansão — nada criado."]

        lote = db.lotes.buscar_por_id(lote_id)
        db.locais.criar(
            id=lote_id,
            nome=d.get("nome", "Local Indefinido"),
            tipo=d.get("tipo", TipoLocal.SOCIAL.value),
            cidade_id=cidade_id,
            categoria=d.get("categoria", "generic"),
            descricao=d.get("descricao", ""),
            coordenadas=[lote.x, lote.y],
        )
        # O01: o lote nasce em obra (reservar_livre); um edifício do Mestre aparece
        # pronto, não em construção — conclui na mesma tacada.
        db.lotes.concluir(lote_id, lote_id)

        # REATRIBUIR_NPC na mesma tacada precisa deste id para resolver "NOVO_LOCAL".
        contexto.novo_local_id = lote_id
        return [f"🏗️ Criado: {d.get('nome')} em ({lote.x}, {lote.y})"]


def _avaliar_expansao_fora_do_processo(db, cidade_id) -> None:
    """M02: o Modo Mestre roda no processo do Flask, sem o `EstadoDoMundo` vivo do
    processo da simulação (ARQUITETURA.md Seção 1, regra de processo — só
    `run_simulation.py` instancia a engine). `avaliar_expansao`/`_aplicar_arrabalde`
    só precisam de cidades/locais/data simulada/banco (nunca de `mundo.npcs`) —
    então este `EstadoDoMundo` é um objeto de TRABALHO, montado com dados frescos do
    banco e descartado ao fim desta chamada; não é a engine da simulação, não a
    substitui, e não deve ser reusado."""
    hora_iso = db.meta.carregar(MetaChave.HORA_ISO)
    data_simulada = datetime.fromisoformat(hora_iso) if hora_iso else datetime.now()
    mundo_de_trabalho = EstadoDoMundo(
        npcs=[], locais=db.locais.carregar_por_id(),
        cidades=db.mundo.carregar_cidades_por_id(),
        data_simulada=data_simulada, db=db)
    GerenciadorUrbanismo(mundo_de_trabalho, carregar_config_global()).avaliar_expansao(cidade_id)
