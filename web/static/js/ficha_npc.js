/**
 * P03/P04 (docs/16_PLANO_PAINEL_E_IA.md): modal do habitante (ficha de vida +
 * crônicas pessoais) — reescrito contra /api/habitantes/<id>, que já resolve
 * nomes de mãe/pai/cônjuge e filhos no servidor (RepositorioNPC.buscar_ficha).
 * Nunca mais varre uma lista local de NPCs (a antiga `allNpcs`, que P01
 * eliminou) nem chama a antiga `abrirHistorico`.
 */
import { registrarAcoes } from './acoes.js';
import { AbaModal } from './constantes.js';
import { escaparHtml, getNPCAvatar, rotuloEstagioCompleto } from './formatacao.js';
import { obterFichaHabitante, obterRelacoesNpc, obterLogsNpc } from './api.js';
import { estado } from './estado_dashboard.js';

function switchModalTab(tab) {
    estado.activeModalTab = tab;

    // Atualizar UI dos botões das abas
    document.getElementById('tab-profile-btn').classList.toggle('active', tab === AbaModal.PERFIL);
    document.getElementById('tab-logs-btn').classList.toggle('active', tab === AbaModal.LOGS);

    // Atualizar exibição dos blocos de conteúdo
    document.getElementById('modal-tab-profile').style.display = tab === AbaModal.PERFIL ? 'block' : 'none';
    document.getElementById('modal-tab-logs').style.display = tab === AbaModal.LOGS ? 'block' : 'none';
}

function montarLinkNpc(id, nome, emoji, corClasse) {
    if (!id) return null;
    return `<a href="#" class="link-simples ${corClasse}" data-acao="abrir-ficha" data-npc-id="${escaparHtml(id)}">${emoji} ${escaparHtml(nome)}</a>`;
}

function montarListaFilhos(filhos) {
    return filhos.length > 0 ? filhos.map(f => `
        <li class="ficha-filho-item">
            <a href="#" class="link-simples cor-accent" data-acao="abrir-ficha" data-npc-id="${escaparHtml(f.id)}">👶 ${escaparHtml(f.nome)} (${f.estagio_vida === 'bebe' ? 'Bebê' : 'Criança'})</a>
        </li>
    `).join('') : '<span class="dim">Nenhum filho registrado.</span>';
}

function montarListaRelacoes(rels) {
    return rels.length > 0 ? rels.map(r => {
        const afinidadeClasse = r.af > 60 ? 'afinidade-alta' : (r.af < 30 ? 'afinidade-baixa' : 'afinidade-media');
        return `
            <div class="rel-item ${afinidadeClasse}">
                <span class="rel-nome">${escaparHtml(r.nome)}</span>
                <span class="dim">${escaparHtml(r.v)} (<strong class="rel-afinidade">${r.af} afinidade</strong>)</span>
            </div>
        `;
    }).join('') : '<span class="dim">Sem conexões sociais expressivas.</span>';
}

function montarHtmlFicha(npc, rels) {
    const avatar = getNPCAvatar(npc.bio.g, npc.bio.ev);
    const generoStr = npc.bio.g === 'M' ? 'Masculino ♂️' : 'Feminino ♀️';
    const estagioStr = rotuloEstagioCompleto(npc.bio.ev);

    const maeLink = montarLinkNpc(npc.bio.mae, npc.mae_nome, '👩', 'cor-accent') || '<span class="dim">Desconhecida</span>';
    const paiLink = montarLinkNpc(npc.bio.pai, npc.pai_nome, '👨', 'cor-accent') || '<span class="dim">Desconhecido</span>';
    const conjugeLink = (npc.bio.ec === 'casado' && npc.bio.cj)
        ? montarLinkNpc(npc.bio.cj, npc.conjuge_nome, '💍', 'cor-success')
        : '<span class="dim">Nenhum</span>';

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
                        <ul class="ficha-filhos-lista">${montarListaFilhos(npc.filhos)}</ul>
                    </div>
                </div>
            </div>

            <!-- Relações Sociais -->
            <div class="ficha-secao full">
                <h4>💬 Círculo de Relacionamentos</h4>
                <div class="ficha-relacoes-scroll">
                    ${montarListaRelacoes(rels)}
                </div>
            </div>
        </div>
    `;
}

async function abrirFicha(npcId) {
    estado.activeNpcId = npcId;
    const modal = document.getElementById('npc-log-modal');
    const title = document.getElementById('modal-npc-nome');
    const profileContainer = document.getElementById('modal-profile-details');
    const list = document.getElementById('modal-log-list');

    title.innerText = 'Carregando...';
    list.innerHTML = `<p class="modal-carregando">Carregando logs...</p>`;
    profileContainer.innerHTML = `<p class="modal-carregando">Carregando ficha...</p>`;
    modal.classList.add('active');
    switchModalTab(AbaModal.PERFIL); // Resetar aba padrão para Perfil

    try {
        const [npc, dataRels] = await Promise.all([obterFichaHabitante(npcId), obterRelacoesNpc(npcId)]);
        if (npc.error) {
            title.innerText = 'Ficha não encontrada';
            profileContainer.innerHTML = `<p class="modal-erro">${escaparHtml(npc.error)}</p>`;
        } else {
            title.innerText = `Ficha de ${npc.nome}`;
            profileContainer.innerHTML = montarHtmlFicha(npc, dataRels.rels || []);
        }
    } catch (e) {
        console.error("Error loading ficha:", e);
        profileContainer.innerHTML = `<p class="modal-erro">Falha ao carregar a ficha.</p>`;
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

function fecharFicha() {
    const modal = document.getElementById('npc-log-modal');
    modal.classList.remove('active');
    estado.activeNpcId = null;
}

// F01: cada módulo registra as próprias ações — evita import circular com app.js.
registrarAcoes({
    'abrir-ficha': (alvo) => abrirFicha(alvo.dataset.npcId),
    // F01: só fecha quando o clique foi no próprio overlay/botão × — não quando um
    // clique dentro do conteúdo do modal borbulha até aqui (o conteúdo não tem
    // data-acao, então closest() sobe até o overlay; sem esta checagem qualquer
    // clique no modal inteiro o fecharia).
    'fechar-ficha': (alvo, ev) => { if (ev.target === alvo) fecharFicha(); },
    'ficha-aba': (alvo) => switchModalTab(alvo.dataset.aba),
});
