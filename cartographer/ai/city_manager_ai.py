import os
from engine.logger import WorldLogger
from ai.client import AIClient
from ai.utils import AIUtils

class CityManagerAIClient:
    """
    Client especializado para geração de metadados e fundação de cidades via LLM.
    """
    @staticmethod
    def generate_cities_for_continent(nome_continente: str, biomas_disponiveis: list, min_cidades: int, max_cidades: int, model_name: str = "qwen2.5-coder:7b"):
        try:
            dir_ai = os.path.dirname(os.path.abspath(__file__))
            caminho_prompt = os.path.join(dir_ai, "prompt", "city_generation.txt")
            
            with open(caminho_prompt, "r", encoding="utf-8") as f:
                prompt_template = f.read()
                
            biomas_str = ", ".join(biomas_disponiveis)
            prompt = prompt_template.replace("{continente}", nome_continente)
            prompt = prompt.replace("{min_cidades}", str(min_cidades))
            prompt = prompt.replace("{max_cidades}", str(max_cidades))
            prompt = prompt.replace("{biomas_str}", biomas_str)
            
            WorldLogger.info(f"[AI-CITY-STRATEGY] Fundando cidades para o continente {nome_continente} usando modelo {model_name}...")
            res = AIClient.query(prompt, json_format=True, timeout=120.0, model_name=model_name)
            
            data = AIUtils.parse_json_safely(res)
            
            if isinstance(data, dict):
                data = [data]
                
            if data and isinstance(data, list) and len(data) > 0:
                WorldLogger.info(f"[AI-CITY-STRATEGY] {len(data)} cidades fundadas com sucesso!")
                return data
            
            raise ValueError("Resposta da IA formatada incorretamente ou vazia.")
            
        except Exception as e:
            WorldLogger.error(f"[AI-CITY-STRATEGY] Falha ao consultar IA: {e}")
            raise e
