/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): abas e barra superior (relógio,
 * pausa, velocidade, banner de evento, crônicas) — extraído de dashboard.js.
 * Também é quem inicia o painel (`iniciarNavegacao`, chamada por app.js) e mantém
 * o polling de `/api/update` até P01 substituir isso por endpoints menores.
 */
import { registrarAcoes } from './acoes.js';
import { initMapaLeaflet } from './mapa_leaflet.js';
import { Aba } from './constantes.js';
import { escaparHtml } from './formatacao.js';
import { obterInit, obterEstadoPainel, definirVelocidade, alternarPausa } from './api.js';
import { carregarHistoricoMestre, enviarMensagemMestre } from './chat_mestre.js';
import { atualizarPainelHabitantes } from './painel_npcs.js';
import { estado } from './estado_dashboard.js';

// F03: o mapeamento do valor curto de `data-aba` pro id de DOM da view — a view em
// si continua sendo um id de elemento HTML, não vocabulário de domínio, então fica
// como está (não é um enum).
const ABA_PARA_VIEW_ID = {
    [Aba.MAPA]: 'map-view',
    [Aba.HABITANTES]: 'npc-view',
    [Aba.MESTRE]: 'mestre-view',
    [Aba.MAPA_LIVE]: 'mapa-leaflet-view',
};

function switchView(btn, aba) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(ABA_PARA_VIEW_ID[aba]).classList.add('active');
    btn.classList.add('active');
    estado.activeView = aba;

    const eventLog = document.getElementById('event-log');
    if (aba === Aba.HABITANTES || aba === Aba.MESTRE || aba === Aba.MAPA_LIVE) {
        eventLog.style.display = 'none';
    } else {
        eventLog.style.display = 'block';
    }

    if (aba === Aba.MESTRE) {
        carregarHistoricoMestre();
    } else if (aba === Aba.MAPA_LIVE) {
        initMapaLeaflet();
    } else {
        update();
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
    iniciarPolling();
}

async function iniciarPolling() {
    try {
        estado.staticData = await obterInit();
        // Old map generation removed

        update();
        setInterval(update, 1000);
    } catch (e) { console.error("Init Error:", e); }
}

async function setSpeed(v) {
    try {
        await definirVelocidade(v);
        document.querySelectorAll('.speed-btn').forEach(b => {
            b.classList.toggle('active', parseInt(b.innerText) == v);
        });
    } catch (e) { console.error("Speed Error:", e); }
}

async function update() {
    const statusMsg = document.getElementById('status-msg');
    const statusIcon = document.getElementById('status-icon');
    const statusBar = document.getElementById('status-bar');

    try {
        const data = await obterEstadoPainel();

        if (data.npcs) estado.allNpcs = data.npcs;
        if (data.rels) estado.allRels = data.rels;

        if (data.error) {
            statusMsg.innerText = data.error;
            statusIcon.innerText = "🔴";
            statusBar.className = "status-error";
            return;
        }

        if (data.warnings && data.warnings.length > 0) {
            statusMsg.innerText = "⚠️ " + data.warnings.join(' | ');
            statusIcon.innerText = "🟡";
            statusBar.className = "status-warn";
        } else {
            statusMsg.innerText = "Sistema Online | Sincronizado";
            statusIcon.innerText = "🟢";
            statusBar.className = "status-ok";
        }

        updatePauseUI(data.p);
        document.getElementById('clock').innerText = data.h || "Sincronizando...";

        document.querySelectorAll('.speed-btn').forEach(b => {
            b.classList.toggle('active', parseFloat(b.innerText) == data.v);
        });

        const banner = document.getElementById('event-banner');
        if (data.evg) {
            banner.style.display = 'block';
            document.getElementById('ev-title').innerText = data.evg.t;
            document.getElementById('ev-desc').innerText = data.evg.d;
            banner.style.background = data.evg.tp === 'CATASTROFE' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)';
        } else {
            banner.style.display = 'none';
        }

        // F05 (docs/16_PLANO_PAINEL_E_IA.md): a bridge window.updateMapEntities saiu
        // — a contagem de NPCs da cidade aberta no mapa em canvas já vem de
        // /api/regiao/<nome>/entities (mapa_composto.js::selectCity), não deste
        // polling geral.
        if (estado.activeView === Aba.HABITANTES && data.npcs) {
            atualizarPainelHabitantes(data.npcs);
        }

        if (data.evs) {
            const logInner = document.getElementById('event-log-inner');
            if (logInner) {
                logInner.innerHTML = `<h4 class="event-log-titulo">📜 Crônicas Recentes</h4>` +
                    data.evs.map(e => `<div class="event-item"><small>${escaparHtml(e.t)}</small><br>${escaparHtml(e.r)}</div>`).join('');
            }
        }

    } catch (e) { console.error("Update Error:", e); }
}

async function togglePause() {
    try {
        const data = await alternarPausa();
        updatePauseUI(data.pausado);
    } catch (e) { console.error("Pause Error:", e); }
}

function updatePauseUI(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (!btn) return;
    btn.innerText = isPaused ? "▶️" : "⏸️";
    btn.style.background = isPaused ? "var(--success)" : "var(--accent)";
    btn.style.boxShadow = `0 0 10px ${isPaused ? "var(--success)" : "var(--accent)"}`;
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'pausar': () => togglePause(),
    'velocidade': (alvo) => setSpeed(parseInt(alvo.dataset.valor, 10)),
    'trocar-aba': (alvo) => switchView(alvo, alvo.dataset.aba),
    'alternar-cronicas': () => toggleEventLog(),
});
