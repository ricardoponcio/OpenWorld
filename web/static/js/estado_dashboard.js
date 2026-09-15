/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado compartilhado do painel
 * (fora do mapa) — extraído de dashboard.js pra este arquivo próprio (não listado
 * na tabela original do plano) porque navegacao.js, painel_npcs.js e ficha_npc.js
 * precisam do mesmo estado sem criar import circular entre eles (mesmo padrão que
 * mapa_composto_estado.js/mapa_leaflet_estado.js já usam).
 */
import { Aba, FiltroNpc, AbaModal } from './constantes.js';

// F01: estado do módulo num objeto só, não dezenas de `let` soltos (ARQUITETURA §10
// regra 4).
export const estado = {
    staticData: null,
    activeView: Aba.MAPA,
    npcFilter: FiltroNpc.VIVOS,
    allNpcs: [],
    allRels: [],
    activeModalTab: AbaModal.PERFIL,
    activeNpcId: null,
};
