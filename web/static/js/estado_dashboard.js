/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estado compartilhado do painel
 * (fora do mapa) — extraído de dashboard.js pra este arquivo próprio (não listado
 * na tabela original do plano) porque navegacao.js, painel_npcs.js e ficha_npc.js
 * precisam do mesmo estado sem criar import circular entre eles (mesmo padrão que
 * mapa_composto_estado.js/mapa_leaflet_estado.js já usam).
 */
import { Aba, AbaModal } from './constantes.js';

// F01: estado do módulo num objeto só, não dezenas de `let` soltos (ARQUITETURA §10
// regra 4).
// P04 (docs/16_PLANO_PAINEL_E_IA.md): `npcFilter`/`allNpcs`/`allRels` saíram — a
// aba Habitantes e a ficha do NPC não guardam mais a lista inteira do mundo, só
// pedem a página/ficha que precisam a cada momento (`painel_npcs.js`/`ficha_npc.js`
// têm seu próprio estado local de filtro/paginação, privado de cada módulo).
export const estado = {
    staticData: null,
    activeView: Aba.MAPA,
    activeModalTab: AbaModal.PERFIL,
    activeNpcId: null,
};
