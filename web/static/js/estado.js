/**
 * P01 (docs/16_PLANO_PAINEL_E_IA.md): relógio, pausa, velocidade, banner de
 * evento global e crônicas da barra superior — polling de /api/estado
 * independente da aba ativa (substitui a parte de dashboard.js/navegacao.js que
 * lia isso de /api/update, removido nesta tarefa).
 */
import { registrarAcoes } from './acoes.js';
import { escaparHtml } from './formatacao.js';
import { obterEstado, definirVelocidade, alternarPausa } from './api.js';

// P02 (docs/16_PLANO_PAINEL_E_IA.md, ARQUITETURA §10 regra 6): o intervalo vem
// de painel.estado_polling_ms (config), nunca duplicado aqui — 1000 é só o
// chute inicial até a primeira resposta de /api/estado chegar.
let pollingMs = 1000;

function atualizarBanner(eventoGlobal) {
    const banner = document.getElementById('event-banner');
    if (eventoGlobal) {
        banner.style.display = 'block';
        document.getElementById('ev-title').innerText = eventoGlobal.titulo;
        document.getElementById('ev-desc').innerText = eventoGlobal.descricao;
        banner.style.background = eventoGlobal.tipo === 'CATASTROFE' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)';
    } else {
        banner.style.display = 'none';
    }
}

function atualizarCronicas(cronicas) {
    const logInner = document.getElementById('event-log-inner');
    if (!logInner || !cronicas) return;
    logInner.innerHTML = `<h4 class="event-log-titulo">📜 Crônicas Recentes</h4>` +
        cronicas.map(c => `<div class="event-item"><small>${escaparHtml(c.timestamp)}</small><br>${escaparHtml(c.resumo)}</div>`).join('');
}

function atualizarVelocidade(pedida) {
    document.querySelectorAll('.speed-btn').forEach(b => {
        b.classList.toggle('active', parseFloat(b.innerText) == pedida);
    });
}

function atualizarPauseUI(pausado) {
    const btn = document.getElementById('pause-btn');
    if (!btn) return;
    btn.innerText = pausado ? "▶️" : "⏸️";
    btn.style.background = pausado ? "var(--success)" : "var(--accent)";
    btn.style.boxShadow = `0 0 10px ${pausado ? "var(--success)" : "var(--accent)"}`;
}

async function atualizarEstado() {
    const statusMsg = document.getElementById('status-msg');
    const statusIcon = document.getElementById('status-icon');
    const statusBar = document.getElementById('status-bar');

    try {
        const data = await obterEstado();

        if (data.error) {
            statusMsg.innerText = data.error;
            statusIcon.innerText = "🔴";
            statusBar.className = "status-error";
            return;
        }

        statusMsg.innerText = "Sistema Online | Sincronizado";
        statusIcon.innerText = "🟢";
        statusBar.className = "status-ok";

        if (data.polling_ms) pollingMs = data.polling_ms;
        document.getElementById('clock').innerText = data.hora;
        atualizarPauseUI(data.pausado);
        atualizarVelocidade(data.velocidade_pedida);
        atualizarBanner(data.evento_global);
        atualizarCronicas(data.cronicas);
    } catch (e) { console.error("Estado Error:", e); }
}

async function togglePause() {
    try {
        const data = await alternarPausa();
        atualizarPauseUI(data.pausado);
    } catch (e) { console.error("Pause Error:", e); }
}

async function setSpeed(v) {
    try {
        await definirVelocidade(v);
        atualizarVelocidade(v);
    } catch (e) { console.error("Speed Error:", e); }
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// app.js — nada de efeito colateral disparado só por importar este módulo.
export async function iniciarEstado() {
    await atualizarEstado(); // primeira resposta já ajusta pollingMs pro valor do config
    setInterval(atualizarEstado, pollingMs);
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'pausar': () => togglePause(),
    'velocidade': (alvo) => setSpeed(parseInt(alvo.dataset.valor, 10)),
});
