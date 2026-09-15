/**
 * F01/F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): ponto de entrada único do painel —
 * substitui as três tags <script> soltas do index.html (ordem implícita entre
 * dashboard.js/mapa_composto.js/mapa_leaflet.js) por módulos ES com import explícito.
 * Só isto importa os módulos de início "por fora"; painel_npcs.js, ficha_npc.js e
 * chat_mestre.js entram transitivamente (navegacao.js já importa dos três) e
 * registram as próprias ações sozinhos, sem precisar ser chamados daqui.
 */
import { despachar } from './acoes.js';
import { iniciarNavegacao } from './navegacao.js';
import { iniciarMapaComposto } from './mapa_composto.js';

document.addEventListener('click', despachar);

iniciarMapaComposto();
iniciarNavegacao();
