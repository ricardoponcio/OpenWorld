"""
MODULE: acoes/__init__.py
FUNÇÃO: Registro explícito das ações de mundo do Modo Mestre (R-F03).

DESCRIÇÃO:
    O registro é escrito à mão, de propósito: varrer o diretório deixaria o conjunto de
    comandos aceitos dependente da ordem do sistema de arquivos, e um arquivo meio
    escrito passaria a ser um comando válido. Mesma política dos modelos de cidade
    (11_ARQUITETURA.md, D6).

    Para acrescentar um comando: o membro novo em `ComandoMestre`, um arquivo aqui com a
    classe, e uma entrada em `ACOES`. O despacho não muda.
"""
from .base import AcaoDeMundo, AcaoProposta, ContextoMestre
from .criar_local import CriarLocal
from .reatribuir_npc import ReatribuirNpc
from .destruir_local import DestruirLocal
from .afetar_npc import AfetarNpc

# A ordem importa: CRIAR_LOCAL precisa vir antes de REATRIBUIR_NPC numa mesma lista de
# ações para que o marcador NOVO_LOCAL tenha um id para resolver. Esta tupla não define
# essa ordem (quem define é a lista proposta pela IA), mas documenta a dependência.
ACOES = (CriarLocal(), ReatribuirNpc(), DestruirLocal(), AfetarNpc())

POR_COMANDO = {acao.comando: acao for acao in ACOES}

__all__ = [
    "AcaoDeMundo", "AcaoProposta", "ContextoMestre",
    "CriarLocal", "ReatribuirNpc", "DestruirLocal", "AfetarNpc",
    "ACOES", "POR_COMANDO",
]
