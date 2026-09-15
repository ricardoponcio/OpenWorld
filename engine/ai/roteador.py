"""
MODULE: roteador.py
FUNÇÃO: Cadeia de fallback entre provedores de IA, por cliente (I04, docs/
    16_PLANO_PAINEL_E_IA.md) — inclui a detecção de contexto truncado (I11):
    é o mesmo lugar que já sabe o resultado de cada chamada.
"""
import os
import time
from typing import Callable, Mapping, Optional

from engine.logger import WorldLogger

from .clientes import ClienteIA, resolver_config_cliente, validar_config_ia
from .coleta_uso import RegistradorDeUsoIA, RegistroUsoIA, ResultadoChamadaIA, agora_utc_iso
from .limite_taxa import LimitadorDeTaxa
from .provedores import (
    ErroConfiguracaoProvedor,
    ErroLimiteDeTaxa,
    ErroProvedorIndisponivel,
    PedidoIA,
    ProvedorOpenAICompativel,
    RespostaIA,
)


class ErroIAIndisponivel(Exception):
    """Toda a cadeia do cliente falhou — o chamador usa o fallback procedural
    que já existe (AIFallbacks), exatamente como hoje."""


def _estimar_tokens(texto: Optional[str]) -> int:
    """~4 caracteres por token — só usado quando o provedor não manda `usage`
    (o Ollama não manda; o OpenRouter manda)."""
    return max(1, len(texto or "") // 4)


class RoteadorIA:
    def __init__(self, config: dict, registrador: RegistradorDeUsoIA,
                 fabrica_provedor: Callable = None, ambiente: Mapping = None):
        self._validar_config(config)
        self._config = config
        self._registrador = registrador
        self._ambiente = os.environ if ambiente is None else ambiente
        fabrica = fabrica_provedor or ProvedorOpenAICompativel

        self._provedores = {}
        self._limitadores = {}
        self._contexto_tokens_servidor = {}
        self._avisado_erro_configuracao = set()   # (provedor, modelo)
        self._avisado_truncado = set()             # cliente.value

        for nome, cfg in config["provedores"].items():
            self._limitadores[nome] = LimitadorDeTaxa(
                cfg["requisicoes_por_minuto"], cfg["requisicoes_por_dia"], cfg["pausa_apos_limite_s"])
            self._contexto_tokens_servidor[nome] = cfg.get("contexto_tokens_servidor", 0)
            self._provedores[nome] = self._criar_provedor(fabrica, nome, cfg)

    def _validar_config(self, config: dict) -> None:
        validar_config_ia(config)

    def _resolver_cliente(self, cliente: ClienteIA) -> dict:
        return resolver_config_cliente(self._config, cliente)

    def _criar_provedor(self, fabrica: Callable, nome: str, cfg: dict):
        chave_env = cfg.get("chave_api_env", "")
        chave = self._ambiente.get(chave_env, "") if chave_env else ""
        if chave_env and not chave:
            # Um único aviso na construção (não em toda chamada) — pulado
            # silenciosamente depois disso (I04 passo 1).
            WorldLogger.error(
                f"[IA] provedor {nome} sem chave: defina a variável {chave_env} — pulado em toda cadeia.")
            return None
        return fabrica(nome, cfg["url_base"], chave, cfg.get("cabecalhos_extras", {}))

    def consultar(self, prompt: str, cliente: ClienteIA, json_format: bool) -> str:
        cfg_cliente = self._resolver_cliente(cliente)
        for passo in cfg_cliente["cadeia"]:
            texto = self._tentar_provedor(prompt, cliente, json_format, cfg_cliente, passo)
            if texto is not None:
                return texto
        WorldLogger.warning(f"[IA] cadeia esgotada para {cliente.value}")
        raise ErroIAIndisponivel(f"Cadeia de IA esgotada para o cliente '{cliente.value}'.")

    def _tentar_provedor(self, prompt: str, cliente: ClienteIA, json_format: bool,
                          cfg_cliente: dict, passo: dict) -> Optional[str]:
        nome_provedor, modelo = passo["provedor"], passo["modelo"]
        provedor = self._provedores[nome_provedor]
        limitador = self._limitadores[nome_provedor]

        if provedor is None:
            self._registrar(cliente, nome_provedor, modelo, 1, ResultadoChamadaIA.PULADO_SEM_CHAVE, json_format, prompt)
            return None
        if not limitador.pode_chamar():
            self._registrar(cliente, nome_provedor, modelo, 1, ResultadoChamadaIA.PULADO_LIMITADOR, json_format, prompt)
            return None

        pedido = PedidoIA(prompt=prompt, modelo=modelo, json_format=json_format, timeout_s=cfg_cliente["timeout_s"])
        tentativas = cfg_cliente["tentativas_por_provedor"]
        for tentativa in range(1, tentativas + 1):
            limitador.registrar_chamada()
            try:
                resposta = provedor.completar(pedido)
            except ErroLimiteDeTaxa:
                limitador.pausar_por_limite()
                self._registrar(cliente, nome_provedor, modelo, tentativa, ResultadoChamadaIA.LIMITE_TAXA,
                                 json_format, prompt, erro="limite de taxa (429)")
                return None  # próximo provedor — sem backoff, o 429 já diz "não agora"
            except ErroProvedorIndisponivel as e:
                self._registrar(cliente, nome_provedor, modelo, tentativa, ResultadoChamadaIA.INDISPONIVEL,
                                 json_format, prompt, erro=str(e))
                if tentativa < tentativas:
                    time.sleep(cfg_cliente["backoff_inicial_s"] * (2 ** (tentativa - 1)))
                continue
            except ErroConfiguracaoProvedor as e:
                self._avisar_erro_configuracao(nome_provedor, modelo, e)
                self._registrar(cliente, nome_provedor, modelo, tentativa, ResultadoChamadaIA.ERRO_CONFIGURACAO,
                                 json_format, prompt, erro=str(e))
                return None  # próximo provedor — não vai melhorar tentando de novo

            return self._registrar_sucesso(resposta, cliente, nome_provedor, modelo, tentativa, json_format, prompt)
        return None

    def _avisar_erro_configuracao(self, nome_provedor: str, modelo: str, erro: Exception) -> None:
        chave = (nome_provedor, modelo)
        if chave not in self._avisado_erro_configuracao:
            self._avisado_erro_configuracao.add(chave)
            WorldLogger.error(f"[IA] {nome_provedor}/{modelo}: erro de configuração: {erro}")

    def _registrar_sucesso(self, resposta: RespostaIA, cliente: ClienteIA, nome_provedor: str, modelo: str,
                            tentativa: int, json_format: bool, prompt: str) -> str:
        tokens_estimados = resposta.tokens_entrada is None or resposta.tokens_saida is None
        tokens_entrada = resposta.tokens_entrada if resposta.tokens_entrada is not None else _estimar_tokens(prompt)
        tokens_saida = resposta.tokens_saida if resposta.tokens_saida is not None else _estimar_tokens(resposta.texto)

        # I11: contexto do servidor batido/estourado — a resposta provavelmente
        # veio de um prompt cortado, não do prompt inteiro.
        teto = self._contexto_tokens_servidor.get(nome_provedor, 0)
        resultado = ResultadoChamadaIA.SUCESSO
        if teto > 0 and tokens_entrada >= teto:
            resultado = ResultadoChamadaIA.SUCESSO_TRUNCADO
            if cliente.value not in self._avisado_truncado:
                self._avisado_truncado.add(cliente.value)
                WorldLogger.warning(
                    f"[IA] prompt de {cliente.value} atingiu o contexto do servidor {nome_provedor} "
                    f"({teto} tokens) — provável truncamento.")

        self._registrador.registrar(RegistroUsoIA(
            ts=agora_utc_iso(), cliente=cliente.value, provedor=nome_provedor, modelo=modelo,
            tentativa=tentativa, resultado=resultado.value, latencia_s=resposta.latencia_s,
            tokens_entrada=tokens_entrada, tokens_saida=tokens_saida, tokens_estimados=tokens_estimados,
            custo_informado_usd=resposta.custo_informado_usd, json_format=json_format,
            prompt=prompt, resposta=resposta.texto, erro=None))
        return resposta.texto

    def _registrar(self, cliente: ClienteIA, nome_provedor: str, modelo: str, tentativa: int,
                    resultado: ResultadoChamadaIA, json_format: bool, prompt: str,
                    erro: Optional[str] = None) -> None:
        self._registrador.registrar(RegistroUsoIA(
            ts=agora_utc_iso(), cliente=cliente.value, provedor=nome_provedor, modelo=modelo,
            tentativa=tentativa, resultado=resultado.value, latencia_s=None,
            tokens_entrada=None, tokens_saida=None, tokens_estimados=False,
            custo_informado_usd=None, json_format=json_format, prompt=prompt, resposta=None, erro=erro))
