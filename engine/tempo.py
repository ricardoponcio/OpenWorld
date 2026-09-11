"""
MODULE: tempo.py
FUNÇÃO: Origem do calendário do mundo e formatação de data simulada.

DESCRIÇÃO:
    Ponto único do "Dia 1" do mundo. Antes desta classe, `datetime(1200,1,1)` estava
    escrito à mão em 8 arquivos, com horas divergentes entre eles (0,0 pra contar dias;
    6,0 como hora de início da simulação; '1200-01-01T06:00:00' como string no
    dashboard) — mudar a época exigiria caçar todas e acertar cada uma (R-B07).
"""
from datetime import datetime


class RelogioMundo:
    EPOCA = datetime(1200, 1, 1, 0, 0)
    HORA_INICIAL_PADRAO = datetime(1200, 1, 1, 6, 0)
    HORA_INICIAL_PADRAO_ISO = HORA_INICIAL_PADRAO.isoformat()
    ANOS_DE_VIDA_DE_REFERENCIA = 80.0  # ver R-B08 — escala de dias simulados -> "anos" narrativos

    @staticmethod
    def dia_do_mundo(data_simulada: datetime) -> int:
        return (data_simulada - RelogioMundo.EPOCA).days + 1

    @staticmethod
    def timestamp_rpg(data_simulada: datetime) -> str:
        """'Dia 42, 14:30' — o carimbo usado em todo Evento persistido."""
        return f"Dia {RelogioMundo.dia_do_mundo(data_simulada)}, {data_simulada.strftime('%H:%M')}"

    @staticmethod
    def idade_em_anos(data_nascimento_iso: str, agora: datetime, dias_ate_a_morte: int) -> int:
        """Converte a idade em dias simulados para 'anos' narrativos, escalando pelo
        tempo de vida configurado (`ANOS_DE_VIDA_DE_REFERENCIA`). Retorna 0 se a data de
        nascimento for inválida ou ausente."""
        if not data_nascimento_iso:
            return 0
        try:
            # Dado legado grava com espaço em vez de 'T' como separador — normaliza
            # antes de parsear, mesma tolerância que o código anterior já tinha.
            nascimento = datetime.fromisoformat(data_nascimento_iso.replace(' ', 'T'))
        except ValueError:
            return 0
        idade_dias = (agora - nascimento).days
        if dias_ate_a_morte <= 0:
            return 0
        return int((idade_dias / dias_ate_a_morte) * RelogioMundo.ANOS_DE_VIDA_DE_REFERENCIA)
