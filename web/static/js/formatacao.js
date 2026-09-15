/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): formatação e escape — um lugar só.
 * Junta o que estava espalhado em dashboard.js (getNPCAvatar, renderStatus, os dois
 * rótulos de estágio de vida) e mapa_leaflet.js (as tabelas de cor/emoji).
 */

// F01 (docs/16_PLANO_PAINEL_E_IA.md): renomeado de escapeHtmlMestre — todo texto
// vindo do servidor (nome, profissão, personalidade, resumo de evento) é ENTRADA
// NÃO CONFIÁVEL (pode ter vindo de um LLM); passa por aqui antes de ir pro DOM.
export function escaparHtml(str) {
    const div = document.createElement('div');
    div.innerText = str == null ? '' : String(str);
    return div.innerHTML;
}

export function getNPCAvatar(genero, estagio_vida) {
    if (estagio_vida === 'bebe') return '👶';
    if (estagio_vida === 'crianca') return genero === 'M' ? '👦' : '👧';
    if (estagio_vida === 'idoso') return genero === 'M' ? '👴' : '👵';
    if (estagio_vida === 'morto') return '💀';
    return genero === 'M' ? '👨' : '👩';
}

// F06 (docs/16_PLANO_PAINEL_E_IA.md): `corClasse` é um modificador de
// .status-fill (status-fill--energia/fome/social, ver style.css) — a largura
// contínua vai em data-percentual e é aplicada via setProperty por quem insere
// este HTML no DOM (painel_npcs.js::atualizarPainelHabitantes), nunca em style="".
export function renderStatus(icon, val, corClasse) {
    return `
        <div class="status-item">
            <span class="status-icon">${icon}</span>
            <div class="status-bar"><div class="status-fill ${corClasse}" data-percentual="${val}"></div></div>
        </div>
    `;
}

// Rótulo compacto do cartão da grade de habitantes (aba Habitantes). `profissao`
// pode ter vindo de geração por IA — F05 (docs/16_PLANO_PAINEL_E_IA.md): escapa
// aqui, na origem, pra todo chamador ganhar de graça.
export function rotuloEstagioCompacto(estagioVida, profissao) {
    return estagioVida === 'bebe' ? '🍼 Bebê' : (estagioVida === 'crianca' ? '🧸 Criança' : escaparHtml(profissao));
}

// Rótulo completo da ficha do habitante (modal de perfil).
export function rotuloEstagioCompleto(estagioVida) {
    return estagioVida === 'bebe' ? 'Bebê 👶' :
        (estagioVida === 'crianca' ? 'Criança 👦' :
        (estagioVida === 'idoso' ? 'Idoso(a) 👴👵' :
        (estagioVida === 'morto' ? 'Falecido(a) 💀' : 'Adulto(a) 🧑')));
}

// A residência é massa construída, não informação — tom neutro único, sem cor de
// categoria (Seção 6/E3 do 08_ESPEC_TECIDO_URBANO.md: com ~1.350 residências e ~48 prédios
// notáveis por cidade, dar cor de categoria a todas empasta a tela). A cor de categoria
// fica reservada pros notáveis, que são os que o jogador procura.
// Chaves conferidas contra engine.models.CategoriaLocal (F04, docs/
// 16_PLANO_PAINEL_E_IA.md): batem exatamente as 9.
export const CATEGORIA_EDIFICIO_COR = { residencia: '#9c8a76', fazenda: '#228B22', quartel: '#4682B4', taverna: '#D2691E', publico: '#696969', mercado: '#FFD700', forja: '#A9A9A9', universidade: '#5D3FD3', generic: '#808080' };

export const TIPO_CIDADE_EMOJI = { capital: '👑', fortaleza: '🏯', portuaria: '⚓', pesqueira: '🎣', comercial: '💰', mistica: '🔮', 'mística': '🔮', mineira: '⛏️', agricola: '🌾', 'agrícola': '🌾', residencial: '🏠' };

// M04 (docs/16_PLANO_PAINEL_E_IA.md): cor do ponto de cada NPC na camada de
// "habitantes se locomovendo" do Mapa Live, por ação atual — a lista de ações
// válidas vem de /api/habitantes/filtros (não copiada aqui); isto é só a
// apresentação (mesmo espírito de CATEGORIA_EDIFICIO_COR/TIPO_CIDADE_EMOJI).
// Chaves conferidas contra engine.models.Acao: batem exatamente as 7.
export const COR_POR_ACAO = {
    Dormir: '#7c3aed', Trabalhar: '#f59e0b', Socializar: '#22c55e', Comer: '#ef4444',
    Ocioso: '#94a3b8', 'Cuidar da Prole': '#38bdf8', Construindo: '#eab308',
};
export const COR_ACAO_PADRAO = '#ffffff';
