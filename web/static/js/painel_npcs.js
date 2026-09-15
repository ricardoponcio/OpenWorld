/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): aba Habitantes (grade e filtro) —
 * extraído de dashboard.js. Reescrita em P04 (paginação/filtro no servidor); por
 * enquanto é só a mesma lógica, movida.
 */
import { registrarAcoes } from './acoes.js';
import { FiltroNpc } from './constantes.js';
import { escaparHtml, getNPCAvatar, renderStatus, rotuloEstagioCompacto } from './formatacao.js';
import { estado } from './estado_dashboard.js';

function setNpcFilter(filter) {
    estado.npcFilter = filter;
    // F03 (docs/16_PLANO_PAINEL_E_IA.md, Armadilha 19): decidia o botão ativo lendo
    // o TEXTO VISÍVEL do botão — quebraria se o rótulo mudasse. Agora usa o mesmo
    // `data-filtro` que a ação já lê.
    document.querySelectorAll('.filter-btn[data-filtro]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filtro === filter);
    });
    atualizarPainelHabitantes(estado.allNpcs);
}

// Chamada por navegacao.js — só quando a aba Habitantes está ativa (Armadilha 24:
// nada aqui decide sozinho se deve rodar, quem chama já filtrou por isso).
export function atualizarPainelHabitantes(npcs) {
    const grid = document.getElementById('npc-grid');

    // Aplicar o filtro na lista de habitantes
    let filteredNpcs = npcs;
    if (estado.npcFilter === FiltroNpc.VIVOS) {
        filteredNpcs = npcs.filter(n => n.status.h > 0);
    } else if (estado.npcFilter === FiltroNpc.MORTOS) {
        filteredNpcs = npcs.filter(n => n.status.h <= 0);
    }

    grid.innerHTML = filteredNpcs.map(n => {
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

    // F06 (docs/16_PLANO_PAINEL_E_IA.md): a largura contínua das barras não vai em
    // style="width:..." — fica numa variável CSS definida por propriedade,
    // consumida pelas regras .health-fill/.status-fill (style.css).
    grid.querySelectorAll('[data-percentual]').forEach(el => {
        el.style.setProperty('--percentual', el.dataset.percentual + '%');
    });
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'filtro-npc': (alvo) => setNpcFilter(alvo.dataset.filtro),
});
