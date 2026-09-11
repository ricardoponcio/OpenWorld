import os
import random
import zlib
from engine.logger import WorldLogger
from engine.ai.client import AIClient
from engine.ai.utils import AIUtils

# Fase 1.4 (P1.4): fallback procedural — o mesmo padrão de tabela de sílabas usado
# implicitamente em outros fallbacks do projeto (nomes fixos em world_manager_ai.py), aqui
# generativo porque cidade precisa de mais nomes distintos do que continente.
_SILABAS_INICIO = ["Val", "Bel", "Cor", "Dra", "El", "Fen", "Gal", "Hel", "Ir", "Jor",
                    "Kel", "Lor", "Mar", "Nor", "Or", "Pel", "Quen", "Ren", "Sil", "Tor"]
_SILABAS_MEIO = ["a", "an", "en", "in", "or", "ar", "el", "dor", "ver", "mir"]
_SILABAS_FIM = ["dor", "via", "burgo", "ford", "vale", "port", "stead", "mont", "field", "haven"]

_TAMANHOS = ["pequeno", "medio", "grande"]
_TIPOS = ["pesqueira", "agricola", "comercial", "fortaleza", "mistica", "mineira", "portuaria"]


def _nome_procedural(rng):
    return rng.choice(_SILABAS_INICIO) + rng.choice(_SILABAS_MEIO) + rng.choice(_SILABAS_FIM)


def _cidade_procedural(rng, biomas_disponiveis):
    return {
        "nome": _nome_procedural(rng),
        "tamanho": rng.choice(_TAMANHOS),
        "tipo": rng.choice(_TIPOS),
        "bioma_desejado": rng.choice(biomas_disponiveis),
    }


class CityManagerAIClient:
    """
    Client especializado para geração de metadados e fundação de cidades via LLM.
    """

    @staticmethod
    def _validar_cidades(data, biomas_disponiveis):
        """
        Fase 1.4 (P1.4): a IA (7B, sem garantia nenhuma) pode devolver campo faltando,
        `bioma_desejado` fora da lista fechada ou `tamanho` fora do enum. Descarta o que
        não presta em vez de deixar passar pro resto do pipeline — "Python decide
        geometria" também vale pra validar dado estruturado da IA.
        """
        biomas_validos = {b.lower() for b in biomas_disponiveis}
        validas = []
        for c in data if isinstance(data, list) else []:
            if not isinstance(c, dict):
                continue
            if not all(k in c and c[k] for k in ("nome", "tamanho", "tipo", "bioma_desejado")):
                continue
            if c["tamanho"] not in _TAMANHOS:
                continue
            if c["bioma_desejado"].lower() not in biomas_validos:
                continue
            validas.append(c)
        return validas

    @staticmethod
    def generate_cities_for_continent(nome_continente: str, biomas_disponiveis: list, min_cidades: int,
                                       max_cidades: int, model_name: str = "qwen2.5-coder:7b", retries: int = 2):
        """
        Fase 1.4 (P1.4): antes, uma falha ou resposta curta da IA matava o processo
        inteiro (`raise e` sem retry, sem fallback). Agora tenta até `retries` vezes,
        validando e descartando cidades malformadas a cada tentativa; se ainda faltar
        depois de todas as tentativas, completa proceduralmente até `min_cidades` — o
        continente NUNCA fica sem cidade suficiente só porque o modelo 7B teve um dia ruim.
        """
        dir_ai = os.path.dirname(os.path.abspath(__file__))
        caminho_prompt = os.path.join(dir_ai, "prompt", "city_generation.txt")
        with open(caminho_prompt, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        biomas_str = ", ".join(biomas_disponiveis)
        prompt = prompt_template.replace("{continente}", nome_continente)
        prompt = prompt.replace("{min_cidades}", str(min_cidades))
        prompt = prompt.replace("{max_cidades}", str(max_cidades))
        prompt = prompt.replace("{biomas_str}", biomas_str)

        cidades_validas = []
        for tentativa in range(retries + 1):
            try:
                WorldLogger.info(
                    f"[AI-CITY-STRATEGY] Fundando cidades para {nome_continente} "
                    f"(tentativa {tentativa + 1}/{retries + 1})..."
                )
                res = AIClient.query(prompt, json_format=True, timeout=120.0, model_name=model_name)
                data = AIUtils.parse_json_safely(res)
                if isinstance(data, dict):
                    data = [data]
                cidades_validas = CityManagerAIClient._validar_cidades(data, biomas_disponiveis)
                if len(cidades_validas) >= min_cidades:
                    WorldLogger.info(f"[AI-CITY-STRATEGY] {len(cidades_validas)} cidades válidas!")
                    return cidades_validas[:max_cidades]
                WorldLogger.warning(
                    f"[AI-CITY-STRATEGY] Só {len(cidades_validas)} cidade(s) válida(s) "
                    f"(< mínimo {min_cidades}) na tentativa {tentativa + 1}."
                )
            except Exception as e:
                WorldLogger.warning(f"[AI-CITY-STRATEGY] Falha na tentativa {tentativa + 1}: {e}")

        # Fallback procedural determinístico — nunca hash() (aleatorizado por processo,
        # mesmo achado #7 de outros fallbacks do projeto). Completa só o que falta,
        # preservando as cidades válidas que a IA já tiver fundado.
        faltam = min_cidades - len(cidades_validas)
        WorldLogger.warning(
            f"[AI-CITY-STRATEGY] Completando {faltam} cidade(s) proceduralmente pra {nome_continente}."
        )
        seed = zlib.crc32(nome_continente.encode("utf-8"))
        rng = random.Random(seed)
        nomes_usados = {c["nome"] for c in cidades_validas}
        while len(cidades_validas) < min_cidades:
            nova = _cidade_procedural(rng, biomas_disponiveis)
            if nova["nome"] in nomes_usados:
                continue
            nomes_usados.add(nova["nome"])
            cidades_validas.append(nova)

        return cidades_validas[:max_cidades]
