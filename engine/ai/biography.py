import random
import re
from typing import Dict
from .client import AIClient
from ..logger import WorldLogger

class AIBiographyClient:
    """
    Specialized client for NPC identity, name generation, and biological backgrounds.
    Features robust pre-selected fallback generators to prevent simulation failure.
    """
    @staticmethod
    def gerar_nome_bebe(genero: str, sobrenome_bebe: str, mae_nome: str, pai_nome: str) -> str:
        """
        Generates an immersive baby name using LLM, with fallback lists in case of offline LLM.
        """
        try:
            template = AIClient.read_prompt("baby_name.txt")
            prompt = template.format(
                genero=genero,
                sobrenome_bebe=sobrenome_bebe,
                mae_nome=mae_nome,
                pai_nome=pai_nome
            )
            res = AIClient.query(prompt, timeout=8.0)
            res = re.sub(r'["\'`\n\r]', '', res).strip()
            if res and len(res) < 50 and "Erro" not in res:
                return res
        except Exception as e:
            WorldLogger.warning(f"[AI-BIOLOGY] Ativando fallback para nome de bebê devido a erro no Ollama: {e}")
            
        # Fallback de alta fidelidade
        nomes_masculinos = ["Arthur", "Alistair", "Tristan", "Cedric", "Edric", "Kaelen", "Gareth", "Rowan", "Elian", "Lucas", "Loran", "Eliot", "Aron"]
        nomes_femininos = ["Lyra", "Elora", "Sylvia", "Aria", "Eliana", "Maeve", "Seraphina", "Isolde", "Clara", "Fiona", "Dahlia", "Selene", "Lila"]
        primeiro_nome = random.choice(nomes_masculinos) if genero == 'M' else random.choice(nomes_femininos)
        return f"{primeiro_nome} {sobrenome_bebe}"

    @staticmethod
    def gerar_background_npc(tema: str, raca: str, profissao: str, nome: str) -> Dict[str, str]:
        """
        Generates narrative details for an NPC, with high-fidelity fallbacks.
        """
        try:
            template = AIClient.read_prompt("npc_background.txt")
            prompt = template.format(
                tema=tema,
                nome=nome,
                raca=raca,
                profissao=profissao
            )
            res = AIClient.query(prompt, json_format=True, timeout=8.0)
            import json
            data = json.loads(res)
            if "personalidade" in data and "background" in data:
                return data
        except Exception as e:
            WorldLogger.warning(f"[AI-BIOLOGY] Ativando fallback para background do NPC {nome}: {e}")
            
        # Fallback de alta fidelidade
        personalidades = [
            "Extremamente calmo, prefere resolver conflitos conversando pacientemente.",
            "Um pouco desconfiado de estranhos, mas extremamente leal com os amigos próximos.",
            "Sempre otimista, vê o lado bom de qualquer situação desafiadora.",
            "Obstinado e focado em seu trabalho, às vezes esquece de descansar.",
            "Curioso sobre mistérios antigos e segredos esquecidos do reino."
        ]
        backgrounds = [
            f"Cresceu nas redondezas da vila sonhando em dominar a arte de {profissao}.",
            f"Após anos viajando pelas estradas do reino, decidiu se estabelecer na tranquilidade da comunidade.",
            f"Vem de uma antiga linhagem de trabalhadores dedicados da região.",
            f"Perdeu tudo em uma antiga crise e reconstrói sua vida honestamente na colônia.",
            f"Um aprendiz talentoso que busca deixar sua própria marca lendária no mundo."
        ]
        return {
            "personalidade": random.choice(personalidades),
            "background": random.choice(backgrounds)
        }
