import json
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.append(raiz)

from ai.client import AIClient
from ai.utils import AIUtils
from engine.logger import WorldLogger

class WorldManagerAIClient:
    """
    Specialized AI client for generating high-level geographical continental layouts
    and regional metadata for OpenWorld's Tiled Cartographer.
    """
    @staticmethod
    def planejar_continentes(semente: int, tamanho_global: int = 768) -> dict:
        """
        Queries the local LLM to plan the distribution, sizing, irregularity, 
        and climate modification properties of continents.
        """
        try:
            # Caminho absoluto seguro para o prompt/world_map_generation.txt
            dir_ai = os.path.dirname(os.path.abspath(__file__))
            caminho_prompt = os.path.join(dir_ai, "prompt", "world_map_generation.txt")
            
            with open(caminho_prompt, "r", encoding="utf-8") as f:
                prompt_template = f.read()
                
            # Substitui as variáveis específicas no template do prompt de forma robusta e segura
            prompt = prompt_template.replace("{semente}", str(semente)).replace("{limite}", str(tamanho_global - 150))
            
            WorldLogger.info(f"[AI-WORLD-STRATEGY] Planejando continentes com a semente: {semente}...")
            res = AIClient.query(prompt, json_format=True, timeout=120.0)
            
            # Limpeza e parsing de JSON robustos e seguros via AIUtils global
            data = AIUtils.parse_json_safely(res)
            
            if data and "continentes" in data and isinstance(data["continentes"], list) and len(data["continentes"]) > 0:
                WorldLogger.info(f"[AI-WORLD-STRATEGY] {len(data['continentes'])} continentes planejados com sucesso pela IA!")
                return data
            raise ValueError("Resposta da IA formatada incorretamente ou vazia.")
        except Exception as e:
            WorldLogger.warning(f"[AI-WORLD-STRATEGY] Falha ao consultar IA Ollama: {e}. Usando fallback determinístico.")
            
        # Fallback procedural determinístico baseado na semente
        import random
        random.seed(semente)
        num_continentes = random.randint(3, 5)
        continentes = []
        nomes = ["Eldoria", "Aridia", "Gondwana", "Bravia", "Arquipélago Azul"]
        perfis = ["Alpino", "Platô", "Arquipélago", "Erosivo"]
        
        for i in range(num_continentes):
            continentes.append({
                "nome": nomes[i % len(nomes)],
                "centro_x": random.randint(200, tamanho_global - 200),
                "centro_y": random.randint(200, tamanho_global - 200),
                "area_km2": random.randint(1000000, 6000000),
                "raio_visual": random.randint(150, 250),
                "irregularidade": random.uniform(0.3, 0.6),
                "elevacao_maxima": random.uniform(0.7, 0.95),
                "perfil_geologico": perfis[i % len(perfis)],
                "modificadores": {
                    "calor": random.uniform(-0.15, 0.15),
                    "umidade": random.uniform(-0.15, 0.15)
                }
            })
            
        return {"continentes": continentes}
