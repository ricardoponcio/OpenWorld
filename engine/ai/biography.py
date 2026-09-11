import re
from typing import Dict
from .client import AIClient
from .fallbacks import AIFallbacks
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
        primeiro_nome = AIFallbacks.sortear_nome_bebe(genero)
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
        return {
            "personalidade": AIFallbacks.sortear_personalidade(),
            "background": AIFallbacks.sortear_background(profissao)
        }
