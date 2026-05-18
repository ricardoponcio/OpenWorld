"""
SCRIPT: generator.py
FUNÇÃO: Gerador de Identidades e Personagens.
DESCRIÇÃO: Interface direta com a IA para criar nomes, backgrounds e atributos 
           para os habitantes, transformando 'NPCs' em personagens com história.
"""
from typing import Optional, Dict
from engine.ai import AIGeneratorClient, AIClient

class AIWorldGenerator:
    @staticmethod
    def generate_city_locations(tema: str, quantidade: int) -> Optional[list]:
        """Gera uma lista dinâmica de locais temáticos para a cidade."""
        return AIGeneratorClient.gerar_locais_cidade(tema, quantidade)

    @staticmethod
    def ask_ai(prompt: str) -> str:
        """Método genérico para consultar a IA."""
        try:
            return AIClient.query(prompt)
        except Exception as e:
            return f"Erro na IA: {e}"

    @staticmethod
    def generate_npc_dna(tema: str, loc_nome: str, loc_tipo: str, genero: str = 'M', nomes_excluidos: list = None) -> Optional[Dict]:
        """Gera um DNA único evitando nomes repetidos."""
        return AIGeneratorClient.gerar_dna_npc(tema, loc_nome, loc_tipo, genero, nomes_excluidos)