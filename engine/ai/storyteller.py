import random
import json
from typing import Dict
from .client import AIClient
from ai.utils import AIUtils
from ..logger import WorldLogger

class AIStorytellerClient:
    """
    Specialized client for high-level global narrative event weaving.
    """
    @staticmethod
    def gerar_evento_global(tema: str, contexto: Dict) -> Dict:
        """
        Generates global narrative event with robust JSON extraction and fallback protection.
        """
        try:
            template = AIClient.read_prompt("event.txt")
            prompt = template.format(
                tema=tema,
                contexto_json=json.dumps(contexto, indent=2)
            )
            res = AIClient.query(prompt, json_format=True, timeout=60.0)
            
            data = AIUtils.parse_json_safely(res)
            if data and isinstance(data, dict) and "titulo" in data and "descricao" in data and "modificadores" in data:
                return data
        except Exception as e:
            WorldLogger.warning(f"[AI-STORYTELLER] Ativando fallback para evento global: {e}")
            
        # Fallback procedural
        titulos = ["Nevasca Súbita", "Mercado Próspero", "Epidemia Leve", "Dia de Sol"]
        descricoes = [
            "Uma nevasca misteriosa cobre a vila de frio, dificultando movimentações na rua.",
            "Comerciantes de terras distantes chegam, trazendo oportunidades e prosperidade.",
            "Um resfriado sazonal se espalha, fazendo com que as pessoas prefiram descansar.",
            "Um dia extremamente ensolarado e alegre, perfeito para happy hour na taverna."
        ]
        idx = random.randint(0, 3)
        return {
            "titulo": titulos[idx],
            "descricao": descricoes[idx],
            "tipo": "METEOROLOGICO" if idx == 0 or idx == 3 else "ECONOMICO",
            "modificadores": {"SOCIALIZAR": 10 if idx == 3 else -5},
            "duracao_ticks": 6,
            "acoes_mundo": []
        }
