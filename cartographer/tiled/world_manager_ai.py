import json
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.append(raiz)

from ai.client import AIClient
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
        prompt = f"""
        Você é um Gerador Geográfico Estratégico para um RPG de fantasia em um mundo composto por tiles.
        Sua tarefa é planejar a silhueta das massas de terra de forma criativa com base na semente determinística: {semente}.
        
        Gere um JSON com uma lista de continentes (entre 2 e 4). Cada continente deve ter:
        - "nome": Nome fictício do continente (Ex: "Aridia", "Eldoria").
        - "centro_x": Coordenada X global do centro (entre 150 e {tamanho_global - 150}).
        - "centro_y": Coordenada Y global do centro (entre 150 e {tamanho_global - 150}).
        - "raio": Raio de influência da massa de terra (entre 120 e 280 pixels).
        - "irregularidade": Coeficiente de deformidade da costa (entre 0.2 e 0.6).
        - "modificador_calor": Modificador térmico regional (entre -0.25 e +0.25).
        - "modificador_umidade": Modificador de umidade regional (entre -0.25 e +0.25).

        Responda ESTRITAMENTE em formato JSON puro, sem comentários, sem markdown extras, como no modelo abaixo:
        {{
            "continentes": [
                {{
                    "nome": "Eldoria",
                    "centro_x": 250,
                    "centro_y": 280,
                    "raio": 180,
                    "irregularidade": 0.4,
                    "modificador_calor": 0.05,
                    "modificador_umidade": 0.15
                }}
            ]
        }}
        """
        try:
            WorldLogger.info(f"[AI-WORLD-STRATEGY] Planejando continentes com a semente: {semente}...")
            res = AIClient.query(prompt, json_format=True, timeout=120.0)
            
            # Limpeza rápida se o LLM enviar com ```json ou markdown
            if "```" in res:
                res = res.split("```")[1]
                if res.startswith("json"):
                    res = res[4:]
            res = res.strip()
            
            data = json.loads(res)
            if "continentes" in data and isinstance(data["continentes"], list) and len(data["continentes"]) > 0:
                WorldLogger.info(f"[AI-WORLD-STRATEGY] {len(data['continentes'])} continentes planejados com sucesso pela IA!")
                return data
        except Exception as e:
            WorldLogger.warning(f"[AI-WORLD-STRATEGY] Falha ao consultar IA Ollama: {e}. Usando fallback determinístico.")
            
        # Fallback procedural determinístico baseado na semente
        import random
        random.seed(semente)
        num_continentes = random.randint(2, 3)
        continentes = []
        nomes = ["Eldoria", "Aridia", "Terras Geladas", "Bravia", "Arquipélago Coral"]
        
        for i in range(num_continentes):
            continentes.append({
                "nome": nomes[i % len(nomes)],
                "centro_x": random.randint(200, tamanho_global - 200),
                "centro_y": random.randint(200, tamanho_global - 200),
                "raio": random.randint(150, 250),
                "irregularidade": random.uniform(0.3, 0.5),
                "modificador_calor": random.uniform(-0.15, 0.15),
                "modificador_umidade": random.uniform(-0.15, 0.15)
            })
            
        return {"continentes": continentes}
