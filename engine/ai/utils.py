import re
import json
from typing import Optional, Union, Dict, List
from ..logger import WorldLogger

class AIUtils:
    """
    Central utility class to clean and parse LLM responses safely,
    deduplicating string manipulations across all specialized AI clients.
    """
    @staticmethod
    def clean_json_response(raw_text: str) -> str:
        """
        Removes markdown code blocks, comments, and extracts the core JSON boundary.
        """
        if not raw_text:
            return ""
            
        # 1. Remover blocos de código Markdown (```json ... ``` ou ```)
        cleaned = re.sub(r'```json\s*', '', raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'```\s*', '', cleaned)
        
        # 2. Remover comentários estilo // ... ou # ... de dentro do JSON
        cleaned = re.sub(r'//.*', '', cleaned)
        cleaned = re.sub(r'#.*', '', cleaned)
        
        # 3. Encontrar os limites reais do JSON (objeto {} ou array [])
        start_obj = cleaned.find('{')
        end_obj = cleaned.rfind('}')
        start_arr = cleaned.find('[')
        end_arr = cleaned.rfind(']')
        
        # Escolher a menor janela válida que abrange o JSON correto
        start_idx = -1
        end_idx = -1
        
        if start_obj != -1 and start_arr != -1:
            if start_obj < start_arr:
                start_idx = start_obj
                end_idx = end_obj
            else:
                start_idx = start_arr
                end_idx = end_arr
        elif start_obj != -1:
            start_idx = start_obj
            end_idx = end_obj
        elif start_arr != -1:
            start_idx = start_arr
            end_idx = end_arr
            
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return cleaned[start_idx:end_idx+1].strip()
            
        return cleaned.strip()

    @staticmethod
    def parse_json_safely(raw_text: str) -> Optional[Union[Dict, List]]:
        """
        Attempts to clean and parse the LLM raw text response into a JSON object.
        Returns None if parsing fails.
        """
        cleaned = AIUtils.clean_json_response(raw_text)
        try:
            return json.loads(cleaned)
        except Exception as e:
            WorldLogger.warning(f"[AI-UTILS] Falha ao decodificar JSON após limpeza: {e}")
            WorldLogger.debug(f"[AI-UTILS] Conteúdo bruto: {raw_text} | Limpo: {cleaned}")
            return None
