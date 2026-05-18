import os
import json
import urllib.request
import urllib.error
import time
from ..logger import WorldLogger

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5-coder:7b"

class AIClient:
    """
    Base low-level AI Client.
    Handles communication with local Ollama service, robust retries with backoff,
    detailed performance logging, and central configuration.
    """
    @staticmethod
    def query(prompt: str, json_format: bool = False, max_retries: int = 3, timeout: float = 15.0) -> str:
        """
        Sends a generic text prompt to the LLM with automatic retries and exponential backoff.
        """
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        if json_format:
            payload["format"] = "json"

        data_bytes = json.dumps(payload).encode('utf-8')
        backoff = 1.0
        
        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            try:
                req = urllib.request.Request(
                    OLLAMA_URL, 
                    data=data_bytes, 
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    content = res_body['message']['content'].strip()
                    duration = time.time() - start_time
                    WorldLogger.debug(f"[AI] Requisição bem-sucedida em {duration:.2f}s (Tentativa {attempt})")
                    return content
            except urllib.error.URLError as e:
                duration = time.time() - start_time
                WorldLogger.warning(f"[AI] Erro de rede/conexão na tentativa {attempt}/{max_retries} ({duration:.2f}s): {e}")
            except Exception as e:
                duration = time.time() - start_time
                WorldLogger.warning(f"[AI] Erro inesperado na tentativa {attempt}/{max_retries} ({duration:.2f}s): {e}")
            
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2.0
                
        raise ConnectionError("O serviço local de IA está offline ou indisponível após múltiplas tentativas.")

    @staticmethod
    def read_prompt(filename: str) -> str:
        """Reads a prompt template file from the prompts subdirectory."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, "prompts", filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
