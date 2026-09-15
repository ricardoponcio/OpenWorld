/**
 * F01/F05/P01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de entrada único do painel —
 * substitui as três tags <script> soltas do index.html (ordem implícita entre
 * dashboard.js/mapa_composto.js/mapa_leaflet.js) por módulos ES com import explícito.
 * chat_mestre.js entra transitivamente (navegacao.js já importa dele) e registra
 * as próprias ações sozinho; painel_npcs.js/ficha_npc.js precisam ser importados
 * daqui (nenhum outro módulo os alcança desde que P01 tirou o polling de
 * /api/update de navegacao.js).
 */
import { despachar } from './acoes.js';
import { iniciarNavegacao } from './navegacao.js';
import { iniciarMapaComposto } from './mapa_composto.js';
import { iniciarEstado } from './estado.js';
// P01 (docs/16_PLANO_PAINEL_E_IA.md): painel_npcs.js/ficha_npc.js ficaram sem
// nenhum importador quando o polling de /api/update saiu de navegacao.js — só
// registram as próprias ações (não têm `iniciar*` próprio ainda). P04 os
// reescreve contra os endpoints novos e decide o import definitivo.
import './painel_npcs.js';
import './ficha_npc.js';

document.addEventListener('click', despachar);

iniciarMapaComposto();
iniciarNavegacao();
iniciarEstado();
