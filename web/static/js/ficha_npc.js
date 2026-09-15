/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): modal do habitante (ficha de vida +
 * crônicas pessoais) — extraído de dashboard.js. Reescrita em P03/P04 (ficha
 * resolvida no servidor); por enquanto é só a mesma lógica, movida.
 */
import { registrarAcoes } from './acoes.js';
import { AbaModal } from './constantes.js';
import { escaparHtml, getNPCAvatar, rotuloEstagioCompleto } from './formatacao.js';
import { obterRelacoesNpc, obterLogsNpc } from './api.js';
import { estado } from './estado_dashboard.js';

function getNPCNameById(npcId) {
    if (!npcId) return null;
    const found = estado.allNpcs.find(n => n.id === npcId);
    return found ? found.nome : "Desconhecido";
}

function getNPCChildren(npcId) {
    return estado.allNpcs.filter(n => n.bio.pai === npcId || n.bio.mae === npcId);
}

function getNPCRelationships(npcId) {
    return estado.allRels.filter(r => r.a === npcId);
}

function switchModalTab(tab) {
    estado.activeModalTab = tab;

    // Atualizar UI dos botões das abas
    document.getElementById('tab-profile-btn').classList.toggle('active', tab === AbaModal.PERFIL);
    document.getElementById('tab-logs-btn').classList.toggle('active', tab === AbaModal.LOGS);

    // Atualizar exibição dos blocos de conteúdo
    document.getElementById('modal-tab-profile').style.display = tab === AbaModal.PERFIL ? 'block' : 'none';
    document.getElementById('modal-tab-logs').style.display = tab === AbaModal.LOGS ? 'block' : 'none';
}

function renderNPCProfile(npc) {
    const avatar = getNPCAvatar(npc.bio.g, npc.bio.ev);
    const generoStr = npc.bio.g === 'M' ? 'Masculino ♂️' : 'Feminino ♀️';
    const estagioStr = rotuloEstagioCompleto(npc.bio.ev);

    // Pais
    const maeNome = getNPCNameById(npc.bio.mae);
    const paiNome = getNPCNameById(npc.bio.pai);

    const maeLink = npc.bio.mae ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.mae)}">👩 ${escaparHtml(maeNome)}</a>` : '<span style="color: var(--text-dim)">Desconhecida</span>';
    const paiLink = npc.bio.pai ? `<a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.pai)}">👨 ${escaparHtml(paiNome)}</a>` : '<span style="color: var(--text-dim)">Desconhecido</span>';

    // Cônjuge
    let conjugeLink = '<span style="color: var(--text-dim)">Nenhum</span>';
    if (npc.bio.ec === 'casado' && npc.bio.cj) {
        const conjugeNome = getNPCNameById(npc.bio.cj);
        conjugeLink = `<a href="#" style="color: var(--success); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.cj)}">💍 ${escaparHtml(conjugeNome)}</a>`;
    }

    // Filhos
    const filhos = getNPCChildren(npc.id);
    const filhosList = filhos.length > 0 ? filhos.map(f => `
        <li style="list-style: none; margin-bottom: 0.3rem;">
            <a href="#" style="color: var(--accent); text-decoration: none; font-weight: 600;" data-acao="abrir-ficha" data-npc-id="${escaparHtml(f.id)}">👶 ${escaparHtml(f.nome)} (${f.bio.ev === 'bebe' ? 'Bebê' : 'Criança'})</a>
        </li>
    `).join('') : '<span style="color: var(--text-dim)">Nenhum filho registrado.</span>';

    // Círculo Social
    const rels = getNPCRelationships(npc.id);
    const relsList = rels.length > 0 ? rels.map(r => {
        const outroNome = getNPCNameById(r.b);
        const afinidadeCor = r.af > 60 ? 'var(--success)' : (r.af < 30 ? 'var(--danger)' : 'var(--warning)');
        return `
            <div style="display:flex; justify-content:space-between; padding: 0.5rem; background: rgba(255,255,255,0.02); border-radius: 6px; margin-bottom: 0.4rem; font-size: 0.8rem; border-left: 3px solid ${afinidadeCor};">
                <span style="font-weight: 600; color: var(--text);">${escaparHtml(outroNome)}</span>
                <span style="color: var(--text-dim)">${escaparHtml(r.v)} (<strong style="color: ${afinidadeCor}">${r.af} afinidade</strong>)</span>
            </div>
        `;
    }).join('') : '<span style="color: var(--text-dim)">Sem conexões sociais expressivas.</span>';

    // Gestão de gravidez
    const gravidezHtml = npc.bio.gr > 0 ? `
        <div style="background: rgba(255,0,127,0.08); border: 1px dashed #ff007f; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; color: #ff007f; display:flex; align-items:center; gap: 0.8rem;">
            <span style="font-size: 1.5rem;">🤰</span>
            <div>
                <strong style="display:block">Período de Gestação Ativo</strong>
                <span style="font-size: 0.75rem; color: var(--text-dim);">Faltam ${npc.bio.gr} ticks virtuais para o nascimento do bebê!</span>
            </div>
        </div>
    ` : '';

    return `
        ${gravidezHtml}

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.5rem;">
            <!-- Informações Básicas -->
            <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">👤 Identidade</h4>
                <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.8rem;">
                    <div><span style="color: var(--text-dim)">Gênero:</span> <strong>${generoStr}</strong></div>
                    <div><span style="color: var(--text-dim)">Fase da Vida:</span> <strong>${estagioStr}</strong></div>
                    <div><span style="color: var(--text-dim)">Estado Civil:</span> <strong style="text-transform: capitalize;">${npc.bio.ec || 'solteiro'}</strong></div>
                    <div><span style="color: var(--text-dim)">Idade Biológica:</span> <strong style="color: var(--accent)">${npc.bio.idade || 0} anos</strong></div>
                    <div><span style="color: var(--text-dim)">Profissão:</span> <strong>${escaparHtml(npc.profissao)}</strong></div>
                    <div><span style="color: var(--text-dim)">Ação Atual:</span> <strong>${escaparHtml(npc.acao)}</strong></div>
                    <div><span style="color: var(--text-dim)">Saúde:</span> <strong style="color: ${npc.status.h > 40 ? 'var(--success)' : 'var(--danger)'}">${npc.status.h}%</strong></div>
                    <div><span style="color: var(--text-dim)">Humor:</span> <strong style="color: var(--warning)">${escaparHtml(npc.status.m)}</strong></div>
                    <div><span style="color: var(--text-dim)">Finanças:</span> <strong style="color: var(--success)">💰 ${npc.status.d}</strong></div>
                    <div><span style="color: var(--text-dim)">Data Nascimento:</span> <span>${npc.bio.dn.split('T')[0] || "Era Inicial"}</span></div>
                </div>
            </div>

            <!-- Família e Árvore Genealógica -->
            <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">👨‍👩‍👧 Árvore Genealógica</h4>
                <div style="display: flex; flex-direction: column; gap: 0.6rem; font-size: 0.8rem;">
                    <div><span style="color: var(--text-dim)">Mãe:</span> ${maeLink}</div>
                    <div><span style="color: var(--text-dim)">Pai:</span> ${paiLink}</div>
                    <div><span style="color: var(--text-dim)">Cônjuge:</span> ${conjugeLink}</div>
                    <div style="margin-top: 0.4rem;">
                        <span style="color: var(--text-dim); display:block; margin-bottom:0.3rem">Filhos:</span>
                        <ul style="padding-left: 0; margin: 0;">${filhosList}</ul>
                    </div>
                </div>
            </div>

            <!-- Relações Sociais -->
            <div style="grid-column: 1 / -1; background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04);">
                <h4 style="color: var(--accent); font-family: 'Outfit'; margin-bottom: 0.8rem; border-bottom: 1px solid rgba(56,189,248,0.1); padding-bottom: 0.4rem;">💬 Círculo de Relacionamentos</h4>
                <div style="max-height: 140px; overflow-y: auto; padding-right: 0.3rem;">
                    ${relsList}
                </div>
            </div>
        </div>
    `;
}

async function abrirHistorico(npcId) {
    estado.activeNpcId = npcId;
    const npcEncontrado = estado.allNpcs.find(n => n.id === npcId);
    const npcNome = npcEncontrado ? npcEncontrado.nome : "Desconhecido";
    const modal = document.getElementById('npc-log-modal');
    const title = document.getElementById('modal-npc-nome');
    const profileContainer = document.getElementById('modal-profile-details');
    const list = document.getElementById('modal-log-list');

    title.innerText = `Ficha de ${npcNome}`;
    list.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando logs...</p>`;
    profileContainer.innerHTML = `<p style="text-align: center; color: var(--text-dim);">Carregando ficha...</p>`;
    modal.classList.add('active');

    // Resetar aba padrão para Perfil
    switchModalTab(AbaModal.PERFIL);

    try {
        const dataRels = await obterRelacoesNpc(npcId);
        if (dataRels.rels) {
            estado.allRels = dataRels.rels.map(r => ({...r, a: npcId})); // Populate 'a' field to match old logic
        }

        const foundNpc = estado.allNpcs.find(n => n.id === npcId);
        if (foundNpc) {
            profileContainer.innerHTML = renderNPCProfile(foundNpc);
        }
    } catch (e) {
        console.error("Error loading relationships:", e);
    }

    try {
        const data = await obterLogsNpc(npcId);
        if (data.error) {
            list.innerHTML = `<p style="color: var(--danger); text-align: center;">Erro: ${escaparHtml(data.error)}</p>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            list.innerHTML = `<p style="color: var(--text-dim); text-align: center;">Nenhum registro de crônica encontrado para este habitante.</p>`;
            return;
        }

        list.innerHTML = data.logs.map(log => {
            const levelClass = `level-${log.l.toLowerCase()}`;
            return `
                <div class="npc-log-item ${levelClass}">
                    <div class="npc-log-meta">
                        <span>[${escaparHtml(log.l)}]</span>
                        <span>${escaparHtml(log.t)}</span>
                    </div>
                    <div>${escaparHtml(log.m)}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error("Error loading NPC logs:", e);
        list.innerHTML = `<p style="color: var(--danger); text-align: center;">Falha ao carregar os dados.</p>`;
    }
}

function fecharHistorico() {
    const modal = document.getElementById('npc-log-modal');
    modal.classList.remove('active');
    estado.activeNpcId = null;
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'abrir-ficha': (alvo) => abrirHistorico(alvo.dataset.npcId),
    // F01: só fecha quando o clique foi no próprio overlay/botão × — não quando um
    // clique dentro do conteúdo do modal borbulha até aqui (o conteúdo não tem
    // data-acao, então closest() sobe até o overlay; sem esta checagem qualquer
    // clique no modal inteiro o fecharia).
    'fechar-ficha': (alvo, ev) => { if (ev.target === alvo) fecharHistorico(); },
    'ficha-aba': (alvo) => switchModalTab(alvo.dataset.aba),
});
