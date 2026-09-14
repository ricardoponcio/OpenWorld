"""
MODULE: estatisticas.py
FUNÇÃO: Números agregados do mundo para o painel e o console.

DESCRIÇÃO:
    O03 (docs/16_PLANO_PAINEL_E_IA.md): substitui "ler o log pra saber o que está
    acontecendo" por um retrato calculado a cada N ticks, direto dos índices já
    mantidos em `EstadoDoMundo` (`npcs`, `npcs_por_cidade`, `contadores`) — NUNCA
    varrendo o banco. `run_simulation.py` grava o resultado em
    `MetaChave.ESTATISTICAS`; o painel só lê essa chave (Armadilha 24: nunca "tudo,
    e o front filtra").

    Fluxo (chamado a cada `observabilidade.estatisticas_a_cada_ticks`):
      1. montar()             — retrato do instante atual: por cidade, total, dia
      2. _por_cidade()        — um resumo por cidade habitada
      3. _contadores_do_dia() — os ContadorMundo (O02) do dia simulado corrente;
                                zera e arquiva em "dia_anterior" quando o dia vira
"""
import statistics
from collections import Counter
from typing import Dict, List

from ..config_loader import cfg_get
from ..models import ContadorMundo, EstagioVida, NPC
from ..mundo import EstadoDoMundo
from ..tempo import RelogioMundo


class ColetorDeEstatisticas:
    """Instância porque guarda o dia simulado da última montagem (pra zerar os
    contadores só quando o dia vira, não a cada chamada) — não é um grupo de
    funções puras sem estado (ARQUITETURA §7)."""

    def __init__(self, mundo: EstadoDoMundo, config: dict):
        self._mundo = mundo
        self._config = config
        self._ultimo_dia = None

    def montar(self) -> dict:
        limiar_fome = cfg_get(cfg_get(self._config, "biologia_e_sociedade"), "inaniacao_fome_limiar")
        resultado = {
            "por_cidade": self._por_cidade(limiar_fome),
            "total": self._resumo(self._mundo.npcs, limiar_fome),
        }
        resultado.update(self._contadores_do_dia())
        return resultado

    def _por_cidade(self, limiar_fome: float) -> Dict[int, dict]:
        resultado = {}
        for cidade_id, npcs in self._mundo.npcs_por_cidade.items():
            cidade = self._mundo.cidades.get(cidade_id)
            resumo = self._resumo(npcs, limiar_fome)
            resumo["nome"] = cidade.nome if cidade else None
            resultado[cidade_id] = resumo
        return resultado

    @staticmethod
    def _resumo(npcs: List[NPC], limiar_fome: float) -> dict:
        vivos = [n for n in npcs if n.esta_vivo()]
        adultos = [n for n in vivos if n.estagio_vida == EstagioVida.ADULTO.value]
        empregados = sum(1 for n in adultos if n.local_trabalho_id)
        saldos_adultos = [n.dinheiro_total_pc for n in adultos]
        return {
            "vivos_por_estagio": dict(Counter(n.estagio_vida for n in vivos)),
            "empregados": empregados,
            "desempregados": len(adultos) - empregados,
            "famintos": sum(1 for n in vivos if n.fome > limiar_fome),
            "saldo_zerado": sum(1 for n in adultos if n.dinheiro_total_pc <= 0),
            "mediana_saldo_pc": statistics.median(saldos_adultos) if saldos_adultos else 0.0,
        }

    def _contadores_do_dia(self) -> dict:
        """O02: zera `mundo.contadores` quando o dia simulado vira — comparado à
        última montagem, não a cada tick, então o corte real cai em algum instante
        dentro de `estatisticas_a_cada_ticks` do início do dia novo, não exatamente
        na meia-noite."""
        dia_atual = RelogioMundo.dia_do_mundo(self._mundo.data_simulada)
        resultado = {}
        if self._ultimo_dia is not None and dia_atual != self._ultimo_dia:
            resultado["dia_anterior"] = self._contadores_legiveis()
            self._mundo.contadores.clear()
        self._ultimo_dia = dia_atual
        resultado["hoje"] = self._contadores_legiveis()
        return resultado

    def _contadores_legiveis(self) -> dict:
        return {contador.value: self._mundo.contadores.get(contador, 0) for contador in ContadorMundo}


def formatar_resumo_console(estatisticas: dict) -> str:
    """O03: uma linha só, pura e testável — separada de `montar()` porque o
    console quer TEXTO e o painel quer o dict inteiro; formatar dentro do coletor
    misturaria as duas responsabilidades."""
    total = estatisticas["total"]
    desempenho = estatisticas.get("desempenho", {})
    vivos = sum(total["vivos_por_estagio"].values())
    hoje = estatisticas.get("hoje", {})
    nascimentos = hoje.get(ContadorMundo.NASCIMENTO.value, 0)
    obitos = hoje.get(ContadorMundo.OBITO_VELHICE.value, 0) + hoje.get(ContadorMundo.OBITO_SAUDE.value, 0)

    velocidade_efetiva = desempenho.get("velocidade_efetiva")
    velocidade_pedida = desempenho.get("velocidade_pedida")
    ms_por_tick = desempenho.get("ms_por_tick_medio")
    trecho_velocidade = (
        f"{velocidade_efetiva:.0f}× efetivo (pedido {velocidade_pedida:.0f}×)"
        if velocidade_efetiva is not None and velocidade_pedida is not None
        else "velocidade: medindo…"
    )
    trecho_tick = f"{ms_por_tick:.0f} ms/tick" if ms_por_tick is not None else "ms/tick: medindo…"

    return (
        f"📊 {trecho_velocidade} | {trecho_tick} | vivos {vivos:,} | "
        f"desempregados {total['desempregados']:,} | famintos {total['famintos']:,} | "
        f"hoje: +{nascimentos} nasc. / -{obitos} óbitos"
    ).replace(",", ".")
