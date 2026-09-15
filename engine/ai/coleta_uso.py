"""
MODULE: coleta_uso.py
FUNÇÃO: Registro de uso de IA em JSONL — uma linha por chamada, sucesso ou
    falha, inclusive as tentativas puladas (I06, docs/16_PLANO_PAINEL_E_IA.md).
    O script de estimativa de custo (I07) lê este arquivo; os campos de
    `RegistroUsoIA` são o contrato entre os dois.
"""
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from engine.caminhos import na_raiz
from engine.logger import WorldLogger


class ResultadoChamadaIA(Enum):
    SUCESSO = "sucesso"
    # I11: tokens_entrada bateu ou passou de contexto_tokens_servidor — a
    # resposta provavelmente foi gerada com o prompt cortado.
    SUCESSO_TRUNCADO = "sucesso_truncado"
    LIMITE_TAXA = "limite_taxa"
    INDISPONIVEL = "indisponivel"
    ERRO_CONFIGURACAO = "erro_configuracao"
    PULADO_LIMITADOR = "pulado_limitador"
    PULADO_SEM_CHAVE = "pulado_sem_chave"


@dataclass
class RegistroUsoIA:
    """Uma linha do JSONL — campos EXATOS (contrato de `estimar_custo_ia.py`,
    I07)."""
    ts: str                                  # datetime.now(timezone.utc).isoformat() — tempo real
    cliente: str                             # ClienteIA.value
    provedor: str                            # nome em ia.provedores
    modelo: str
    tentativa: int                           # 1, 2, ... dentro do provedor
    resultado: str                           # ResultadoChamadaIA.value
    latencia_s: Optional[float]              # None quando pulado
    tokens_entrada: Optional[int]
    tokens_saida: Optional[int]
    tokens_estimados: bool                   # True quando não veio usage e os números são len(texto)/4
    custo_informado_usd: Optional[float]
    json_format: bool
    prompt: Optional[str]                    # None se gravar_texto for False
    resposta: Optional[str]                  # None se gravar_texto for False, ou se falhou
    erro: Optional[str]                      # mensagem curta, SEM a chave


def agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegistradorDeUsoIA:
    """`registrar` grava uma linha JSON por chamada, sob `threading.Lock` — o
    nome de bebê roda em thread própria, o DNA em ThreadPool (I08), então duas
    chamadas podem terminar ao mesmo tempo. `OSError` ao gravar não derruba a
    IA: a coleta é diagnóstico, não faz parte do caminho crítico — um único
    aviso e segue (ARQUITETURA §9)."""

    def __init__(self, arquivo: str, gravar_texto: bool, ativo: bool):
        self._caminho = na_raiz(arquivo)
        self._gravar_texto = gravar_texto
        self._ativo = ativo
        self._trava = threading.Lock()

    def registrar(self, registro: RegistroUsoIA) -> None:
        if not self._ativo:
            return
        dados = asdict(registro)
        if not self._gravar_texto:
            dados["prompt"] = None
            dados["resposta"] = None
        linha = json.dumps(dados, ensure_ascii=False)
        with self._trava:
            try:
                os.makedirs(os.path.dirname(self._caminho), exist_ok=True)
                with open(self._caminho, "a", encoding="utf-8") as f:
                    f.write(linha + "\n")
            except OSError as e:
                WorldLogger.warning(f"[IA] falha ao gravar uso em {self._caminho}: {e}")
