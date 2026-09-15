import random
from typing import Dict, List, Optional
from .client import AIClient, ErroIAIndisponivel
from .clientes import ClienteIA
from .respostas_llm import RespostaLLM
from .fallbacks import AIFallbacks
from ..logger import WorldLogger
from ..models import Genero

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
            res = AIClient.query(prompt, cliente=ClienteIA.LOCAIS_CIDADE, json_format=True)

            data = RespostaLLM.parse_json_safely(res)
            if isinstance(data, list) and len(data) > 0:
                return data
        except (ErroIAIndisponivel, KeyError) as e:
            WorldLogger.warning(f"[AI-GENERATOR] Ativando fallback para criação de locais devido a falha: {e}")
            
        # Fallback procedural
        locais = []
        for i in range(quantidade):
            tipo = "Social" if i < 2 else "Oficina"
            nome = AIFallbacks.sortear_local_social() if tipo == "Social" else AIFallbacks.sortear_local_oficina()
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
        genero_ext = "MASCULINO" if genero == Genero.MASCULINO.value else "FEMININO"
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
            )
            res = AIClient.query(prompt, cliente=ClienteIA.DNA_NPC, json_format=True)

            data = RespostaLLM.parse_json_safely(res)
            if data and isinstance(data, dict) and "nome" in data and "genero" in data:
                return data
        except (ErroIAIndisponivel, KeyError) as e:
            WorldLogger.warning(f"[AI-GENERATOR] Ativando fallback para DNA de NPC: {e}")
            
        # Fallback procedural
        nome_completo = AIFallbacks.sortear_nome_npc(genero, nomes_excluidos)

        return {
            "nome": nome_completo,
            "genero": genero,
            "raca": AIFallbacks.sortear_raca(),
            "cargo": f"Trabalhador de {loc_nome}",
            "personalidade": "Uma mente curiosa e determinada a cumprir seus objetivos.",
            "background": f"Chegou a {tema} recentemente buscando fazer fortuna em {loc_nome}."
        }
