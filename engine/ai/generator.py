import random
from typing import Dict, List, Optional
from .client import AIClient
from ai.utils import AIUtils
from ..logger import WorldLogger

class AIGeneratorClient:
    """
    Specialized client for physical map architectures, city buildings and DNA configurations.
    """
    @staticmethod
    def gerar_locais_cidade(tema: str, quantidade: int) -> List[Dict]:
        """
        Generates structural urban locations with robust JSON parsing and fallback.
        """
        try:
            template = AIClient.read_prompt("locations.txt")
            prompt = template.format(tema=tema, quantidade=quantidade)
            res = AIClient.query(prompt, json_format=True, timeout=60.0)
            
            data = AIUtils.parse_json_safely(res)
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception as e:
            WorldLogger.warning(f"[AI-GENERATOR] Ativando fallback para criação de locais devido a falha: {e}")
            
        # Fallback procedural
        categorias_oficina = ["Oficina do Dragão", "Ferrearia da Guilda", "Moinho de Vento", "Serraria Real"]
        categorias_sociais = ["Taverna do Dragão", "Praça das Estrelas", "Arena da Vila", "Jardim Botânico"]
        locais = []
        for i in range(quantidade):
            tipo = "Social" if i < 2 else "Oficina"
            nome = random.choice(categorias_sociais) if tipo == "Social" else random.choice(categorias_oficina)
            locais.append({
                "nome": f"{nome} {random.randint(10, 99)}",
                "tipo": tipo,
                "descricao": f"Um estabelecimento robusto e bem estabelecido no centro de {tema}."
            })
        return locais

    @staticmethod
    def gerar_dna_npc(tema: str, loc_nome: str, loc_tipo: str, genero: str, nomes_excluidos: list) -> Dict:
        """
        Generates an NPC DNA structure, ensuring high-fidelity fallback when offline.
        """
        genero_ext = "MASCULINO" if genero == 'M' else "FEMININO"
        nomes_str = ", ".join(nomes_excluidos) if nomes_excluidos else "Nenhum"
        
        try:
            template = AIClient.read_prompt("dna.txt")
            prompt = template.format(
                tema=tema,
                genero_ext=genero_ext,
                nomes_str=nomes_str,
                loc_nome=loc_nome,
                loc_tipo=loc_tipo,
                genero=genero
            )            # Aumentado de 30s para 120s para suportar chamadas pesadas via ThreadPool
            res = AIClient.query(prompt, json_format=True, timeout=120.0)
            
            data = AIUtils.parse_json_safely(res)
            if data and isinstance(data, dict) and "nome" in data and "genero" in data:
                return data
        except Exception as e:
            WorldLogger.warning(f"[AI-GENERATOR] Ativando fallback para DNA de NPC: {e}")
            
        # Fallback procedural
        nomes_m = ["Erik", "Thorn", "Kaelen", "Fíricus", "Einar", "Elior", "Garrick", "Bram"]
        nomes_f = ["Elara", "Mila", "Aria", "Lila", "Natalia", "Mariana", "Sylvia", "Vespera"]
        sobrenomes = ["Stonefist", "Ironforge", "Moonshadow", "Thornbloom", "Frostwhisper", "Brilhante", "Marinerá", "Soliluna"]
        
        first = random.choice(nomes_m) if genero == 'M' else random.choice(nomes_f)
        last = random.choice(sobrenomes)
        nome_completo = f"{first} {last}"
        
        while nome_completo in nomes_excluidos:
            first = random.choice(nomes_m) if genero == 'M' else random.choice(nomes_f)
            last = random.choice(sobrenomes)
            nome_completo = f"{first} {last}"
            
        raca = "Humano" if random.random() < 0.7 else random.choice(["Elfo", "Anão", "Orc"])
        
        return {
            "nome": nome_completo,
            "genero": genero,
            "raca": raca,
            "cargo": f"Trabalhador de {loc_nome}",
            "personalidade": "Uma mente curiosa e determinada a cumprir seus objetivos.",
            "background": f"Chegou a {tema} recentemente buscando fazer fortuna em {loc_nome}."
        }
