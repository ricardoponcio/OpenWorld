"""
MODULE: criar_local.py
FUNÇÃO: Ação de mundo CRIAR_LOCAL do Modo Mestre.
"""
import random
from typing import List

from ....models import ComandoMestre, TipoLocal
from ....geo import GeoUtils
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre

# Quantas vezes tentar outro ponto antes de aceitar uma coordenada já ocupada: o sorteio
# é em terra firme ao redor da cidade, e colisão é raro o bastante para não valer um laço
# sem teto.
MAX_TENTATIVAS_DE_PONTO = 10


class CriarLocal(AcaoDeMundo):
    comando = ComandoMestre.CRIAR_LOCAL

    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        d = acao.dados
        ponto = self._sortear_ponto_livre(db, contexto)

        novo_id = f"loc_mestre_{random.randint(0, 999999)}"
        db.locais.criar(
            id=novo_id,
            nome=d.get("nome", "Local Indefinido"),
            tipo=d.get("tipo", TipoLocal.SOCIAL.value),
            cidade_id=int(contexto.cidade_id_simulada) if contexto.cidade_id_simulada else None,
            categoria=d.get("categoria", "generic"),
            descricao=d.get("descricao", ""),
            coordenadas=ponto,
        )
        # REATRIBUIR_NPC na mesma tacada precisa deste id para resolver "NOVO_LOCAL".
        contexto.novo_local_id = novo_id
        return [f"🏗️ Criado: {d.get('nome')} em ({ponto[0]}, {ponto[1]})"]

    @staticmethod
    def _sortear_ponto_livre(db, contexto: ContextoMestre):
        """Fase 2.1 (P0.3): o local do Mestre nasce em coordenada de MUNDO, ao redor da
        cidade atualmente simulada — não mais numa grade local fake."""
        existentes = db.locais.coordenadas_ocupadas()
        ponto = GeoUtils.sortear_ponto_em_terra(
            contexto.cx_cidade, contexto.cy_cidade, contexto.raio_px, contexto.nivel_mar)

        tentativa = 0
        while tuple(ponto) in existentes and tentativa < MAX_TENTATIVAS_DE_PONTO:
            ponto = GeoUtils.sortear_ponto_em_terra(
                contexto.cx_cidade, contexto.cy_cidade, contexto.raio_px, contexto.nivel_mar)
            tentativa += 1
        return ponto
