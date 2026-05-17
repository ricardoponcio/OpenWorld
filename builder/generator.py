"""
SCRIPT: generator.py
FUNÇÃO: Gerador de Identidades e Personagens.
DESCRIÇÃO: Interface direta com a IA para criar nomes, backgrounds e atributos 
           para os habitantes, transformando 'NPCs' em personagens com história.
"""
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
    def ask_ai(prompt: str) -> str:
        """Método genérico para consultar a IA."""
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        try:
            req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode('utf-8'))
                return res['message']['content']
        except Exception as e:
            return f"Erro na IA: {e}"

    @staticmethod
    def generate_npc_dna(tema: str, loc_nome: str, loc_tipo: str, genero: str = 'M', nomes_excluidos: list = None) -> Optional[Dict]:
        """Gera um DNA único evitando nomes repetidos."""
        nomes_str = ", ".join(nomes_excluidos) if nomes_excluidos else "Nenhum"
        gen_ext = "MASCULINO" if genero == 'M' else "FEMININO"
        
        prompt = f"""
        Você é um mestre de RPG. Crie um habitante único para um mundo '{tema}'.
        REGRAS CRÍTICAS:
        1. Gênero OBRIGATÓRIO: {gen_ext}.
        2. NOME ÚNICO: Não use nomes da lista: [{nomes_str}].
        3. Local de Trabalho: {loc_nome} ({loc_tipo}).
        
        Retorne um JSON com:
        - nome: Nome e Sobrenome inéditos.
        - genero: Retorne exatamente '{genero}'.
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