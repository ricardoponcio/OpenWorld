/**
 * F05/P01 (docs/16_PLANO_PAINEL_E_IA.md): abas e navegação — extraído de
 * dashboard.js. O relógio/pausa/velocidade/banner/crônicas da barra superior
 * saíram daqui para estado.js (P01), que faz o próprio polling de /api/estado
 * independente da aba ativa.
 */
import { registrarAcoes } from './acoes.js';
import { initMapaLeaflet } from './mapa_leaflet.js';
import { Aba } from './constantes.js';
import { obterInit } from './api.js';
import { carregarHistoricoMestre, enviarMensagemMestre } from './chat_mestre.js';
import { carregarPaginaHabitantes } from './painel_npcs.js';
import { carregarEstatisticas } from './painel_estatisticas.js';
import { estado } from './estado_dashboard.js';

// F03: o mapeamento do valor curto de `data-aba` pro id de DOM da view — a view em
// si continua sendo um id de elemento HTML, não vocabulário de domínio, então fica
// como está (não é um enum).
const ABA_PARA_VIEW_ID = {
    [Aba.MAPA]: 'map-view',
    [Aba.HABITANTES]: 'npc-view',
    [Aba.MESTRE]: 'mestre-view',
    [Aba.MAPA_LIVE]: 'mapa-leaflet-view',
    [Aba.ESTATISTICAS]: 'estatisticas-view',
};

function switchView(btn, aba) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(ABA_PARA_VIEW_ID[aba]).classList.add('active');
    btn.classList.add('active');
    estado.activeView = aba;

    const eventLog = document.getElementById('event-log');
    if (aba === Aba.HABITANTES || aba === Aba.MESTRE || aba === Aba.MAPA_LIVE || aba === Aba.ESTATISTICAS) {
        eventLog.style.display = 'none';
    } else {
        eventLog.style.display = 'block';
    }

    if (aba === Aba.MESTRE) {
        carregarHistoricoMestre();
    } else if (aba === Aba.MAPA_LIVE) {
        initMapaLeaflet();
    } else if (aba === Aba.HABITANTES) {
        carregarPaginaHabitantes();
    } else if (aba === Aba.ESTATISTICAS) {
        carregarEstatisticas();
    }
}

function toggleEventLog() {
    const log = document.getElementById('event-log');
    log.classList.toggle('collapsed');
}

export function iniciarNavegacao() {
    // F01: o Enter no campo do Mestre era um `onkeydown` inline — vira um listener
    // de verdade, registrado aqui (uma vez), no próprio elemento.
    document.getElementById('mestre-input').addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') enviarMensagemMestre();
    });
    // P01: `staticData` (mapa_terreno) não tem nenhum leitor no JS hoje — mantido
    // só porque nenhuma tarefa deste bloco pediu pra apagar `/api/init`; se um dia
    // sobrar sem uso nenhum, é `estado.staticData` que sai, não este fetch.
    obterInit().then(data => { estado.staticData = data; }).catch(e => console.error("Init Error:", e));
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'trocar-aba': (alvo) => switchView(alvo, alvo.dataset.aba),
    'alternar-cronicas': () => toggleEventLog(),
});
