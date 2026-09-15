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
            <div style="margin-top: 0.5rem; font-size: 0.65rem; color: #ff007f; background: rgba(255,0,127,0.08); border: 1px dashed #ff007f; padding: 2px 8px; border-radius: 6px; display: inline-block;">
                🤰 Gestante (${n.bio.gr} ticks)
            </div>
        ` : '';

        return `
            <div class="npc-card" style="${n.status.h <= 0 ? 'opacity: 0.6; filter: grayscale(50%);' : ''}">
                <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                    <h3 style="font-family:'Outfit'">${avatar} ${escaparHtml(n.nome)} ${n.status.h <= 0 ? '💀' : ''}</h3>
                    <span style="font-size:0.7rem; background:rgba(56,189,248,0.1); padding:2px 8px; border-radius:10px; color:var(--accent)">${n.status.h <= 0 ? 'FALECIDO' : escaparHtml(n.acao)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.2rem;">
                    <span style="font-size:0.8rem; color:var(--text-dim)">${stageLabel}</span>
                    <span style="font-size:0.7rem; color:var(--warning)">${n.status.h <= 0 ? 'Sem Humor' : escaparHtml(n.status.m)}</span>
                </div>
                ${pregnantBadge}

                <div class="health-bar" style="margin-top:0.8rem;">
                    <div class="health-fill" style="width:${n.status.h}%; background:${n.status.h > 30 ? 'var(--success)' : 'var(--danger)'}"></div>
                </div>
                <p style="font-size:0.6rem; color:var(--text-dim); margin-bottom:1rem; text-align:right">SAÚDE: ${n.status.h}%</p>
                <div class="status-row">
                    ${renderStatus('⚡', n.status.e, 'var(--accent)')}
                    ${renderStatus('🍗', n.status.f, 'var(--danger)')}
                    ${renderStatus('💬', n.status.s, 'var(--success)')}
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1rem;">
                    <div style="font-weight:bold; color:var(--warning)">💰 ${n.status.d}</div>
                    <button class="filter-btn" style="padding: 0.2rem 0.6rem; font-size: 0.7rem; border-color: rgba(56,189,248,0.3); color: var(--accent);" data-acao="abrir-ficha" data-npc-id="${escaparHtml(n.id)}">👤 Perfil</button>
                </div>
            </div>
        `;
    }).join('');
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'filtro-npc': (alvo) => setNpcFilter(alvo.dataset.filtro),
});
