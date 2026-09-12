import json
from typing import Dict, List
from .client import AIClient
from .utils import AIUtils
from ..logger import WorldLogger
from ..models import ComandoMestre, HumorNPC


class AIGameMasterClient:
    """
    Cliente de IA do Modo Mestre (Frente 5) — irmão de AIStorytellerClient, mas para
    diálogo contínuo em vez de disparo único: recebe o histórico da conversa e a
    mensagem do jogador, devolve uma narração livre e (opcionalmente) ações de mundo
    propostas. Nenhuma ação é aplicada aqui — só sugerida; ver engine/mechanics/mestre/.

    Os comandos e humores aceitos são injetados no prompt a partir dos enums
    (`ComandoMestre`, `HumorNPC`), não copiados no .txt: o vocabulário que a IA pode usar
    e o que o código aceita de volta são a mesma lista, por construção (R-F03).
    """

    @staticmethod
    def gerar_resposta_mestre(tema: str, contexto: Dict, historico: List[dict], mensagem_jogador: str) -> Dict:
        """
        Gera a resposta do Mestre a uma mensagem do jogador.
        Retorna sempre {"narracao": str, "acoes_propostas": list}.
        """
        try:
            template = AIClient.read_prompt("mestre_mensagem.txt")
            historico_texto = "\n".join(f"{h['autor']}: {h['mensagem']}" for h in historico[-10:]) or "(início da conversa)"
            prompt = template.format(
                tema=tema,
                contexto_json=json.dumps(contexto, indent=2, ensure_ascii=False),
                historico=historico_texto,
                mensagem_jogador=mensagem_jogador,
                comandos=", ".join(c.value for c in ComandoMestre),
                humores=", ".join(f'"{h.value}"' for h in HumorNPC),
            )
            res = AIClient.query(prompt, json_format=True, timeout=60.0)
            data = AIUtils.parse_json_safely(res)
            if data and isinstance(data, dict) and "narracao" in data:
                data.setdefault("acoes_propostas", [])
                return data
        except Exception as e:
            WorldLogger.warning(f"[MESTRE-IA] Falha ao gerar resposta, ativando fallback: {e}")

        return {
            "narracao": (
                "O Mestre pondera por um instante, mas as brumas do destino (a IA local) "
                "estão indisponíveis agora. Verifique se o Ollama está rodando e tente de novo."
            ),
            "acoes_propostas": [],
        }
