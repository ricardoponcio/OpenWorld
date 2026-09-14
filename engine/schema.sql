-- Tabelas Globais (Geradas pelo Cartógrafo e Importadas no Bootstrap)
CREATE TABLE IF NOT EXISTS continentes (
    uuid TEXT PRIMARY KEY,
    nome TEXT,
    area_real_km2 REAL
);

CREATE TABLE IF NOT EXISTS cidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    continente_uuid TEXT,
    nome TEXT,
    tamanho TEXT,
    tipo TEXT,
    x_global INTEGER,
    y_global INTEGER,
    FOREIGN KEY(continente_uuid) REFERENCES continentes(uuid)
);

-- Locais (Expandido para Mercado de Trabalho e Escopo da Cidade)
CREATE TABLE IF NOT EXISTS locais (
    id TEXT PRIMARY KEY,
    nome TEXT,
    tipo TEXT,
    cidade_id INTEGER,
    categoria TEXT, -- Ex: 'fazenda', 'quartel', 'taverna'
    descricao TEXT,
    coordenadas TEXT,
    status INTEGER DEFAULT 1,
    integridade INTEGER DEFAULT 100,
    capacidade INTEGER DEFAULT 5,
    salario_base INTEGER DEFAULT 100,
    tipo_local TEXT DEFAULT '',
    bairro TEXT DEFAULT '',
    dono_npc_id TEXT DEFAULT ''
);

-- Lotes urbanos (T01, docs/12_PLANO_CIDADE_VIVA.md): geometria vem do GeoJSON do
-- cartógrafo, ESTADO vive aqui — armadilha 2: cartographer/ nunca escreve estado de
-- simulação, engine/ nunca escreve GeoJSON. x/y (não JSON) porque O01 ordena lote
-- livre mais próximo por distância ao quadrado, sem sqrt, num ORDER BY simples.
CREATE TABLE IF NOT EXISTS lotes (
    id TEXT PRIMARY KEY,
    cidade_id INTEGER,
    quarteirao_id TEXT,
    bairro TEXT,
    banda INTEGER,
    classe_frente TEXT,
    area_m2 REAL,
    x REAL DEFAULT 0.0,
    y REAL DEFAULT 0.0,
    estado TEXT DEFAULT 'livre',    -- LoteEstado: livre | obra | ocupado
    -- T05: o valor de `estado` na hora da importação (T02) — congelado, nunca mais
    -- escrito depois. `estado != estado_inicial` é o delta que o mapa (que lê o
    -- GeoJSON, não o banco) precisa saber pra redesenhar sem regenerar geometria.
    estado_inicial TEXT DEFAULT 'livre',
    local_id TEXT DEFAULT '',
    dono_npc_id TEXT DEFAULT '',
    FOREIGN KEY(cidade_id) REFERENCES cidades(id)
);
CREATE INDEX IF NOT EXISTS idx_lotes_cidade_estado ON lotes(cidade_id, estado);

-- Profissões / Funções (Âncora de Dados)
CREATE TABLE IF NOT EXISTS profissoes (
    id TEXT PRIMARY KEY,
    nome TEXT,
    categoria_local_id TEXT -- Qual categoria de local aceita essa profissão
);

-- Tabela de NPCs
CREATE TABLE IF NOT EXISTS npcs (
    id TEXT PRIMARY KEY,
    nome TEXT,
    profissao TEXT, -- Nome customizado (IA)
    profissao_id TEXT, -- Link com a tabela profissoes
    cidade_id INTEGER,
    casa_id TEXT,
    local_trabalho_id TEXT,
    localizacao_atual_id TEXT,
    acao_atual TEXT,
    energia REAL,
    dinheiro_total_pc REAL, -- fracionário desde a Frente 4 (pago a cada tick de 1 min)
    social REAL,
    fome REAL,
    saude INTEGER DEFAULT 100,
    humor TEXT DEFAULT 'Neutro',
    genero TEXT DEFAULT 'M',
    estagio_vida TEXT DEFAULT 'adulto',
    raca TEXT DEFAULT '',
    personalidade TEXT DEFAULT '',
    background TEXT DEFAULT '',
    data_nascimento TEXT,
    estado_civil TEXT DEFAULT 'solteiro',
    conjuge_id TEXT,
    pai_id TEXT,
    mae_id TEXT,
    genealogia TEXT,
    relacionamentos TEXT,
    memoria_eventos TEXT,
    gravidez_ticks INTEGER DEFAULT 0,
    FOREIGN KEY(profissao_id) REFERENCES profissoes(id)
);

-- D04 (docs/16_PLANO_PAINEL_E_IA.md): filtros do painel paginado (P02) e da camada de
-- NPCs do mapa (M04). Sem índice, cada requisição varre a tabela inteira.
CREATE INDEX IF NOT EXISTS idx_npcs_cidade_saude ON npcs(cidade_id, saude);
CREATE INDEX IF NOT EXISTS idx_npcs_localizacao ON npcs(localizacao_atual_id);

-- Tabela de Relacionamentos (SOCIAL)
CREATE TABLE IF NOT EXISTS relacionamentos (
    npc_a_id TEXT,
    npc_b_id TEXT,
    afinidade INTEGER DEFAULT 0,
    vinculo TEXT DEFAULT 'Conhecido',
    PRIMARY KEY (npc_a_id, npc_b_id)
);

-- Tabela de Eventos
CREATE TABLE IF NOT EXISTS eventos (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    local_id TEXT,
    envolvidos TEXT,
    tipo_evento TEXT,
    modificador_afinidade INTEGER,
    resumo_estruturado TEXT
);

-- Tabela de Meta
CREATE TABLE IF NOT EXISTS mundo_meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

-- Tabela de Eventos Globais (A Vontade do Mundo)
CREATE TABLE IF NOT EXISTS eventos_globais (
    id TEXT PRIMARY KEY,
    titulo TEXT,
    descricao TEXT,
    tipo TEXT,
    afeta_local_id TEXT,
    modificadores TEXT, -- JSON com pesos para acoes
    ticks_restantes INTEGER,
    timestamp_criacao TEXT
);

-- Tabela de Mapeamento de Categorias de Trabalho (Para IA Storyteller)
CREATE TABLE IF NOT EXISTS mapeamento_categorias_trabalho (
    termo TEXT PRIMARY KEY,
    categoria_sistema TEXT
);

-- Tabela de Logs Individuais de NPCs (Para Auditoria/UI)
CREATE TABLE IF NOT EXISTS npc_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    npc_id TEXT,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    level TEXT,
    message TEXT,
    FOREIGN KEY(npc_id) REFERENCES npcs(id)
);

CREATE INDEX IF NOT EXISTS idx_npc_logs_npc_id ON npc_logs(npc_id);

-- Tabela de Conversas do Modo Mestre de IA (Frente 5)
CREATE TABLE IF NOT EXISTS mestre_conversas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    autor TEXT, -- 'jogador' ou 'mestre'
    mensagem TEXT,
    acoes_propostas TEXT, -- JSON com a lista de ações de mundo propostas pela IA (nullable)
    aplicada INTEGER DEFAULT 0 -- 1 quando o jogador confirmou e as ações foram aplicadas
);

-- F01 (docs/14_PLANO_AVANCO_E_CALIBRAGEM.md): fila de ações de mundo do Modo Mestre.
-- O Mestre roda no processo do Flask e não tem o EstadoDoMundo vivo da simulação
-- (11_ARQUITETURA.md, "regra de processo": só run_simulation.py instancia a engine) —
-- em vez de escrever direto no banco, enfileira aqui; run_simulation.py drena a
-- cada volta do laço (mesmo pausado) e aplica com o mundo vivo, exatamente o
-- padrão que AVANCAR_MINUTOS já usa pra "preparar cena com a simulação parada".
CREATE TABLE IF NOT EXISTS mestre_acoes_pendentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL, -- JSON: o mesmo dict que AcaoProposta.de_payload espera
    criada_em TEXT DEFAULT (datetime('now', 'localtime')),
    aplicada_em TEXT -- NULL enquanto pendente; datetime de quando run_simulation.py aplicou
);
