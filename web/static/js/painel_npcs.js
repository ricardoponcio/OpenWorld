/**
 * P04 (docs/16_PLANO_PAINEL_E_IA.md): aba Habitantes — filtro e paginação
 * resolvidos no servidor (/api/habitantes), nunca mais a lista inteira do mundo
 * (F05/P01 só tinham movido a versão antiga de dashboard.js pra cá; esta é a
 * reescrita real). Não faz polling: recarrega ao mudar filtro/página, ao clicar
 * "↻ Atualizar", e a cada `painel.estatisticas_polling_ms` só se a aba estiver
 * visível.
 */
import { registrarAcoes } from './acoes.js';
import { Aba } from './constantes.js';
import { escaparHtml, getNPCAvatar, renderStatus, rotuloEstagioCompacto, rotuloEstagioCompleto } from './formatacao.js';
import { obterHabitantes, obterFiltrosHabitantes } from './api.js';
import { estado } from './estado_dashboard.js';

// Detalhe de UI (não é config do servidor) — quanto esperar depois da última
// tecla digitada antes de refazer a busca.
const ATRASO_BUSCA_MS = 300;

// P04: estado privado deste módulo — filtro/paginação da aba Habitantes não é
// compartilhado com nenhum outro módulo (ARQUITETURA §10 regra 4).
const estadoHabitantes = {
    cidade: '', busca: '', estagio: '', acao: '', situacao: 'vivos',
    pagina: 1, porPagina: 50, total: 0, timerBusca: null,
};

function preencherSelect(id, opcoes, rotuloTodos) {
    const select = document.getElementById(id);
    select.innerHTML = `<option value="">${escaparHtml(rotuloTodos)}</option>` +
        opcoes.map(o => `<option value="${escaparHtml(o.valor)}">${escaparHtml(o.rotulo)}</option>`).join('');
}

async function carregarFiltros() {
    const dados = await obterFiltrosHabitantes();
    estadoHabitantes.porPagina = dados.painel.habitantes_por_pagina;

    preencherSelect('npc-filtro-cidade', dados.cidades.map(c => ({ valor: c.id, rotulo: c.nome })), 'Todas as cidades');
    preencherSelect('npc-filtro-estagio', dados.estagios.map(e => ({ valor: e, rotulo: rotuloEstagioCompleto(e) })), 'Toda fase de vida');
    preencherSelect('npc-filtro-acao', dados.acoes.map(a => ({ valor: a, rotulo: a })), 'Toda ação');

    return dados;
}

function renderizarGrade(habitantes) {
    const grid = document.getElementById('npc-grid');

    grid.innerHTML = habitantes.map(n => {
        const avatar = getNPCAvatar(n.bio.g, n.bio.ev);
        const stageLabel = rotuloEstagioCompacto(n.bio.ev, n.profissao);
        const pregnantBadge = n.bio.gr > 0 ? `
            <div class="badge-gestante">
                🤰 Gestante (${n.bio.gr} ticks)
            </div>
        ` : '';
        const saudeClasse = n.status.h > 30 ? 'saude-ok' : 'saude-baixa';

        return `
            <div class="npc-card ${n.status.h <= 0 ? 'falecido' : ''}">
                <div class="npc-card-header">
                    <h3 class="npc-card-nome">${avatar} ${escaparHtml(n.nome)} ${n.status.h <= 0 ? '💀' : ''}</h3>
                    <span class="npc-card-acao">${n.status.h <= 0 ? 'FALECIDO' : escaparHtml(n.acao)}</span>
                </div>
                <div class="npc-card-subrow">
                    <span class="npc-card-estagio">${stageLabel}</span>
                    <span class="npc-card-humor">${n.status.h <= 0 ? 'Sem Humor' : escaparHtml(n.status.m)}</span>
                </div>
                ${pregnantBadge}

                <div class="health-bar">
                    <div class="health-fill ${saudeClasse}" data-percentual="${n.status.h}"></div>
                </div>
                <p class="npc-card-saude-label">SAÚDE: ${n.status.h}%</p>
                <div class="status-row">
                    ${renderStatus('⚡', n.status.e, 'status-fill--energia')}
                    ${renderStatus('🍗', n.status.f, 'status-fill--fome')}
                    ${renderStatus('💬', n.status.s, 'status-fill--social')}
                </div>
                <div class="npc-card-footer">
                    <div class="npc-card-dinheiro">💰 ${n.status.d}</div>
                    <button class="filter-btn perfil-btn" data-acao="abrir-ficha" data-npc-id="${escaparHtml(n.id)}">👤 Perfil</button>
                </div>
            </div>
        `;
    }).join('');

    // F06 (docs/16_PLANO_PAINEL_E_IA.md): --percentual via setProperty, nunca
    // style="width:...".
    grid.querySelectorAll('[data-percentual]').forEach(el => {
        el.style.setProperty('--percentual', el.dataset.percentual + '%');
    });
}

function atualizarPaginacao() {
    const totalPaginas = Math.max(1, Math.ceil(estadoHabitantes.total / estadoHabitantes.porPagina));
    document.getElementById('npc-pagina-label').innerText = `página ${estadoHabitantes.pagina} de ${totalPaginas}`;
}

export async function carregarPaginaHabitantes() {
    const dados = await obterHabitantes({
        cidade: estadoHabitantes.cidade, busca: estadoHabitantes.busca,
        estagio: estadoHabitantes.estagio, acao: estadoHabitantes.acao,
        situacao: estadoHabitantes.situacao,
        pagina: estadoHabitantes.pagina, por_pagina: estadoHabitantes.porPagina,
    });
    if (dados.error) { console.error("Habitantes Error:", dados.error); return; }

    estadoHabitantes.total = dados.total;
    renderizarGrade(dados.habitantes);
    atualizarPaginacao();
}

function refiltrar(campo, valor) {
    estadoHabitantes[campo] = valor;
    estadoHabitantes.pagina = 1;
    carregarPaginaHabitantes();
}

function setSituacao(btn, situacao) {
    document.querySelectorAll('[data-acao="npc-situacao"]').forEach(b => {
        b.classList.toggle('active', b.dataset.situacao === situacao);
    });
    refiltrar('situacao', situacao);
}

function aoDigitarBusca(valor) {
    clearTimeout(estadoHabitantes.timerBusca);
    estadoHabitantes.timerBusca = setTimeout(() => refiltrar('busca', valor), ATRASO_BUSCA_MS);
}

function irParaPaginaAnterior() {
    if (estadoHabitantes.pagina > 1) { estadoHabitantes.pagina--; carregarPaginaHabitantes(); }
}

function irParaProximaPagina() {
    const totalPaginas = Math.max(1, Math.ceil(estadoHabitantes.total / estadoHabitantes.porPagina));
    if (estadoHabitantes.pagina < totalPaginas) { estadoHabitantes.pagina++; carregarPaginaHabitantes(); }
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// app.js. Os <select>/input de filtro disparam 'change'/'input', não 'click' —
// fora do alcance do despachar() (que só ouve clique); ganham listener direto
// aqui, uma vez só, mesmo padrão do Enter do campo do Mestre em navegacao.js.
export async function iniciarPainelHabitantes() {
    const dados = await carregarFiltros();

    document.getElementById('npc-filtro-cidade').addEventListener('change', (ev) => refiltrar('cidade', ev.target.value));
    document.getElementById('npc-filtro-estagio').addEventListener('change', (ev) => refiltrar('estagio', ev.target.value));
    document.getElementById('npc-filtro-acao').addEventListener('change', (ev) => refiltrar('acao', ev.target.value));
    document.getElementById('npc-filtro-busca').addEventListener('input', (ev) => aoDigitarBusca(ev.target.value));

    setInterval(() => {
        if (estado.activeView === Aba.HABITANTES) carregarPaginaHabitantes();
    }, dados.painel.estatisticas_polling_ms);
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'npc-situacao': (alvo) => setSituacao(alvo, alvo.dataset.situacao),
    'npc-atualizar': () => carregarPaginaHabitantes(),
    'npc-pagina-anterior': () => irParaPaginaAnterior(),
    'npc-pagina-proxima': () => irParaProximaPagina(),
});
