"""
MODULE: openai_compativel.py
FUNÇÃO: Fala com qualquer provedor no formato OpenAI /chat/completions (I02,
    docs/16_PLANO_PAINEL_E_IA.md) — o Ollama também aceita, em /v1.

DESCRIÇÃO:
    `transporte` é INJETADO (ARQUITETURA §7): uma função
    `(url, corpo_bytes, cabecalhos, timeout) -> (status_http, corpo_bytes)`. O
    default usa `urllib.request` (sem dependência nova no requirements.txt) —
    isso é o que permite testar `completar()` inteiro sem rede: um transporte
    falso simplesmente devolve a tupla que o teste quer, sem precisar montar um
    `HTTPError` de verdade. A classificação de erro (429/4xx/5xx/corpo vazio)
    acontece toda em `completar()`, a partir do status devolvido — não de tipos
    de exceção do urllib (esses só existem dentro do transporte default).
"""
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class RespostaIA:
    texto: str
    tokens_entrada: Optional[int]      # usage.prompt_tokens
    tokens_saida: Optional[int]        # usage.completion_tokens
    custo_informado_usd: Optional[float]  # usage.cost (o OpenRouter manda; o Ollama não)
    latencia_s: float


@dataclass
class PedidoIA:
    """Agrupa os parâmetros de uma chamada — método com 1 parâmetro, não 4
    (ARQUITETURA §4, limite de 5)."""
    prompt: str
    modelo: str
    json_format: bool
    timeout_s: float


class ErroLimiteDeTaxa(Exception):
    """HTTP 429 — o provedor pediu pra esperar."""


class ErroProvedorIndisponivel(Exception):
    """Rede, timeout, 5xx, ou uma resposta 200 sem conteúdo utilizável (sem
    `choices`, `content` vazio, ou `"error"` no corpo apesar do 200)."""


class ErroConfiguracaoProvedor(Exception):
    """400/401/403/404 — problema de configuração (chave errada, modelo
    inexistente...); tentar de novo não vai ajudar."""


def _transporte_urllib(url: str, corpo_bytes: bytes, cabecalhos: dict, timeout: float):
    """Transporte default (I02 passo 4) — sem dependência nova. `HTTPError` TEM
    status e corpo (é uma resposta de verdade, só que não-2xx); convertido na
    MESMA tupla `(status, corpo)` que uma resposta 2xx devolveria, pra quem
    decide o que fazer com o status ser só `completar()`. Erros SEM resposta
    nenhuma (recusa de conexão, DNS, timeout) propagam como exceção.

    ⚠️ `HTTPError` precisa ser capturado ANTES de um `except URLError` genérico
    — é subclasse dela; um `except URLError` sozinho engoliria o HTTPError
    também, perdendo o status/corpo que a classificação em completar() precisa."""
    req = urllib.request.Request(url, data=corpo_bytes, headers=cabecalhos, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resposta:
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ProvedorOpenAICompativel:
    def __init__(self, nome: str, url_base: str, chave_api: str, cabecalhos_extras: dict,
                 transporte: Callable = None):
        self.nome = nome
        self._url = f"{url_base.rstrip('/')}/chat/completions"
        self._chave_api = chave_api
        self._cabecalhos_extras = cabecalhos_extras
        self._transporte = transporte or _transporte_urllib

    def _montar_pedido(self, pedido: PedidoIA):
        corpo = {"model": pedido.modelo, "messages": [{"role": "user", "content": pedido.prompt}], "stream": False}
        if pedido.json_format:
            corpo["response_format"] = {"type": "json_object"}

        # A chave NUNCA aparece em log nem em mensagem de exceção (I02) — só entra
        # no cabeçalho HTTP em si, e só quando existe.
        cabecalhos = {"Content-Type": "application/json"}
        if self._chave_api:
            cabecalhos["Authorization"] = f"Bearer {self._chave_api}"
        cabecalhos.update(self._cabecalhos_extras)
        return json.dumps(corpo).encode("utf-8"), cabecalhos

    def _classificar_status(self, status: int, corpo_bytes: bytes) -> None:
        if status == 429:
            raise ErroLimiteDeTaxa(f"[{self.nome}] limite de taxa (429).")
        if status in (400, 401, 403, 404):
            raise ErroConfiguracaoProvedor(
                f"[{self.nome}] erro de configuração (HTTP {status}): "
                f"{corpo_bytes.decode('utf-8', 'replace')[:300]}")
        if status != 200:
            raise ErroProvedorIndisponivel(f"[{self.nome}] HTTP {status}.")

    def completar(self, pedido: PedidoIA) -> RespostaIA:
        corpo_bytes, cabecalhos = self._montar_pedido(pedido)

        inicio = time.monotonic()
        try:
            status, corpo_resposta = self._transporte(self._url, corpo_bytes, cabecalhos, pedido.timeout_s)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            raise ErroProvedorIndisponivel(f"[{self.nome}] provedor indisponível: {e}") from e
        latencia_s = time.monotonic() - inicio

        self._classificar_status(status, corpo_resposta)

        try:
            dados = json.loads(corpo_resposta)
        except json.JSONDecodeError as e:
            raise ErroProvedorIndisponivel(f"[{self.nome}] resposta não é JSON válido: {e}") from e

        if "error" in dados:
            raise ErroProvedorIndisponivel(f"[{self.nome}] resposta 200 com erro no corpo: {dados['error']}")
        escolhas = dados.get("choices")
        if not escolhas:
            raise ErroProvedorIndisponivel(f"[{self.nome}] resposta sem 'choices'.")
        texto = (escolhas[0].get("message") or {}).get("content")
        if not texto:
            raise ErroProvedorIndisponivel(f"[{self.nome}] conteúdo vazio na resposta.")

        uso = dados.get("usage") or {}
        return RespostaIA(
            texto=texto.strip(),
            tokens_entrada=uso.get("prompt_tokens"),
            tokens_saida=uso.get("completion_tokens"),
            custo_informado_usd=uso.get("cost"),
            latencia_s=latencia_s,
        )
