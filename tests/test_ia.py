"""
Testes do Bloco I (docs/16_PLANO_PAINEL_E_IA.md) — IA configurável, OpenRouter e
medição de custo. Nenhum teste deste arquivo toca rede: `ProvedorOpenAICompativel`
recebe `transporte` injetado, `RoteadorIA` recebe `fabrica_provedor`/`ambiente`
injetados, `LimitadorDeTaxa` recebe `relogio` injetado.
"""
import json
import os
import threading

import pytest

from engine.ai.clientes import ClienteIA, resolver_config_cliente, validar_config_ia
from engine.ai.coleta_uso import RegistradorDeUsoIA, RegistroUsoIA, agora_utc_iso
from engine.ai.limite_taxa import LimitadorDeTaxa
from engine.ai.provedores import (
    ErroConfiguracaoProvedor,
    ErroLimiteDeTaxa,
    ErroProvedorIndisponivel,
    PedidoIA,
    ProvedorOpenAICompativel,
)


def _config_ia_valida():
    """Uma config.json['ia'] mínima e válida — cada teste copia e quebra um pedaço."""
    return {
        "provedores": {
            "ollama_local": {"url_base": "http://localhost:11434/v1", "chave_api_env": "",
                              "requisicoes_por_minuto": 0, "requisicoes_por_dia": 0,
                              "pausa_apos_limite_s": 0, "cabecalhos_extras": {}},
            "openrouter": {"url_base": "https://openrouter.ai/api/v1", "chave_api_env": "OPENROUTER_API_KEY",
                           "requisicoes_por_minuto": 20, "requisicoes_por_dia": 50,
                           "pausa_apos_limite_s": 60, "cabecalhos_extras": {}},
        },
        "padrao": {
            "cadeia": [{"provedor": "openrouter", "modelo": "modelo-a"},
                       {"provedor": "ollama_local", "modelo": "modelo-b"}],
            "timeout_s": 60, "tentativas_por_provedor": 2, "backoff_inicial_s": 1.0,
        },
        "clientes": {cliente.value: {} for cliente in ClienteIA},
    }


def test_cliente_sem_entrada_no_config_falha_alto():
    config = _config_ia_valida()
    del config["clientes"][ClienteIA.MESTRE.value]
    with pytest.raises(ValueError, match="mestre"):
        resolver_config_cliente(config, ClienteIA.MESTRE)


def test_cliente_vazio_herda_o_padrao():
    config = _config_ia_valida()
    efetiva = resolver_config_cliente(config, ClienteIA.LOCAIS_CIDADE)
    assert efetiva == config["padrao"]


def test_sobrescrita_de_cadeia_substitui_a_lista():
    config = _config_ia_valida()
    config["clientes"][ClienteIA.NOME_BEBE.value] = {
        "cadeia": [{"provedor": "ollama_local", "modelo": "modelo-c"}], "timeout_s": 8,
    }
    efetiva = resolver_config_cliente(config, ClienteIA.NOME_BEBE)
    assert efetiva["cadeia"] == [{"provedor": "ollama_local", "modelo": "modelo-c"}]
    assert efetiva["timeout_s"] == 8
    assert efetiva["tentativas_por_provedor"] == 2  # herdado do padrão, não apagado


def test_cadeia_com_provedor_inexistente_falha_alto():
    config = _config_ia_valida()
    config["clientes"][ClienteIA.DNA_NPC.value] = {
        "cadeia": [{"provedor": "provedor_fantasma", "modelo": "x"}],
    }
    with pytest.raises(ValueError, match="provedor_fantasma"):
        validar_config_ia(config)


def test_validar_config_ia_aceita_a_config_padrao_valida():
    validar_config_ia(_config_ia_valida())  # não levanta


def test_validar_config_ia_rejeita_timeout_zero():
    config = _config_ia_valida()
    config["clientes"][ClienteIA.MESTRE.value] = {"timeout_s": 0}
    with pytest.raises(ValueError, match="timeout_s"):
        validar_config_ia(config)


def test_validar_config_ia_rejeita_zero_tentativas():
    config = _config_ia_valida()
    config["clientes"][ClienteIA.MESTRE.value] = {"tentativas_por_provedor": 0}
    with pytest.raises(ValueError, match="tentativas_por_provedor"):
        validar_config_ia(config)


# ----------------------------------------------------------------------
# I02 — ProvedorOpenAICompativel (transporte falso, nenhuma rede)
# ----------------------------------------------------------------------

class _TransporteFalso:
    """Grava a última chamada (pra inspecionar corpo/cabeçalhos) e devolve a
    resposta configurada — o contrato de `transporte` é `(status, corpo_bytes)`,
    nunca uma exceção do urllib (essas só existem dentro do transporte default)."""
    def __init__(self, status, corpo_bytes):
        self.status = status
        self.corpo_bytes = corpo_bytes
        self.ultima_chamada = None

    def __call__(self, url, corpo_bytes, cabecalhos, timeout):
        self.ultima_chamada = {"url": url, "corpo": json.loads(corpo_bytes),
                                "cabecalhos": cabecalhos, "timeout": timeout}
        return self.status, self.corpo_bytes


def _resposta_ok(texto="ok", usage=None):
    corpo = {"choices": [{"message": {"content": texto}}]}
    if usage:
        corpo["usage"] = usage
    return json.dumps(corpo).encode("utf-8")


def test_provedor_envia_response_format_so_quando_json():
    transporte = _TransporteFalso(200, _resposta_ok())
    provedor = ProvedorOpenAICompativel("teste", "http://x", "", {}, transporte=transporte)

    provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))
    assert "response_format" not in transporte.ultima_chamada["corpo"]

    provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=True, timeout_s=10))
    assert transporte.ultima_chamada["corpo"]["response_format"] == {"type": "json_object"}


def test_provedor_sem_chave_nao_envia_authorization():
    transporte = _TransporteFalso(200, _resposta_ok())
    provedor = ProvedorOpenAICompativel("teste", "http://x", "", {}, transporte=transporte)
    provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))
    assert "Authorization" not in transporte.ultima_chamada["cabecalhos"]


def test_provedor_com_chave_envia_authorization():
    transporte = _TransporteFalso(200, _resposta_ok())
    provedor = ProvedorOpenAICompativel("teste", "http://x", "minha-chave-secreta", {}, transporte=transporte)
    provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))
    assert transporte.ultima_chamada["cabecalhos"]["Authorization"] == "Bearer minha-chave-secreta"


def test_provedor_le_usage_e_custo():
    uso = {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.001}
    transporte = _TransporteFalso(200, _resposta_ok("resposta", uso))
    provedor = ProvedorOpenAICompativel("teste", "http://x", "", {}, transporte=transporte)
    resp = provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))
    assert resp.texto == "resposta"
    assert resp.tokens_entrada == 10
    assert resp.tokens_saida == 20
    assert resp.custo_informado_usd == 0.001


def test_provedor_429_vira_erro_limite_de_taxa():
    transporte = _TransporteFalso(429, b'{"error": "rate limited"}')
    provedor = ProvedorOpenAICompativel("teste", "http://x", "", {}, transporte=transporte)
    with pytest.raises(ErroLimiteDeTaxa):
        provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))


def test_provedor_401_vira_erro_de_configuracao_sem_vazar_chave():
    transporte = _TransporteFalso(401, b'{"error": "invalid api key sk-teste-12345"}')
    provedor = ProvedorOpenAICompativel("teste", "http://x", "chave-super-secreta", {}, transporte=transporte)
    with pytest.raises(ErroConfiguracaoProvedor) as exc_info:
        provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))
    assert "chave-super-secreta" not in str(exc_info.value)


def test_provedor_200_com_error_no_corpo_vira_indisponivel():
    transporte = _TransporteFalso(200, b'{"error": {"message": "modelo sobrecarregado"}}')
    provedor = ProvedorOpenAICompativel("teste", "http://x", "", {}, transporte=transporte)
    with pytest.raises(ErroProvedorIndisponivel):
        provedor.completar(PedidoIA(prompt="oi", modelo="m", json_format=False, timeout_s=10))


# ----------------------------------------------------------------------
# I03 — LimitadorDeTaxa (relógio falso, nenhum sleep de verdade)
# ----------------------------------------------------------------------

class _RelogioFalso:
    def __init__(self, inicio=0.0):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def avancar(self, segundos):
        self.agora += segundos


def test_limitador_bloqueia_a_21a_chamada_no_mesmo_minuto():
    relogio = _RelogioFalso()
    limitador = LimitadorDeTaxa(por_minuto=20, por_dia=0, pausa_apos_limite_s=60, relogio=relogio)
    for _ in range(20):
        assert limitador.pode_chamar()
        limitador.registrar_chamada()
    assert not limitador.pode_chamar()


def test_limitador_libera_depois_de_60s():
    relogio = _RelogioFalso()
    limitador = LimitadorDeTaxa(por_minuto=1, por_dia=0, pausa_apos_limite_s=60, relogio=relogio)
    assert limitador.pode_chamar()
    limitador.registrar_chamada()
    assert not limitador.pode_chamar()

    relogio.avancar(60.01)
    assert limitador.pode_chamar()


def test_limitador_pausa_apos_429():
    relogio = _RelogioFalso()
    limitador = LimitadorDeTaxa(por_minuto=0, por_dia=0, pausa_apos_limite_s=30, relogio=relogio)
    assert limitador.pode_chamar()

    limitador.pausar_por_limite()
    assert not limitador.pode_chamar()

    relogio.avancar(29.9)
    assert not limitador.pode_chamar()
    relogio.avancar(0.2)
    assert limitador.pode_chamar()


def test_limitador_zero_e_ilimitado():
    relogio = _RelogioFalso()
    limitador = LimitadorDeTaxa(por_minuto=0, por_dia=0, pausa_apos_limite_s=60, relogio=relogio)
    for _ in range(1000):
        assert limitador.pode_chamar()
        limitador.registrar_chamada()


# ----------------------------------------------------------------------
# I06 — RegistradorDeUsoIA (arquivo em tmp_path, nunca logs/ia_uso.jsonl real)
# ----------------------------------------------------------------------

def _registro(**overrides):
    base = dict(
        ts=agora_utc_iso(), cliente="mestre", provedor="ollama_local", modelo="m",
        tentativa=1, resultado="sucesso", latencia_s=1.0, tokens_entrada=10,
        tokens_saida=20, tokens_estimados=False, custo_informado_usd=None,
        json_format=True, prompt="um prompt", resposta="uma resposta", erro=None,
    )
    base.update(overrides)
    return RegistroUsoIA(**base)


def test_registrador_grava_uma_linha_json_por_chamada(tmp_path):
    arquivo = str(tmp_path / "ia_uso.jsonl")
    registrador = RegistradorDeUsoIA(arquivo=arquivo, gravar_texto=True, ativo=True)
    registrador.registrar(_registro())
    registrador.registrar(_registro(tentativa=2))

    linhas = open(arquivo, encoding="utf-8").read().splitlines()
    assert len(linhas) == 2
    dados = [json.loads(l) for l in linhas]
    assert dados[0]["cliente"] == "mestre"
    assert dados[1]["tentativa"] == 2


def test_registrador_sem_texto_nao_grava_prompt(tmp_path):
    arquivo = str(tmp_path / "ia_uso.jsonl")
    registrador = RegistradorDeUsoIA(arquivo=arquivo, gravar_texto=False, ativo=True)
    registrador.registrar(_registro(prompt="segredo", resposta="resposta"))

    dados = json.loads(open(arquivo, encoding="utf-8").read())
    assert dados["prompt"] is None
    assert dados["resposta"] is None


def test_registrador_e_seguro_entre_threads(tmp_path):
    arquivo = str(tmp_path / "ia_uso.jsonl")
    registrador = RegistradorDeUsoIA(arquivo=arquivo, gravar_texto=True, ativo=True)

    def gravar_50():
        for _ in range(50):
            registrador.registrar(_registro())

    threads = [threading.Thread(target=gravar_50) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    linhas = open(arquivo, encoding="utf-8").read().splitlines()
    assert len(linhas) == 500
    for linha in linhas:
        json.loads(linha)  # JSON válido — nenhuma linha corrompida por interleaving entre threads


def test_registrador_inativo_nao_grava_nada(tmp_path):
    arquivo = str(tmp_path / "ia_uso.jsonl")
    registrador = RegistradorDeUsoIA(arquivo=arquivo, gravar_texto=True, ativo=False)
    registrador.registrar(_registro())
    assert not os.path.exists(arquivo)
