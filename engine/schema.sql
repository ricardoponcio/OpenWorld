-- Locais (Expandido para Mercado de Trabalho)
CREATE TABLE IF NOT EXISTS locais (
    id TEXT PRIMARY KEY,
    nome TEXT,
    tipo TEXT,
    categoria TEXT, -- Ex: 'fazenda', 'quartel', 'taverna'
    descricao TEXT,
    coordenadas TEXT,
    status INTEGER DEFAULT 1,
    integridade INTEGER DEFAULT 100,
    capacidade INTEGER DEFAULT 5,
    salario_base INTEGER DEFAULT 100
);

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
    casa_id TEXT,
    local_trabalho_id TEXT,
    localizacao_atual_id TEXT,
    acao_atual TEXT,
    energia REAL,
    dinheiro_total_pc INTEGER,
    social REAL,
    fome REAL,
    saude INTEGER DEFAULT 100,
    humor TEXT DEFAULT 'Neutro',
    genero TEXT DEFAULT 'M',
    estagio_vida TEXT DEFAULT 'adulto',
    data_nascimento TEXT,
    pai_id TEXT,
    mae_id TEXT,
    genealogia TEXT,
    relacionamentos TEXT,
    memoria_eventos TEXT,
    gravidez_ticks INTEGER DEFAULT 0,
    FOREIGN KEY(profissao_id) REFERENCES profissoes(id)
);

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
