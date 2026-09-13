"""
MODULE: criar_local.py
FUNÇÃO: Ação de mundo CRIAR_LOCAL do Modo Mestre.
"""
from typing import List

from ....models import ComandoMestre, TipoLocal
from ...urbanismo import GerenciadorUrbanismo, SpecObra
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre


class CriarLocal(AcaoDeMundo):
    comando = ComandoMestre.CRIAR_LOCAL

    def aplicar(self, mundo, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        """M02 (docs/PLANO_POPULACAO_E_ESCALA.md) + F01/F02 (docs/
        PLANO_AVANCO_E_CALIBRAGEM.md): chama `abrir_obra` DE VERDADE — o mesmo
        caminho único pelo qual todo edifício nasce durante a simulação (O03,
        docs/PLANO_CIDADE_VIVA.md). M02 precisou reservar o lote na mão e inventar
        `_avaliar_expansao_fora_do_processo` porque o Modo Mestre não tinha o
        `EstadoDoMundo` vivo; agora tem (roda dentro de `run_simulation.py`, via
        `MestreManager.drenar_e_aplicar`), então esse desvio inteiro some.

        Sem dono (um quartel não tem dono pessoal — F02) e `pronta=True` (nasce
        pronto, não em obra). Sem cidade simulada não há onde abrir — a ação não
        cria nada."""
        d = acao.dados
        if not contexto.cidade_id_simulada:
            return []
        cidade_id = int(contexto.cidade_id_simulada)

        spec = SpecObra(
            categoria=d.get("categoria", "generic"),
            tipo_local=d.get("tipo", TipoLocal.SOCIAL.value),
            nome=d.get("nome", "Local Indefinido"),
            capacidade=d.get("capacidade", 5),
        )
        urbanismo = GerenciadorUrbanismo(mundo, contexto.config)
        obra = urbanismo.abrir_obra(cidade_id, spec, dono_npc=None, pronta=True)
        if obra is None:
            return [f"⚠️ Sem lote livre em cidade {cidade_id} mesmo após avaliar expansão — nada criado."]

        # REATRIBUIR_NPC na mesma tacada precisa deste id para resolver "NOVO_LOCAL".
        contexto.novo_local_id = obra.id
        return [f"🏗️ Criado: {obra.nome} em ({obra.coordenadas[0]}, {obra.coordenadas[1]})"]
