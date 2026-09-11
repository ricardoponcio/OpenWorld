from .models import Local, CategoriaLocal
from .config_loader import cfg_get, carregar_config_global


class LocationUtils:
    @staticmethod
    def is_local_publico(local: 'Local') -> bool:
        """
        Verifica se um local é público/gratuito (ex: praça, parque, etc.).
        """
        if not local:
            return False
        if local.categoria == CategoriaLocal.PUBLICO.value:
            return True
        palavras_publicas = cfg_get(carregar_config_global(), "geracao_urbana", "palavras_chave_local_publico")
        nome_lower = local.nome.lower()
        return any(p in nome_lower for p in palavras_publicas)

    @staticmethod
    def is_local_comida(local: 'Local') -> bool:
        """Verifica se o local serve comida (Taverna ou Praça Pública com barraquinhas)."""
        if not local:
            return False
        return local.categoria in [CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value]

    @staticmethod
    def is_local_passeio(local: 'Local', npc_casa_id: str = "") -> bool:
        """Verifica se o local é adequado para perambulação ociosa (Social, Lojas comerciais, ou própria casa)."""
        if not local:
            return False
        if local.id == npc_casa_id:
            return True
        return local.tipo in ['Social', 'Loja']
