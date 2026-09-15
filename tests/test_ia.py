"""
Testes do Bloco I (docs/16_PLANO_PAINEL_E_IA.md) — IA configurável, OpenRouter e
medição de custo. Nenhum teste deste arquivo toca rede: `ProvedorOpenAICompativel`
recebe `transporte` injetado, `RoteadorIA` recebe `fabrica_provedor`/`ambiente`
injetados, `LimitadorDeTaxa` recebe `relogio` injetado.
"""
import pytest

from engine.ai.clientes import ClienteIA, resolver_config_cliente, validar_config_ia


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
