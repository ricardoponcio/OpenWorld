import json
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importações globais
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if raiz not in sys.path:
    sys.path.append(raiz)

from engine.ai.client import AIClient, ErroIAIndisponivel
from engine.ai.clientes import ClienteIA
from engine.ai.respostas_llm import RespostaLLM
from engine.logger import WorldLogger
from cartographer.config import CARTOGRAPHER_CONFIG
from config import cfg_get

class WorldManagerAIClient:
    """
    Specialized AI client for generating high-level geographical continental layouts
    and regional metadata for OpenWorld's Tiled Cartographer.
    """

    @staticmethod
    def _clampar_campo(c: dict, campo: str, lo: float, hi: float, padrao: float, rotulo: str):
        """Clampa um campo numérico ao intervalo que o PRÓPRIO prompt pede, logando
        quando a IA o ignora — sem isso, silenciosamente."""
        valor_antes = c.get(campo, padrao)
        valor = min(max(valor_antes, lo), hi)
        if valor != valor_antes:
            WorldLogger.warning(
                f"[AI-WORLD-STRATEGY] {rotulo} veio da IA com {campo}={valor_antes} "
                f"fora do intervalo [{lo},{hi}] pedido no prompt — clampado para {valor}."
            )
        c[campo] = valor

    @staticmethod
    def _validar_e_clampar_layout(continentes: list, tamanho_global: int) -> list:
        """
        Fase 1.1 (achado real, repetido em 2 sessões): o prompt PEDE limites pra
        `centro_x/y`, `irregularidade`, `area_km2` e `elevacao_maxima`, mas a IA os
        ignora com frequência — um continente saiu com `centro_x=50` (vinheta cortou
        quase tudo, área real 15% da planejada); outro saiu com `irregularidade=0.9`
        (prompt pede até 0,8) e ficou preso em 63% de área real mesmo com a
        compensação de irregularidade + calibração adaptativa (Fase 1.1) no limite.
        "Python decide geometria" (Seção 4 do plano): pedir o limite em texto não
        basta, tem que garantir no código — todo campo geométrico é clampado aqui.
        """
        margem = cfg_get(CARTOGRAPHER_CONFIG, "continente_centro_margem_borda_px")
        lo_pos, hi_pos = margem, tamanho_global - margem
        for c in continentes:
            cx_antes, cy_antes = c.get("centro_x"), c.get("centro_y")
            cx = min(max(c.get("centro_x", tamanho_global / 2), lo_pos), hi_pos)
            cy = min(max(c.get("centro_y", tamanho_global / 2), lo_pos), hi_pos)
            if cx != cx_antes or cy != cy_antes:
                WorldLogger.warning(
                    f"[AI-WORLD-STRATEGY] Continente '{c.get('nome')}' veio da IA com centro "
                    f"({cx_antes},{cy_antes}) fora da margem segura [{lo_pos},{hi_pos}] — clampado para ({cx},{cy})."
                )
            c["centro_x"], c["centro_y"] = cx, cy

            # Mesmos intervalos que ai/prompt/world_map_generation.txt pede por escrito.
            rotulo = f"Continente '{c.get('nome')}'"
            WorldManagerAIClient._clampar_campo(c, "irregularidade", 0.1, 0.8, 0.45, rotulo)
            WorldManagerAIClient._clampar_campo(c, "area_km2", 2_500_000, 8_000_000, 4_500_000, rotulo)
            WorldManagerAIClient._clampar_campo(c, "elevacao_maxima", 0.6, 1.0, 0.8, rotulo)
            mods = c.setdefault("modificadores", {})
            WorldManagerAIClient._clampar_campo(mods, "calor", -0.3, 0.3, 0.0, rotulo)
            WorldManagerAIClient._clampar_campo(mods, "umidade", -0.3, 0.3, 0.0, rotulo)
        return continentes

    @staticmethod
    def planejar_continentes(semente: int, tamanho_global: int) -> dict:
        """
        Queries the local LLM to plan the distribution, sizing, irregularity, 
        and climate modification properties of continents.
        """
        try:
            # Caminho absoluto seguro para o prompt/world_map_generation.txt
            dir_ai = os.path.dirname(os.path.abspath(__file__))
            caminho_prompt = os.path.join(dir_ai, "prompt", "world_map_generation.txt")
            
            with open(caminho_prompt, "r", encoding="utf-8") as f:
                prompt_template = f.read()
                
            # Substitui as variáveis específicas no template do prompt de forma robusta e segura
            prompt = prompt_template.replace("{semente}", str(semente)).replace("{limite}", str(tamanho_global - 150))
            
            WorldLogger.info(f"[AI-WORLD-STRATEGY] Planejando continentes com a semente: {semente}...")
            res = AIClient.query(prompt, cliente=ClienteIA.PLANEJAMENTO_CONTINENTES, json_format=True)

            # Limpeza e parsing de JSON robustos e seguros via RespostaLLM global
            data = RespostaLLM.parse_json_safely(res)

            if data and "continentes" in data and isinstance(data["continentes"], list) and len(data["continentes"]) > 0:
                WorldLogger.info(f"[AI-WORLD-STRATEGY] {len(data['continentes'])} continentes planejados com sucesso pela IA!")
                data["continentes"] = WorldManagerAIClient._validar_e_clampar_layout(data["continentes"], tamanho_global)
                return data
            raise ValueError("Resposta da IA formatada incorretamente ou vazia.")
        except (ErroIAIndisponivel, ValueError) as e:
            WorldLogger.warning(f"[AI-WORLD-STRATEGY] Falha ao consultar o serviço de IA: {e}. Usando fallback determinístico.")
            
        # Fallback procedural determinístico baseado na semente
        import random
        random.seed(semente)
        num_continentes = random.randint(3, 5)
        continentes = []
        nomes = ["Eldoria", "Aridia", "Gondwana", "Bravia", "Arquipélago Azul"]
        perfis = ["Alpino", "Platô", "Arquipélago", "Erosivo"]
        margem = int(cfg_get(CARTOGRAPHER_CONFIG, "continente_centro_margem_borda_px"))

        for i in range(num_continentes):
            continentes.append({
                "nome": nomes[i % len(nomes)],
                "centro_x": random.randint(margem, tamanho_global - margem),
                "centro_y": random.randint(margem, tamanho_global - margem),
                "area_km2": random.randint(2500000, 8000000),
                "raio_visual": random.randint(150, 250),
                "irregularidade": random.uniform(0.3, 0.6),
                "elevacao_maxima": random.uniform(0.7, 0.95),
                "perfil_geologico": perfis[i % len(perfis)],
                "modificadores": {
                    "calor": random.uniform(-0.15, 0.15),
                    "umidade": random.uniform(-0.15, 0.15)
                }
            })
            
        return {"continentes": continentes}
