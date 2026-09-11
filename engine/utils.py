import os
import json
import math
import random as random_module
from typing import List, Dict
from datetime import datetime
from .models import NPC, Local


class GeoUtils:
    """
    Fase 2.1 (P0.3): `Local.coordenadas` é coordenada de MUNDO (pixel, Seção 2.3 do
    plano), não mais um par aleatório 5–35. Centralizado aqui porque três lugares
    criam `Local` novo depois do povoamento inicial (builder/populate.py,
    engine/mechanics/housing.py — expansão urbana, engine/mechanics/mestre.py — Modo
    Mestre) e todos têm que sortear na mesma convenção, senão um local nasce em
    coordenada de mundo e outro na grade antiga — exatamente a inconsistência que esta
    fase existe pra eliminar.

    ⚠️ Paliativo consciente (documentado na Seção 2.1 do plano): espalhar edifícios num
    raio de poucos pixels de mundo é espalhá-los por dezenas de km — fisicamente
    absurdo, visualmente aceitável até a Fase 4 (cidade como geometria vetorial real).
    """
    _mapa_cache = None
    _mapa_cache_mtime = None

    @staticmethod
    def _carregar_mapa(caminho: str = "database/mapa_composto.npz"):
        import numpy as np
        mtime = os.path.getmtime(caminho) if os.path.exists(caminho) else None
        if GeoUtils._mapa_cache is None or GeoUtils._mapa_cache_mtime != mtime:
            GeoUtils._mapa_cache = np.load(caminho)["mapa"]
            GeoUtils._mapa_cache_mtime = mtime
        return GeoUtils._mapa_cache

    @staticmethod
    def sortear_ponto_em_terra(cx: float, cy: float, raio: float, nivel_mar: float,
                                rng=None, tentativas: int = 200) -> List[float]:
        """
        Sorteia um ponto uniforme no disco de raio `raio` (em px de mundo) ao redor de
        `(cx, cy)`, rejeitando pontos em água. Cai de volta no próprio `(cx, cy)` se
        `tentativas` esgotar sem achar terra (ex.: cidade cercada de água rasa demais).
        """
        rng = rng or random_module
        try:
            mapa = GeoUtils._carregar_mapa()
        except FileNotFoundError:
            return [float(cx), float(cy)]

        for _ in range(tentativas):
            ang = rng.uniform(0, 2 * math.pi)
            r = raio * math.sqrt(rng.random())
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            ix, iy = int(round(x)), int(round(y))
            if 0 <= ix < mapa.shape[1] and 0 <= iy < mapa.shape[0] and mapa[iy, ix, 0] >= nivel_mar:
                return [round(float(x), 3), round(float(y), 3)]
        return [float(cx), float(cy)]

class NPCUtils:
    @staticmethod
    def agrupar_npcs_por_localizacao(npcs: List[NPC], ignorar_dormindo: bool = True) -> Dict[str, List[NPC]]:
        """
        Agrupa os NPCs ativos/vivos pela sua localização atual.
        """
        from .models import Acao
        por_local = {}
        for npc in npcs:
            if not npc.esta_vivo():
                continue
            if ignorar_dormindo and npc.acao_atual == Acao.DORMIR:
                continue
            loc_id = npc.localizacao_atual_id
            if not loc_id:
                continue
            if loc_id not in por_local:
                por_local[loc_id] = []
            por_local[loc_id].append(npc)
        return por_local

    @staticmethod
    def agrupar_por_casa(npcs: List[NPC]) -> Dict[str, List[NPC]]:
        """
        Agrupa todos os NPCs vivos pelas suas respectivas casas (onde moram).
        """
        por_casa = {}
        for npc in npcs:
            if not npc.esta_vivo() or not npc.casa_id:
                continue
            if npc.casa_id not in por_casa:
                por_casa[npc.casa_id] = []
            por_casa[npc.casa_id].append(npc)
        return por_casa

    @staticmethod
    def obter_moradores_da_casa(npcs: List[NPC], casa_id: str, apenas_vivos: bool = True) -> List[NPC]:
        """
        Retorna todos os NPCs que moram na casa especificada.
        """
        if not casa_id:
            return []
        moradores = []
        for npc in npcs:
            if npc.casa_id == casa_id:
                if apenas_vivos and not npc.esta_vivo():
                    continue
                moradores.append(npc)
        return moradores

    @staticmethod
    def is_casa_superlotada(locais: Dict[str, 'Local'], npcs: List[NPC], casa_id: str) -> bool:
        """
        Retorna True se a quantidade de moradores vivos na casa exceder ou igualar a capacidade do local.
        """
        if not casa_id or not locais:
            return False
        casa = locais.get(casa_id)
        if not casa:
            return False
        
        moradores_vivos = NPCUtils.obter_moradores_da_casa(npcs, casa_id, apenas_vivos=True)
        return len(moradores_vivos) >= casa.capacidade

    @staticmethod
    def obter_casas_vazias(locais: Dict[str, 'Local'], npcs: List['NPC'], ignorar_id: str = "") -> List['Local']:
        """
        Retorna uma lista de residências ativas (status=1) que estão completamente vazias (zero moradores vivos).
        """
        if not locais:
            return []
        
        casas_vazias = []
        for local_id, local in locais.items():
            if local.categoria.lower() == "residencia" and local.status == 1:
                if local_id == ignorar_id:
                    continue
                moradores = NPCUtils.obter_moradores_da_casa(npcs, local_id, apenas_vivos=True)
                if len(moradores) == 0:
                    casas_vazias.append(local)
        return casas_vazias

    @staticmethod
    def obter_parceiros_adultos_na_casa(npcs: List[NPC], npc: NPC) -> List[NPC]:
        """
        Retorna a lista de outros parceiros adultos vivos que residem na mesma casa do NPC.
        """
        if not npc.casa_id:
            return []
        return [
            n for n in npcs 
            if n.id != npc.id 
            and n.esta_vivo() 
            and n.casa_id == npc.casa_id 
            and n.is_adulto()
        ]

    @staticmethod
    def tem_conjuge(npc: NPC) -> bool:
        """
        Verifica se o NPC é formalmente casado com alguém usando o novo status civil.
        """
        from .models import EstadoCivil
        return npc.estado_civil == EstadoCivil.CASADO.value and npc.conjuge_id != ""

    @staticmethod
    def sao_parentes(n1: NPC, n2: NPC) -> bool:
        """
        Verifica se dois NPCs são parentes diretos (pais, filhos, ou irmãos)
        para impedir casamentos incestuosos.
        """
        # Verifica se n1 é pai/mãe de n2
        if n1.id in n2.genealogia or n1.id == n2.pai_id or n1.id == n2.mae_id:
            return True
        # Verifica se n2 é pai/mãe de n1
        if n2.id in n1.genealogia or n2.id == n1.pai_id or n2.id == n1.mae_id:
            return True
            
        # Verifica se são irmãos (possuem pais em comum que não sejam nulos)
        pais_n1 = set(n1.genealogia + ([n1.pai_id, n1.mae_id]))
        pais_n1.discard("")
        
        pais_n2 = set(n2.genealogia + ([n2.pai_id, n2.mae_id]))
        pais_n2.discard("")
        
        
        if len(pais_n1.intersection(pais_n2)) > 0:
            return True
            
        return False

    @staticmethod
    def obter_obra_do_npc(locais: Dict[str, 'Local'], npc: NPC):
        """
        Retorna a obra (Local em construção) que pertence ao NPC ou seu cônjuge.
        """
        if not locais: return None
        for l in locais.values():
            if l.tipo == "Casa" and l.status == 0:
                if npc.id in getattr(l, 'descricao', '') or (npc.conjuge_id and npc.conjuge_id in getattr(l, 'descricao', '')):
                    return l
        return None

    @staticmethod
    def obter_data_nascimento_valida(npc: NPC):
        """
        Retorna um objeto datetime correspondente à data de nascimento do NPC.
        Se for inválida ou vazia, retorna datetime.min para ordenação uniforme.
        """
        if not npc.data_nascimento:
            return datetime.min
        try:
            return datetime.fromisoformat(npc.data_nascimento.replace(' ', 'T'))
        except:
            return datetime.min

    @staticmethod
    def obter_data_simulada_inicial(db) -> datetime:
        """
        Carrega a data simulada do banco de dados (meta) ou retorna o valor inicial padrão (Dia 1, 06:00).
        """
        hora_salva = db.carregar_meta("hora_simulada_iso")
        if hora_salva:
            try:
                return datetime.fromisoformat(hora_salva)
            except:
                pass
        return datetime(1200, 1, 1, 6, 0)


class LocationUtils:
    @staticmethod
    def is_local_publico(local: 'Local') -> bool:
        """
        Verifica se um local é público/gratuito (ex: praça, parque, etc.).
        """
        if not local:
            return False
        from .models import CategoriaLocal
        if local.categoria == CategoriaLocal.PUBLICO.value:
            return True
        palavras_publicas = ['praça', 'praca', 'parque', 'jardim', 'rua', 'largo', 'campo', 'arena']
        nome_lower = local.nome.lower()
        return any(p in nome_lower for p in palavras_publicas)

    @staticmethod
    def is_local_comida(local: 'Local') -> bool:
        """Verifica se o local serve comida (Taverna ou Praça Pública com barraquinhas)."""
        if not local:
            return False
        from .models import CategoriaLocal
        return getattr(local, 'categoria', '') in [CategoriaLocal.TAVERNA.value, CategoriaLocal.PUBLICO.value]

    @staticmethod
    def is_local_passeio(local: 'Local', npc_casa_id: str = "") -> bool:
        """Verifica se o local é adequado para perambulação ociosa (Social, Lojas comerciais, ou própria casa)."""
        if not local:
            return False
        if local.id == npc_casa_id:
            return True
        return getattr(local, 'tipo', '') in ['Social', 'Loja']


class CartographyImporter:
    @staticmethod
    def import_manifest(db, manifest_path: str) -> list:
        if not os.path.exists(manifest_path):
            print("❌ Manifesto não encontrado. Por favor, execute a Cartografia Global primeiro.")
            return []
            
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        print("🗺️  Importando Continentes e Cidades para o Banco de Dados...")
        cidades_salvas = []
        
        for cont in manifest.get("continentes", []):
            db.salvar_continente(cont["uuid"], cont["nome"], cont.get("area_real_km2", 0))
            
            for cid in cont.get("cidades", []):
                cid_id = db.salvar_cidade(
                    continente_uuid=cont["uuid"],
                    nome=cid["nome"],
                    tamanho=cid.get("tamanho", "Pequeno"),
                    tipo=cid.get("tipo", "Desconhecido"),
                    x_global=cid.get("x_global", 0),
                    y_global=cid.get("y_global", 0)
                )
                cid["db_id"] = cid_id
                cidades_salvas.append(cid)
        return cidades_salvas
