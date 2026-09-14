"""
MODULE: identificadores.py
FUNÇÃO: Geração de ids únicos em runtime.

DESCRIÇÃO:
    C03 (docs/16_PLANO_PAINEL_E_IA.md, Armadilha 25): o padrão antigo,
    `f"<prefixo>_{int(time.time())}_{random.randint(0, 999)}"`, tem só 1.000 valores
    possíveis por segundo real. Como o motor faz vários ticks por segundo e várias
    rotinas disparam no mesmo minuto simulado (concepção e parto têm hora fixa), dois
    eventos caem no mesmo segundo com frequência — e cada par colide com chance de
    1 em 1.000. `RepositorioNPC.salvar` usa `INSERT OR REPLACE`, então a colisão virava
    sobrescrita silenciosa: medido 3 de 495 bebês perdidos numa run real.

    `novo_id` usa uuid4 (2^122 valores) — a colisão deixa de ser um risco prático.
"""
import uuid
from enum import Enum


class PrefixoId(Enum):
    """C03 (docs/16_PLANO_PAINEL_E_IA.md): prefixo de cada tipo de id gerado em
    runtime. O valor é o começo do id gravado no banco — igual ao de hoje, para não
    mudar a leitura humana dos ids."""
    NPC_NASCIDO      = "npc_nac"
    EVENTO_CONCEPCAO = "evt_concepcao"
    EVENTO_PARTO     = "evt_parto"
    EVENTO_HERANCA   = "evt_heranca"
    EVENTO_REINO     = "evt_reino"
    EVENTO_UNIAO     = "evt_uniao"
    EVENTO_CRESCER   = "evt_crescer"
    EVENTO_ADULTO    = "evt_adulto"
    EVENTO_IDOSO     = "evt_idoso"
    EVENTO_MORTE     = "evt_morte"
    EVENTO_SOCIAL    = "evt"
    EVENTO_EXPANSAO  = "evt_expansao"
    EVENTO_GLOBAL    = "glob"


def novo_id(prefixo: PrefixoId) -> str:
    """C03: `<prefixo>_<32 hex de uuid4>` — nunca relógio + sorteio pequeno
    (Armadilha 25). uuid4, e não um gerador seedado, porque o runtime da simulação já
    não é determinístico (usa `random` global e o relógio); o determinismo da
    ARQUITETURA §11 é exigência do `cartographer/`, que não gera estes ids."""
    return f"{prefixo.value}_{uuid.uuid4().hex}"
