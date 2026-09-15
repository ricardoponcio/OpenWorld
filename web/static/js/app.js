/**
 * F01/F05/P01/P04/P05 (docs/16_PLANO_PAINEL_E_IA.md): ponto de entrada único do
 * painel — substitui as três tags <script> soltas do index.html (ordem implícita
 * entre dashboard.js/mapa_composto.js/mapa_leaflet.js) por módulos ES com import
 * explícito. chat_mestre.js entra transitivamente (navegacao.js já importa dele)
 * e registra as próprias ações sozinho; ficha_npc.js só registra ação também, mas
 * nada mais importa este módulo (o botão "Perfil" que a dispara vive na grade de
 * painel_npcs.js, não o módulo em si) — entra aqui como import solto.
 * painel_npcs.js/painel_estatisticas.js precisam do próprio `iniciar*` (buscam
 * config antes de aceitar interação/armar o próprio polling).
 */
import { despachar } from './acoes.js';
import { iniciarNavegacao } from './navegacao.js';
import { iniciarMapaComposto } from './mapa_composto.js';
import { iniciarEstado } from './estado.js';
import { iniciarPainelHabitantes } from './painel_npcs.js';
import { iniciarPainelEstatisticas } from './painel_estatisticas.js';
import './ficha_npc.js';

document.addEventListener('click', despachar);

iniciarMapaComposto();
iniciarNavegacao();
iniciarEstado();
iniciarPainelHabitantes();
iniciarPainelEstatisticas();
