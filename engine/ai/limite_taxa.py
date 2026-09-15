"""
MODULE: limite_taxa.py
FUNÇÃO: Limite de taxa por provedor de IA — janela deslizante por minuto/dia, e
    pausa depois de um 429 (I03, docs/16_PLANO_PAINEL_E_IA.md).
"""
import threading
import time
from collections import deque
from typing import Callable, Optional


class LimitadorDeTaxa:
    """Seguro entre threads (o nome de bebê roda em thread própria, o DNA em
    ThreadPool — I08). `0` em `por_minuto`/`por_dia` = sem limite. `relogio` é
    injetado (`time.monotonic` por padrão) — testável sem `sleep` de verdade."""

    _JANELA_MINUTO_S = 60.0
    # Aproximação local: o "dia" do provedor pode virar em outro horário — não
    # medido (I03). O 429 de verdade é tratado por `pausar_por_limite`, não por
    # esta janela.
    _JANELA_DIA_S = 86400.0

    def __init__(self, por_minuto: int, por_dia: int, pausa_apos_limite_s: float,
                 relogio: Callable[[], float] = time.monotonic):
        self._por_minuto = por_minuto
        self._por_dia = por_dia
        self._pausa_apos_limite_s = pausa_apos_limite_s
        self._relogio = relogio
        self._chamadas_minuto: deque = deque()
        self._chamadas_dia: deque = deque()
        self._pausado_ate: Optional[float] = None
        self._trava = threading.Lock()

    def _descartar_antigas(self, agora: float) -> None:
        while self._chamadas_minuto and agora - self._chamadas_minuto[0] > self._JANELA_MINUTO_S:
            self._chamadas_minuto.popleft()
        while self._chamadas_dia and agora - self._chamadas_dia[0] > self._JANELA_DIA_S:
            self._chamadas_dia.popleft()

    def pode_chamar(self) -> bool:
        """Não consome — só responde se uma chamada agora seria permitida."""
        with self._trava:
            agora = self._relogio()
            if self._pausado_ate is not None and agora < self._pausado_ate:
                return False
            self._descartar_antigas(agora)
            if self._por_minuto > 0 and len(self._chamadas_minuto) >= self._por_minuto:
                return False
            if self._por_dia > 0 and len(self._chamadas_dia) >= self._por_dia:
                return False
            return True

    def registrar_chamada(self) -> None:
        with self._trava:
            agora = self._relogio()
            self._chamadas_minuto.append(agora)
            self._chamadas_dia.append(agora)

    def pausar_por_limite(self) -> None:
        """Chamado ao receber 429 — bloqueia `pode_chamar()` pelos próximos
        `pausa_apos_limite_s`, além (não em vez) das janelas de minuto/dia."""
        with self._trava:
            self._pausado_ate = self._relogio() + self._pausa_apos_limite_s
