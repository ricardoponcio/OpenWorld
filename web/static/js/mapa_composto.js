/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): início e navegação do mapa mundi em
 * canvas (mapa mundi / continente / cidade) — o resto do mapa em canvas foi
 * extraído pra mapa_composto_estado.js, mapa_composto_desenho.js e
 * mapa_composto_interacao.js (era 723 linhas, acima do limite de 250).
 *
 * Um pouco acima do limite de 250 (ARQUITETURA §4 aceita estourar com
 * justificativa escrita): loadContinents() sozinha soma ~65 — é montagem de DOM
 * (lista de continentes/cidades na barra lateral), não navegação por si só, mas
 * não há um arquivo próprio pra isso na tabela de módulos deste bloco (F05) e criar
 * um só pra ~65 linhas pareceu pior que o estouro. Revisitar se este arquivo
 * crescer mais.
 */
import { Modo } from './constantes.js';
import { canvas, estado, img } from './mapa_composto_estado.js';
import { draw, animateLoop } from './mapa_composto_desenho.js';
import { iniciarInteracaoMapaComposto } from './mapa_composto_interacao.js';
import { obterContinentes, obterEntidadesRegiao } from './api.js';
import { escaparHtml } from './formatacao.js';

// Load Continents from API
function loadContinents() {
    obterContinentes()
        .then(data => {
            estado.cachedContinents = data.continentes || [];
            estado.cachedBiomas = data.biomas || {};
            draw(); // Redraw map to show markers

            const container = document.getElementById('continents-list-container');
            container.innerHTML = '';

            data.continentes.forEach(c => {
                const wrapper = document.createElement('div');
                wrapper.className = 'continent-wrapper';

                const btn = document.createElement('button');
                btn.className = 'continent-btn';
                btn.id = `btn-c-${c.uuid}`;

                const emoji = c.area_real_km2 > 50000 ? '🏔️' : '🏝️';
                const statusText = c.gerado ? 'Zoom Pronto' : 'Gerar Zoom';

                btn.innerHTML = `
                    <span class="continent-emoji">${emoji}</span>
                    <span class="continent-details">
                        <span class="continent-name">${escaparHtml(c.nome)}</span>
                        <span class="continent-info-small">${c.area_real_km2.toLocaleString()} km²</span>
                    </span>
                    <span class="continent-status">${statusText}</span>
                `;

                btn.addEventListener('click', () => selectContinent(c.uuid, c.nome, btn));
                wrapper.appendChild(btn);

                // Cidades Nested
                if (c.cidades && c.cidades.length > 0) {
                    const citiesDiv = document.createElement('div');
                    citiesDiv.className = 'cities-list';
                    citiesDiv.style.paddingLeft = '20px';
                    citiesDiv.style.borderLeft = '2px solid rgba(255,255,255,0.1)';
                    citiesDiv.style.marginLeft = '12px';
                    citiesDiv.style.marginBottom = '10px';

                    c.cidades.forEach(cid => {
                        const cidBtn = document.createElement('button');
                        cidBtn.className = 'continent-btn city-btn';
                        cidBtn.style.padding = '0.4rem 0.6rem';
                        cidBtn.style.marginTop = '4px';
                        cidBtn.innerHTML = `
                            <span class="continent-emoji">🏰</span>
                            <span class="continent-details">
                                <span class="continent-name" style="font-size: 0.85rem">${escaparHtml(cid.nome)}</span>
                                <span class="continent-info-small">${escaparHtml(cid.tamanho)} | ${escaparHtml(cid.tipo)}</span>
                            </span>
                        `;
                        cidBtn.addEventListener('click', () => selectCity(cid.nome, cidBtn, c.nome));
                        citiesDiv.appendChild(cidBtn);
                    });
                    wrapper.appendChild(citiesDiv);
                }

                container.appendChild(wrapper);
            });
        })
        .catch(err => console.error("Erro ao carregar continentes:", err));
}

// Select Continent Action
function selectContinent(uuid, nome, btnElement) {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-global-map').classList.remove('active');
    btnElement.classList.add('active');
    btnElement.classList.add('loading');

    const statusSpan = btnElement.querySelector('.continent-status');
    const originalStatus = statusSpan.innerText;
    statusSpan.innerText = 'Processando...';

    estado.currentMode = Modo.CONTINENTE;
    estado.currentContinentUuid = uuid;

    document.getElementById('status-mapa').innerText = `⏳ Gerando/Carregando ${nome}...`;
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = `/api/continente/${uuid}/imagem`;

    img.onload = function() {
        btnElement.classList.remove('loading');
        statusSpan.innerText = 'Zoom Pronto';

        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        draw();

        // UI adjustments for Continent Mode
        document.getElementById('status-mapa').innerText = `🟢 Continente: ${nome} (Zoom)`;
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';

        document.getElementById('lblInspectorTitle').innerText = `🔍 Relevo - ${nome}`;
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'block';

        document.getElementById('lblInstructionTitle').innerText = `🏔️ Alta Resolução (ROI Zoom):`;
        document.getElementById('lblInstructionTip1').innerText = `• Mapa ampliado dinamicamente para 1200x1200px.`;
        document.getElementById('lblInstructionTip2').innerText = `• Processamento avançado de micro-fraturas e detalhes costeiros.`;
    };
}

// Select City Action
function selectCity(nome, btnElement, continenteNome) {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-global-map').classList.remove('active');
    btnElement.classList.add('active');
    btnElement.classList.add('loading');

    estado.currentMode = Modo.CIDADE;
    estado.currentCityNome = nome;
    estado.currentContinentUuid = null;

    document.getElementById('status-mapa').innerText = `⏳ Gerando/Carregando ${nome}...`;
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    // D7 do DIAGNOSTICO_V3 (2026-09-11): renomeado de /api/cidade/ para /api/regiao/ —
    // esta view mostra ONDE a cidade fica no continente (~190km de raio), não o que tem
    // dentro dela. A vista urbana de verdade (ruas/edifícios/lotes) é a camada vetorial
    // do Mapa Live (aba 🗾, corrigida no D3) — ela não perde qualidade ao ampliar.
    img.src = `/api/regiao/${nome}/imagem`;

    img.onload = function() {
        btnElement.classList.remove('loading');

        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        estado.npcAnimations = {};
        if (!estado.isAnimating) {
            estado.isAnimating = true;
            animateLoop();
        }

        obterEntidadesRegiao(nome)
            .then(data => {
                if (!data.error) {
                    estado.cityEntities = data;
                    draw();
                }
            });

        document.getElementById('status-mapa').innerText = `🌍 Região de ${nome} (a cidade é o ponto no centro — veja o Mapa Live pra ruas e edifícios)`;
        document.getElementById('status-mapa').style.borderColor = '#00ffcc';
        document.getElementById('status-mapa').style.color = '#00ffcc';

        document.getElementById('lblInspectorTitle').innerText = `🔍 Relevo Regional - ${nome}`;
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'none';

        document.getElementById('lblInstructionTitle').innerText = `🏰 Alta Resolução (City Zoom):`;
        document.getElementById('lblInstructionTip1').innerText = `• Mapa focado ampliado dinamicamente.`;
        document.getElementById('lblInstructionTip2').innerText = `• Preparado para receber marcadores e construções da Engine.`;
    };
}

// Global Map select
function aoClicarMapaGlobal() {
    document.querySelectorAll('.continent-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');

    estado.currentMode = Modo.GLOBAL;
    estado.currentContinentUuid = null;
    estado.currentCityNome = null;
    estado.cityEntities = { locais: [], npcs: [], bbox: null };

    document.getElementById('status-mapa').innerText = '⏳ Sincronizando Mapa Mundi...';
    document.getElementById('status-mapa').style.borderColor = 'var(--warning)';
    document.getElementById('status-mapa').style.color = 'var(--warning)';

    img.src = '/api/mapa_composto/imagem';

    img.onload = function() {
        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;
        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        estado.isAnimating = false;
        draw();

        document.getElementById('status-mapa').innerText = '🟢 Mapa Mundi Global (768x768)';
        document.getElementById('status-mapa').style.borderColor = 'var(--accent)';
        document.getElementById('status-mapa').style.color = 'var(--accent)';

        document.getElementById('lblInspectorTitle').innerText = '🔍 Inspetor do Mapa Mundi';
        const terrainMetrics = document.getElementById('terrainMetricsContainer');
        if(terrainMetrics) terrainMetrics.style.display = 'block';

        document.getElementById('lblInstructionTitle').innerText = '💡 Visualização do Mapa Mundi:';
        document.getElementById('lblInstructionTip1').innerText = '• Cada tile do mapa composto possui tamanho fixo de 256x256 pixels.';
        document.getElementById('lblInstructionTip2').innerText = '• Ao passar o mouse, a grade acima acende mostrando qual tile você está inspecionando.';
    };
}

// F01 (docs/16_PLANO_PAINEL_E_IA.md): ponto de início explícito, chamado por
// app.js — nada de efeito colateral disparado só por importar este módulo.
export function iniciarMapaComposto() {
    iniciarInteracaoMapaComposto();
    document.getElementById('btn-global-map').addEventListener('click', aoClicarMapaGlobal);

    img.onload = function() {
        canvas.width = 600;
        canvas.height = 600;

        estado.minScale = Math.min(canvas.width / img.width, canvas.height / img.height);
        estado.scale = estado.minScale;

        estado.offsetX = (canvas.width - img.width * estado.scale) / 2;
        estado.offsetY = (canvas.height - img.height * estado.scale) / 2;

        draw();
    };
    img.src = '/api/mapa_composto/imagem';

    loadContinents();
}
