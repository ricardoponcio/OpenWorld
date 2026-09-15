/**
 * P05 (docs/16_PLANO_PAINEL_E_IA.md): aba Estatísticas — só CONSOME o retrato que
 * `ColetorDeEstatisticas`/`run_simulation.py` gravam em `MetaChave.ESTATISTICAS`
 * (O03); nunca agrega NPCs por conta própria (Armadilha 24). Não faz polling
 * fora daqui: recarrega ao trocar pra esta aba (navegacao.js) e a cada
 * `painel.estatisticas_polling_ms` só com a aba visível.
 */
import { Aba } from './constantes.js';
import { escaparHtml } from './formatacao.js';
import { obterEstatisticas } from './api.js';
import { estado } from './estado_dashboard.js';

// Chute inicial até a primeira resposta trazer `polling_ms` do config
// (painel.estatisticas_polling_ms) — mesmo padrão de estado.js (P02).
let pollingMs = 5000;

const ROTULO_CONTADOR = {
    nascimento: '👶 Nascimentos', obito_velhice: '💀 Óbitos (velhice)', obito_saude: '💀 Óbitos (saúde/fome)',
    casamento: '💍 Casamentos', refeicao_parcial: '🍽️ Refeições parciais',
    sem_dinheiro_sem_sopao: '💸 Sem dinheiro e sem sopão', minuto_em_inanicao: '⏳ Minutos em inanição',
};

function formatarSaldo(valor) {
    return `${Math.round(valor || 0).toLocaleString('pt-BR')} pc`;
}

function renderizarDesempenho(desempenho) {
    const el = document.getElementById('stats-desempenho');
    if (!desempenho) { el.innerText = 'Ainda sem medição — aguarde o primeiro retrato.'; return; }
    el.innerHTML = `
        <div class="stats-linha"><span class="dim">Velocidade:</span> <strong>${desempenho.velocidade_efetiva.toFixed(0)}× efetivo</strong> <span class="dim">(pedido ${desempenho.velocidade_pedida.toFixed(0)}×)</span></div>
        <div class="stats-linha"><span class="dim">ms/tick médio:</span> <strong>${desempenho.ms_por_tick_medio.toFixed(1)}</strong></div>
        <div class="stats-linha"><span class="dim">ms/tick p95:</span> <strong>${desempenho.ms_por_tick_p95.toFixed(1)}</strong></div>
    `;
}

function renderizarContadores(elId, contadores) {
    const el = document.getElementById(elId);
    if (!contadores) { el.innerText = 'Sem dados ainda.'; return; }
    el.innerHTML = Object.entries(ROTULO_CONTADOR).map(([chave, rotulo]) =>
        `<div class="stats-linha"><span class="dim">${rotulo}:</span> <strong>${contadores[chave] || 0}</strong></div>`
    ).join('');
}

function renderizarTabelaCidades(porCidade) {
    const corpo = document.getElementById('stats-tabela-corpo');
    corpo.innerHTML = Object.values(porCidade || {}).map(c => {
        const v = c.vivos_por_estagio || {};
        return `
            <tr>
                <td>${escaparHtml(c.nome || '—')}</td>
                <td>${v.bebe || 0}</td><td>${v.crianca || 0}</td><td>${v.adulto || 0}</td><td>${v.idoso || 0}</td>
                <td>${c.empregados || 0}</td><td>${c.desempregados || 0}</td><td>${c.famintos || 0}</td><td>${c.saldo_zerado || 0}</td>
                <td>${formatarSaldo(c.mediana_saldo_pc)}</td>
            </tr>
        `;
    }).join('');
}

export async function carregarEstatisticas() {
    try {
        const dados = await obterEstatisticas();
        if (dados.polling_ms) pollingMs = dados.polling_ms;
        renderizarDesempenho(dados.desempenho);
        renderizarContadores('stats-hoje', dados.hoje);
        renderizarContadores('stats-ontem', dados.dia_anterior);
        renderizarTabelaCidades(dados.por_cidade);
    } catch (e) { console.error("Estatisticas Error:", e); }
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// app.js — nada de efeito colateral disparado só por importar este módulo.
export async function iniciarPainelEstatisticas() {
    await carregarEstatisticas(); // primeira resposta já ajusta pollingMs pro valor do config
    setInterval(() => {
        if (estado.activeView === Aba.ESTATISTICAS) carregarEstatisticas();
    }, pollingMs);
}
