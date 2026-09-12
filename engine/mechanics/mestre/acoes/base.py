"""
MODULE: base.py
FUNÇÃO: Contrato de uma ação de mundo do Modo Mestre (R-F03).

DESCRIÇÃO:
    `aplicar_acoes` era um if/elif de quatro ramos sobre strings vindas da IA, com SQL
    cru dentro de cada ramo. O SQL já mudou para os repositórios; aqui cada ramo passa
    a ser uma classe com um único método, para que acrescentar um comando novo signifique
    acrescentar um arquivo e uma entrada no registro — e nunca mexer no despacho.

    Desvio consciente do esboço do plano: `aplicar` devolve `list[str]`, não `str`.
    REATRIBUIR_NPC produz até dois resultados (trabalho e casa) e pode não produzir
    nenhum quando o local alvo não existe; forçar uma string só obrigaria a inventar um
    resultado vazio.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ....models import ComandoMestre


@dataclass
class ContextoMestre:
    """O que uma ação precisa saber do mundo além do seu próprio payload.

    `novo_local_id` é o único campo mutável, e é o que permite à IA propor "cria um
    quartel e manda o Brom trabalhar nele" numa tacada: CRIAR_LOCAL escreve o id que
    acabou de nascer, REATRIBUIR_NPC lê esse id quando o payload traz o marcador
    `NOVO_LOCAL`. Antes isso era uma variável solta no meio do laço."""
    cidade_id_simulada: Optional[str]
    cx_cidade: float
    cy_cidade: float
    raio_px: float
    nivel_mar: float
    novo_local_id: Optional[str] = None


@dataclass(frozen=True)
class AcaoProposta:
    """Uma ação já validada contra o enum. `alvo_id` fica fora de `dados` porque é
    assim que a IA responde: o id do alvo no nível de cima, o resto em `dados`."""
    comando: ComandoMestre
    alvo_id: str
    dados: dict

    @classmethod
    def de_payload(cls, payload: dict) -> Optional['AcaoProposta']:
        """Converte o dicionário cru proposto pela IA. Devolve None se o comando não
        existir no enum — resposta de LLM é entrada não confiável e precisa ser validada
        antes de chegar ao mundo (ARQUITETURA.md Seção 9)."""
        try:
            comando = ComandoMestre(payload.get("comando"))
        except ValueError:
            return None
        return cls(
            comando=comando,
            alvo_id=payload.get("id") or "",
            dados=payload.get("dados") or payload,
        )


class AcaoDeMundo(ABC):
    """Uma ação de mundo confirmada pelo jogador. Sem estado: o registro guarda uma
    instância por comando e as reusa."""

    comando: ComandoMestre

    @abstractmethod
    def aplicar(self, db, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        """Aplica a ação e devolve as descrições do que foi feito (para log/exibição).
        Lista vazia significa que nada mudou — alvo inexistente, por exemplo."""
        raise NotImplementedError
