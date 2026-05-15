import json
import urllib.request
import re
from typing import Optional, Dict

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5-coder:7b" # Ou o seu modelo preferido (llama3, mistral, etc)

class AIWorldGenerator:
    @staticmethod
    def generate_city_locations(tema: str, quantidade: int) -> Optional[list]:
        """Gera uma lista dinâmica de locais temáticos para a cidade."""
        prompt = f"""
        Você é um arquiteto de mundos lendários. Com base no tema '{tema}', invente EXATAMENTE {quantidade} locais urbanos únicos.
        
        REGRAS:
        1. Distribua entre locais de trabalho (indústria, comércio, magia) e pelo menos 2 locais sociais.
        2. Tipos permitidos: Campo, Oficina, Social, Magia, Mar, Loja, Defesa.
        3. Retorne um JSON com a lista de objetos: {{"nome": "Nome", "tipo": "Tipo", "descricao": "desc"}}.
        """

        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json"
        }
        try:
            req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode('utf-8'))
                return json.loads(res['message']['content'])
        except Exception as e:
            print(f"⚠️ Erro ao gerar locais via IA: {e}")
            return None

    @staticmethod
    def generate_npc_dna(tema: str, loc_nome: str, loc_tipo: str) -> Optional[Dict]:
        """Gera um DNA único e um CARGO específico para o local."""
        prompt = f"""
        Crie um habitante para um mundo com o tema: {tema}.
        Este habitante trabalha no local: {loc_nome} (Tipo: {loc_tipo}).
        
        Retorne um JSON com:
        - nome: Nome completo.
        - raca: Raça condizente.
        - cargo: Um cargo específico (Ex: Mestre Ferreiro, Aprendiz, Guarda, Alquimista).
        - personalidade: Uma frase.
        - background: Uma frase.
        """

        
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json"
        }
        
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode('utf-8'))
                content = res['message']['content']
                return json.loads(content)
        except Exception as e:
            print(f"⚠️ Erro ao falar com Ollama (Certifique-se que o serviço está rodando): {e}")
            return None