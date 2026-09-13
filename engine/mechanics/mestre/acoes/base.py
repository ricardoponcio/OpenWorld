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

    F01 (docs/PLANO_AVANCO_E_CALIBRAGEM.md): `aplicar` recebe `EstadoDoMundo`, não
    `db` — só `run_simulation.py` chama isto agora (`MestreManager.drenar_e_aplicar`),
    com o mundo vivo, então cada ação pode usar as portas de `mundo`
    (`acordar`/`mover_npc`/`mudar_casa`/`registrar_local`/`desativar_local`) em vez
    de escrever direto no banco por fora dos índices mantidos em memória — que
    ficariam desatualizados até o próximo `recarregar_habitantes()`/`recarregar_locais()`
    (armadilha 12, docs/PLANO_POPULACAO_E_ESCALA.md). `mundo.db` continua disponível
    pra quem só precisa de leitura/escrita crua (ex.: lotes)."""
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
    `NOVO_LOCAL`. Antes isso era uma variável solta no meio do laço.

    `config` (F02, docs/PLANO_AVANCO_E_CALIBRAGEM.md): CRIAR_LOCAL precisa montar um
    `GerenciadorUrbanismo(mundo, config)` pra chamar `abrir_obra` de verdade — a
    config inteira, não só os quatro campos já extraídos acima, porque
    `GerenciadorUrbanismo` lê de vários dicionários (`urbanismo`, `geracao_urbana`)."""
    cidade_id_simulada: Optional[str]
    cx_cidade: float
    cy_cidade: float
    raio_px: float
    nivel_mar: float
    config: Optional[dict] = None
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
    def aplicar(self, mundo, contexto: ContextoMestre, acao: AcaoProposta) -> List[str]:
        """Aplica a ação e devolve as descrições do que foi feito (para log/exibição).
        Lista vazia significa que nada mudou — alvo inexistente, por exemplo."""
        raise NotImplementedError

    @staticmethod
    def encontrar_npc(mundo, npc_id: str):
        """`mundo` não mantém índice por id de NPC (só por casa/localização/cidade,
        A04) — uma ação do Mestre é rara (disparada pelo jogador, nunca por tick),
        então uma varredura O(NPCs) aqui é barata; não vale o custo de manter mais um
        índice só pra isto."""
        return next((n for n in mundo.npcs if n.id == npc_id), None)
