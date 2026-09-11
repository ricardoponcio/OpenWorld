"""
Registro dos modelos de cidade (F8.1) — nome -> classe. Importado explicitamente, sem
varredura de diretório: descoberta automática tornaria a ordem de registro dependente do
sistema de arquivos, e isso é porta de entrada pra não-determinismo (F8.1).
"""
import random

from config import cfg_get
from .sitio import SitioCidade
from .base import ModeloCidade, Rua, Quadra, Malha
from .radial import RadialModelo
from .grade import GradeModelo
from .linear import LinearModelo
from .organica import OrganicaModelo

MODELOS = {m.nome: m for m in (RadialModelo, GradeModelo, LinearModelo, OrganicaModelo)}

__all__ = ["SitioCidade", "ModeloCidade", "Rua", "Quadra", "Malha",
           "RadialModelo", "GradeModelo", "LinearModelo", "OrganicaModelo",
           "MODELOS", "escolher_modelo"]


def escolher_modelo(sitio, config):
    """F8.2: lista de possibilidades (cidade_geo_modelo_por_tipo) + sorteio ponderado.
    `if escolhido not in MODELOS` deixa o config citar um modelo ainda não implementado
    (ex.: "portuaria", Seção 4.7) sem quebrar a geração — cai em radial.

    ⚠️ Armadilha de determinismo (Seção 10 item 1/4.5): usa um `random.Random` DERIVADO
    da seed (`seed ^ 0x9E3779B9`), nunca o `self.rng` que o modelo escolhido vai receber
    — sortear o modelo no rng principal, antes do modelo existir, deslocaria a sequência
    de raio/anéis/setores de TODAS as cidades."""
    mapa = cfg_get(config, "cidade_geo_modelo_por_tipo")
    opcoes = mapa.get(sitio.tipo) or mapa.get("_default") or [["radial", 1.0]]
    nomes = [o[0] for o in opcoes]
    pesos = [o[1] for o in opcoes]
    rng_selecao = random.Random(sitio.seed ^ 0x9E3779B9)
    escolhido = rng_selecao.choices(nomes, weights=pesos, k=1)[0]
    if escolhido not in MODELOS:
        escolhido = "radial"
    return escolhido
