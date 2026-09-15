import json
from typing import Dict
from .client import AIClient, ErroIAIndisponivel
from .clientes import ClienteIA
from .utils import AIUtils
from .fallbacks import AIFallbacks
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
            # I11 (docs/16_PLANO_PAINEL_E_IA.md): sem indentação — mesmo conteúdo, ~5%
            # menos entrada pro contexto do Ollama local (janela apertada, Seção 2.7).
            prompt = template.format(
                tema=tema,
                contexto_json=json.dumps(contexto, ensure_ascii=False, separators=(",", ":"))
            )
            res = AIClient.query(prompt, cliente=ClienteIA.EVENTO_GLOBAL, json_format=True)

            data = AIUtils.parse_json_safely(res)
            if data and isinstance(data, dict) and "titulo" in data and "descricao" in data and "modificadores" in data:
                return data
        except (ErroIAIndisponivel, KeyError) as e:
            WorldLogger.warning(f"[AI-STORYTELLER] Ativando fallback para evento global: {e}")
            
        # Fallback procedural — sorteia o evento inteiro, não um índice acoplado ao
        # tamanho de uma lista escrita à mão (R-B12).
        return AIFallbacks.sortear_evento_global()
