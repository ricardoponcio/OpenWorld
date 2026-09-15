/**
 * F05 (docs/16_PLANO_PAINEL_E_IA.md, Bloco F): estilos das camadas vetoriais do Mapa
 * Live — extraído de mapa_leaflet.js.
 */
import { CATEGORIA_EDIFICIO_COR } from './formatacao.js';
import { estado } from './mapa_leaflet_estado.js';

// Estilo de linha/polígono por camada de detalhe de cidade (Fase 4) — L.geoJSON aceita
// `style` (usado pra LineString/Polygon) e `pointToLayer` (usado pra Point) ao mesmo
// tempo; como cada camada só contém um tipo de geometria, cada uma usa só o que precisa.
// Quantos px de TELA vale um metro no zoom atual. No L.CRS.Simple 1 px de mundo ocupa
// 2^zoom px de tela, e 1 px de mundo são `estado.leafletMetrosPorPixelMundo` metros.
function pxDeTelaPorMetro() {
    return Math.pow(2, estado.leafletMap.getZoom()) / estado.leafletMetrosPorPixelMundo;
}

// Tom de cada classe de via. Terra batida clara sobre o verde do terreno; a principal é a
// mais clara e opaca, que é como a hierarquia viária se lê num mapa de verdade.
const ESTILO_VIA_POR_CLASSE = {
    principal: { color: '#e8ddc8', opacity: 0.95 },
    anel: { color: '#dbd1bd', opacity: 0.85 },
    secundaria: { color: '#c6bda9', opacity: 0.75 },
};

// A rua é a única camada com estilo dinâmico: a espessura é uma largura REAL em metros,
// convertida a cada zoom. Antes era `weight: 1.5` fixo em px de tela, o que dava uma rua
// de 11,6 m no z11 e de 0,7 m no z15 — ela afinava conforme você se aproximava, e é daí
// que vinha a impressão de linha imaginária em cima do terreno em vez de rua.
// L.geoJSON aceita `style` como função e a reavalia a cada addData, que acontece em todo
// moveend (e zoom dispara moveend), então isto se reajusta sozinho ao navegar.
function estiloRua(feature) {
    const classe = (feature.properties || {}).classe_via || 'secundaria';
    // F04 (docs/16_PLANO_PAINEL_E_IA.md): sem `|| 5` no fim — se a classe não existir
    // NEM em leafletViaLarguraM.secundaria, é a config vinda do servidor que está
    // incompleta (a chave já é validada em carregarMundoLeaflet).
    const larguraM = estado.leafletViaLarguraM[classe] || estado.leafletViaLarguraM.secundaria;
    return {
        ...(ESTILO_VIA_POR_CLASSE[classe] || ESTILO_VIA_POR_CLASSE.secundaria),
        // O piso existe porque no zoom em que a camada acende a cidade inteira ainda tem
        // ~310 px e a via de verdade daria 2 px de largura.
        weight: Math.max(estado.leafletViaLarguraMinPx, larguraM * pxDeTelaPorMetro()),
        // Junta e ponta arredondadas fecham o cruzamento em vez de deixar o entalhe que
        // denuncia que aquilo são segmentos soltos.
        lineCap: 'round',
        lineJoin: 'round',
    };
}

// E3 do 08_ESPEC_TECIDO_URBANO.md: `edificio` virou Polygon (footprint dentro do lote), não
// mais um Point desenhado por `criarMarcadorDetalheCidade` — passa a usar `style` como
// rua/quarteirao/lote. Preenchimento sólido (é massa construída), contorno bem discreto
// pra não competir com o traço do lote por baixo.
function estiloEdificio(feature) {
    const categoria = (feature.properties || {}).categoria;
    const cor = CATEGORIA_EDIFICIO_COR[categoria] || CATEGORIA_EDIFICIO_COR.generic;
    return {
        color: '#2b2b2b', weight: 0.5, opacity: 0.4,
        fillColor: cor, fillOpacity: categoria === 'residencia' ? 0.55 : 0.9,
    };
}

// T05 (docs/12_PLANO_CIDADE_VIVA.md): lote livre e lote ocupado precisam se distinguir,
// senão a cidade parece igual à de antes (D2/T03 preenche só uma fração dela). O valor
// inicial vem de `feature.properties.estado`, gravado na geometria por T03; depois da
// importação o BANCO é a verdade (armadilha 2) — `mesclarLotesAlteradosLeaflet` reescreve
// essa mesma propriedade em cima do GeoJSON já carregado antes do estilo ser aplicado,
// então uma casa construída/arruinada durante o jogo aparece sem regenerar nada.
function estiloLote(feature) {
    const livre = (feature.properties || {}).estado !== 'ocupado';
    return livre
        ? { color: '#8a7355', weight: 1, opacity: 0.5, dashArray: '3,3', fillColor: '#8a7355', fillOpacity: 0.08 }
        : { color: '#6a5acd', weight: 0.5, opacity: 0.35, fillOpacity: 0.06 };
}

export const ESTILO_CAMADA_CIDADE = {
    muralha: { color: '#d4a017', weight: 3, opacity: 0.9 },
    rua: estiloRua,
    quarteirao: { color: '#888', weight: 1, opacity: 0.4, fillOpacity: 0.04 },
    praca: { color: '#2ecc71', weight: 1, opacity: 0.6, fillOpacity: 0.25 },
    // Q01 (docs/12_PLANO_CIDADE_VIVA.md): o miolo da quadra que não é lote — horta, poço,
    // quintal comum. Sem contorno próprio (o do quarteirão já marca o limite).
    patio: { color: '#2ecc71', weight: 0, opacity: 0, fillOpacity: 0.18 },
    lote: estiloLote,
    edificio: estiloEdificio,
};
