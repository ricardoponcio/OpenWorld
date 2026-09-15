/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): Modo Mestre de IA (Frente 5) —
 * extraído de dashboard.js.
 */
import { registrarAcoes } from './acoes.js';
import { escaparHtml } from './formatacao.js';
import {
    obterHistoricoMestre, enviarMensagemAoMestre, avancarTempoDoMestre, confirmarAcoesDoMestre,
} from './api.js';

function renderMestreChatLog(historico) {
    const log = document.getElementById('mestre-chat-log');
    log.innerHTML = historico.map(h => {
        const ehJogador = h.autor === 'jogador';
        return `
            <div style="align-self:${ehJogador ? 'flex-end' : 'flex-start'}; max-width: 80%; background: ${ehJogador ? 'var(--accent)' : 'rgba(255,255,255,0.06)'}; color: ${ehJogador ? '#04202e' : 'inherit'}; padding: 0.6rem 0.9rem; border-radius: 14px; font-size: 0.85rem; white-space: pre-wrap;">
                ${escaparHtml(h.mensagem)}
            </div>
        `;
    }).join('');
    log.scrollTop = log.scrollHeight;

    // Mostra o painel de confirmação se a última mensagem do Mestre tiver ações pendentes
    const ultima = historico[historico.length - 1];
    const painel = document.getElementById('mestre-acoes-pendentes');
    if (ultima && ultima.autor === 'mestre' && !ultima.aplicada && ultima.acoes_propostas && ultima.acoes_propostas.length > 0) {
        painel.style.display = 'block';
        painel.innerHTML = `
            <div class="info-card" style="border: 1px solid var(--accent);">
                <strong style="font-size:0.85rem;">⚡ O Mestre propôs ${ultima.acoes_propostas.length} ação(ões) no mundo:</strong>
                <ul style="font-size:0.8rem; color: var(--text-dim); margin: 0.4rem 0;">
                    ${ultima.acoes_propostas.map(a => `<li>${escaparHtml(a.comando)} ${escaparHtml(a.id || '')}</li>`).join('')}
                </ul>
                <button class="filter-btn active" data-acao="confirmar-acoes" data-conversa-id="${ultima.id}">✅ Confirmar</button>
                <button class="filter-btn" data-acao="ignorar-acoes">✋ Ignorar</button>
            </div>
        `;
    } else {
        painel.style.display = 'none';
    }
}

export async function carregarHistoricoMestre() {
    try {
        const data = await obterHistoricoMestre();
        if (data.historico) renderMestreChatLog(data.historico);
    } catch (e) { console.error("Erro ao carregar histórico do Mestre:", e); }
}

export async function enviarMensagemMestre() {
    const input = document.getElementById('mestre-input');
    const mensagem = input.value.trim();
    if (!mensagem) return;
    input.value = '';
    input.disabled = true;
    try {
        const data = await enviarMensagemAoMestre(mensagem);
        if (data.error) {
            alert('Erro: ' + data.error);
        } else {
            await carregarHistoricoMestre();
        }
    } catch (e) {
        console.error("Erro ao enviar mensagem ao Mestre:", e);
    } finally {
        input.disabled = false;
        input.focus();
    }
}

async function avancarTempoMestre(minutos) {
    const log = document.getElementById('mestre-chat-log');
    log.insertAdjacentHTML('beforeend', `<div id="mestre-aguardando" style="text-align:center; color: var(--text-dim); font-size:0.8rem;">⏳ Avançando ${minutos} minutos de jogo...</div>`);
    log.scrollTop = log.scrollHeight;
    try {
        const data = await avancarTempoDoMestre(minutos);
        if (data.error) {
            alert('Erro: ' + data.error);
        }
        await carregarHistoricoMestre();
    } catch (e) {
        console.error("Erro ao avançar tempo:", e);
    }
}

async function confirmarAcoesMestre(conversaId) {
    try {
        const data = await confirmarAcoesDoMestre(conversaId);
        if (data.error) {
            alert('Erro: ' + data.error);
        } else {
            document.getElementById('mestre-acoes-pendentes').style.display = 'none';
            // F01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): a ação foi ENFILEIRADA, não
            // aplicada na hora — só vira efeito de verdade quando run_simulation.py
            // drenar a fila (próximo tick, ou próxima volta do laço se pausado).
            let texto = 'Enviado (será aplicado no próximo tick da simulação):\n' + (data.resultados || []).join('\n');
            if (data.aviso) texto += '\n\n⚠️ ' + data.aviso;
            alert(texto);
        }
    } catch (e) { console.error("Erro ao confirmar ações do Mestre:", e); }
}

function ignorarAcoesMestre() {
    document.getElementById('mestre-acoes-pendentes').style.display = 'none';
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'avancar-tempo': (alvo) => avancarTempoMestre(parseInt(alvo.dataset.minutos, 10)),
    'enviar-mensagem': () => enviarMensagemMestre(),
    'confirmar-acoes': (alvo) => confirmarAcoesMestre(alvo.dataset.conversaId),
    'ignorar-acoes': () => ignorarAcoesMestre(),
});
