/**
 * F01 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): ponto de entrada único do painel —
 * substitui as três tags <script> soltas do index.html (ordem implícita entre
 * dashboard.js/mapa_composto.js/mapa_leaflet.js) por módulos ES com import explícito.
 * Só isto importa os outros módulos "por fora"; eles próprios não se importam entre
 * si além do estritamente necessário (dashboard.js precisa de initMapaLeaflet pra
 * trocar de aba).
 */
import { despachar } from './acoes.js';
import { iniciarDashboard } from './dashboard.js';
import { iniciarMapaComposto } from './mapa_composto.js';

document.addEventListener('click', despachar);

iniciarMapaComposto();
iniciarDashboard();
