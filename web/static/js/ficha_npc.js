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

    const maeLink = npc.bio.mae ? `<a href="#" class="link-simples cor-accent" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.mae)}">👩 ${escaparHtml(maeNome)}</a>` : '<span class="dim">Desconhecida</span>';
    const paiLink = npc.bio.pai ? `<a href="#" class="link-simples cor-accent" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.pai)}">👨 ${escaparHtml(paiNome)}</a>` : '<span class="dim">Desconhecido</span>';

    // Cônjuge
    let conjugeLink = '<span class="dim">Nenhum</span>';
    if (npc.bio.ec === 'casado' && npc.bio.cj) {
        const conjugeNome = getNPCNameById(npc.bio.cj);
        conjugeLink = `<a href="#" class="link-simples cor-success" data-acao="abrir-ficha" data-npc-id="${escaparHtml(npc.bio.cj)}">💍 ${escaparHtml(conjugeNome)}</a>`;
    }

    // Filhos
    const filhos = getNPCChildren(npc.id);
    const filhosList = filhos.length > 0 ? filhos.map(f => `
        <li class="ficha-filho-item">
            <a href="#" class="link-simples cor-accent" data-acao="abrir-ficha" data-npc-id="${escaparHtml(f.id)}">👶 ${escaparHtml(f.nome)} (${f.bio.ev === 'bebe' ? 'Bebê' : 'Criança'})</a>
        </li>
    `).join('') : '<span class="dim">Nenhum filho registrado.</span>';

    // Círculo Social
    const rels = getNPCRelationships(npc.id);
    const relsList = rels.length > 0 ? rels.map(r => {
        const outroNome = getNPCNameById(r.b);
        const afinidadeClasse = r.af > 60 ? 'afinidade-alta' : (r.af < 30 ? 'afinidade-baixa' : 'afinidade-media');
        return `
            <div class="rel-item ${afinidadeClasse}">
                <span class="rel-nome">${escaparHtml(outroNome)}</span>
                <span class="dim">${escaparHtml(r.v)} (<strong class="rel-afinidade">${r.af} afinidade</strong>)</span>
            </div>
        `;
    }).join('') : '<span class="dim">Sem conexões sociais expressivas.</span>';

    // Gestão de gravidez
    const gravidezHtml = npc.bio.gr > 0 ? `
        <div class="gravidez-box">
            <span class="gravidez-icone">🤰</span>
            <div>
                <strong class="gravidez-titulo">Período de Gestação Ativo</strong>
                <span class="gravidez-detalhe">Faltam ${npc.bio.gr} ticks virtuais para o nascimento do bebê!</span>
            </div>
        </div>
    ` : '';

    const saudeClasse = npc.status.h > 40 ? 'saude-ok' : 'saude-baixa';

    return `
        ${gravidezHtml}

        <div class="ficha-grid">
            <!-- Informações Básicas -->
            <div class="ficha-secao">
                <h4>👤 Identidade</h4>
                <div class="ficha-lista">
                    <div><span class="dim">Gênero:</span> <strong>${generoStr}</strong></div>
                    <div><span class="dim">Fase da Vida:</span> <strong>${estagioStr}</strong></div>
                    <div><span class="dim">Estado Civil:</span> <strong class="texto-capitalize">${npc.bio.ec || 'solteiro'}</strong></div>
                    <div><span class="dim">Idade Biológica:</span> <strong class="cor-accent">${npc.bio.idade || 0} anos</strong></div>
                    <div><span class="dim">Profissão:</span> <strong>${escaparHtml(npc.profissao)}</strong></div>
                    <div><span class="dim">Ação Atual:</span> <strong>${escaparHtml(npc.acao)}</strong></div>
                    <div><span class="dim">Saúde:</span> <strong class="${saudeClasse}">${npc.status.h}%</strong></div>
                    <div><span class="dim">Humor:</span> <strong class="cor-warning">${escaparHtml(npc.status.m)}</strong></div>
                    <div><span class="dim">Finanças:</span> <strong class="cor-success">💰 ${npc.status.d}</strong></div>
                    <div><span class="dim">Data Nascimento:</span> <span>${npc.bio.dn.split('T')[0] || "Era Inicial"}</span></div>
                </div>
            </div>

            <!-- Família e Árvore Genealógica -->
            <div class="ficha-secao">
                <h4>👨‍👩‍👧 Árvore Genealógica</h4>
                <div class="ficha-lista ficha-lista--arvore">
                    <div><span class="dim">Mãe:</span> ${maeLink}</div>
                    <div><span class="dim">Pai:</span> ${paiLink}</div>
                    <div><span class="dim">Cônjuge:</span> ${conjugeLink}</div>
                    <div class="ficha-filhos-bloco">
                        <span class="dim ficha-filhos-label">Filhos:</span>
                        <ul class="ficha-filhos-lista">${filhosList}</ul>
                    </div>
                </div>
            </div>

            <!-- Relações Sociais -->
            <div class="ficha-secao full">
                <h4>💬 Círculo de Relacionamentos</h4>
                <div class="ficha-relacoes-scroll">
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
    list.innerHTML = `<p class="modal-carregando">Carregando logs...</p>`;
    profileContainer.innerHTML = `<p class="modal-carregando">Carregando ficha...</p>`;
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
            list.innerHTML = `<p class="modal-erro">Erro: ${escaparHtml(data.error)}</p>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            list.innerHTML = `<p class="modal-carregando">Nenhum registro de crônica encontrado para este habitante.</p>`;
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
        list.innerHTML = `<p class="modal-erro">Falha ao carregar os dados.</p>`;
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
