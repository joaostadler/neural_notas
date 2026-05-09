-- =============================================================
-- migrate.sql — NeuralNotas: criação e migração de tabelas
-- Banco: PostgreSQL (Supabase / Railway / Render / Neon)
-- Seguro para executar múltiplas vezes (idempotente)
-- =============================================================

-- ─── 1. CRIAR TABELAS (somente se não existirem) ──────────────

CREATE TABLE IF NOT EXISTS usuarios (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(255) NOT NULL,
    usuario     VARCHAR(80)  NOT NULL UNIQUE,
    senha_hash  VARCHAR(255) NOT NULL,
    criado_em   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usuarios_usuario ON usuarios (usuario);

CREATE TABLE IF NOT EXISTS topicos (
    id           SERIAL PRIMARY KEY,
    id_usuario   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    id_pai       INTEGER REFERENCES topicos(id) ON DELETE CASCADE,
    nome         VARCHAR(255) NOT NULL,
    tipo         VARCHAR(50)  NOT NULL,
    icone        VARCHAR(10)  DEFAULT '📄',
    ordem        INTEGER      DEFAULT 0,
    criado_em    TIMESTAMP    DEFAULT NOW(),
    atualizado_em TIMESTAMP   DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_topicos_usuario_pai ON topicos (id_usuario, id_pai);

CREATE TABLE IF NOT EXISTS notas (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    conteudo     TEXT         DEFAULT '',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etiquetas (
    id       SERIAL PRIMARY KEY,
    id_nota  INTEGER NOT NULL REFERENCES notas(id) ON DELETE CASCADE,
    nome     VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS cadernos (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    conteudo     TEXT         DEFAULT '',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS diagramas (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    dados_json   TEXT         DEFAULT '{"formas":[],"conexoes":[]}',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS celulas_jupyter (
    id               SERIAL PRIMARY KEY,
    id_topico        INTEGER NOT NULL REFERENCES topicos(id) ON DELETE CASCADE,
    tipo             VARCHAR(50) DEFAULT 'codigo',
    conteudo         TEXT        DEFAULT '',
    saida            TEXT        DEFAULT '',
    numero_execucao  INTEGER     DEFAULT 0,
    ordem            INTEGER     DEFAULT 0
);

CREATE TABLE IF NOT EXISTS planilhas (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    dados_json   TEXT         DEFAULT '{}',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS imagens (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    caminho      VARCHAR(500) DEFAULT '',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS codigos (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    conteudo     TEXT         DEFAULT '',
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pdfs (
    id             SERIAL PRIMARY KEY,
    id_topico      INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo         VARCHAR(255) DEFAULT '',
    caminho        VARCHAR(500) DEFAULT '',
    capa           VARCHAR(500) DEFAULT '',
    conteudo_pdf   BYTEA,
    conteudo_capa  BYTEA,
    percentual_lido INTEGER     DEFAULT 0,
    anotacoes      TEXT         DEFAULT '',
    atualizado_em  TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS apresentacoes (
    id           SERIAL PRIMARY KEY,
    id_topico    INTEGER NOT NULL UNIQUE REFERENCES topicos(id) ON DELETE CASCADE,
    titulo       VARCHAR(255) DEFAULT '',
    conteudo     BYTEA,
    slides_json  TEXT         DEFAULT '{}',
    slide_atual  INTEGER      DEFAULT 1,
    atualizado_em TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comentarios_slide (
    id              SERIAL PRIMARY KEY,
    id_apresentacao INTEGER NOT NULL REFERENCES apresentacoes(id) ON DELETE CASCADE,
    slide_num       INTEGER NOT NULL,
    texto           TEXT    NOT NULL,
    pos_x           FLOAT   DEFAULT 50.0,
    pos_y           FLOAT   DEFAULT 50.0,
    cor             VARCHAR(7) DEFAULT '#fbbf24',
    criado_em       TIMESTAMP  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comentarios_slide ON comentarios_slide (id_apresentacao, slide_num);

CREATE TABLE IF NOT EXISTS icones_customizados (
    id          SERIAL PRIMARY KEY,
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo        VARCHAR(50)  NOT NULL,
    caminho     VARCHAR(500) NOT NULL,
    CONSTRAINT uq_icone_usuario_tipo UNIQUE (id_usuario, tipo)
);

CREATE TABLE IF NOT EXISTS colunas_kanban (
    id          SERIAL PRIMARY KEY,
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome        VARCHAR(255) NOT NULL,
    cor         VARCHAR(7)   DEFAULT '#4a9eff',
    ordem       INTEGER      DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_colunas_kanban_usuario_ordem ON colunas_kanban (id_usuario, ordem);

CREATE TABLE IF NOT EXISTS cartoes_kanban (
    id                    SERIAL PRIMARY KEY,
    id_coluna             INTEGER NOT NULL REFERENCES colunas_kanban(id) ON DELETE CASCADE,
    id_topico_pai         INTEGER REFERENCES topicos(id) ON DELETE SET NULL,
    titulo                VARCHAR(255) NOT NULL,
    descricao             TEXT         DEFAULT '',
    etiquetas             VARCHAR(255) DEFAULT '',
    prioridade            VARCHAR(50)  DEFAULT 'baixa',
    ordem                 INTEGER      DEFAULT 0,
    visivel_sidebar       BOOLEAN      DEFAULT TRUE,
    criado_em             TIMESTAMP    DEFAULT NOW(),
    observacoes_conclusao TEXT         DEFAULT '',
    data_conclusao        DATE
);
CREATE INDEX IF NOT EXISTS idx_cartoes_kanban_coluna_ordem ON cartoes_kanban (id_coluna, ordem);

CREATE TABLE IF NOT EXISTS historico_etapas (
    id           SERIAL PRIMARY KEY,
    id_cartao    INTEGER NOT NULL REFERENCES cartoes_kanban(id) ON DELETE CASCADE,
    id_coluna    INTEGER NOT NULL REFERENCES colunas_kanban(id) ON DELETE CASCADE,
    nome_coluna  VARCHAR(255) NOT NULL,
    data_entrada TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_historico_etapas_cartao_coluna ON historico_etapas (id_cartao, id_coluna);

CREATE TABLE IF NOT EXISTS execucoes_cartao (
    id         SERIAL PRIMARY KEY,
    id_cartao  INTEGER NOT NULL REFERENCES cartoes_kanban(id) ON DELETE CASCADE,
    texto      TEXT    NOT NULL,
    concluida  BOOLEAN DEFAULT FALSE,
    criado_em  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_execucoes_cartao ON execucoes_cartao (id_cartao, criado_em);

CREATE TABLE IF NOT EXISTS tarefas_faceis (
    id                   SERIAL PRIMARY KEY,
    id_usuario           INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data_tarefa          DATE    NOT NULL,
    solicitante          VARCHAR(255) DEFAULT '',
    descricao            TEXT    NOT NULL,
    concluida            BOOLEAN DEFAULT FALSE,
    concluida_em         TIMESTAMP,
    observacao_conclusao TEXT,
    criado_em            TIMESTAMP DEFAULT NOW(),
    atualizado_em        TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tarefas_faceis_usuario_data
    ON tarefas_faceis (id_usuario, concluida, data_tarefa);

CREATE TABLE IF NOT EXISTS compartilhamentos_kanban (
    id               SERIAL PRIMARY KEY,
    id_usuario       INTEGER NOT NULL UNIQUE REFERENCES usuarios(id) ON DELETE CASCADE,
    token            VARCHAR(64) NOT NULL UNIQUE,
    ativo            BOOLEAN DEFAULT FALSE,
    colunas_visiveis TEXT    DEFAULT '',
    criado_em        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS acessos_kanban (
    id            SERIAL PRIMARY KEY,
    id_dono       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    id_convidado  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    papel         VARCHAR(20) DEFAULT 'usuario',
    criado_em     TIMESTAMP   DEFAULT NOW(),
    CONSTRAINT uq_acesso_kanban UNIQUE (id_dono, id_convidado)
);

CREATE TABLE IF NOT EXISTS roadmaps (
    id           SERIAL PRIMARY KEY,
    id_usuario   INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome         VARCHAR(255) NOT NULL,
    padrao       BOOLEAN DEFAULT FALSE NOT NULL,
    criado_em    TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linhas_roadmap (
    id          SERIAL PRIMARY KEY,
    id_roadmap  INTEGER NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    nome        VARCHAR(255) NOT NULL,
    cor         VARCHAR(7)   DEFAULT '#1e293b',
    ordem       INTEGER      DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subgrupos_roadmap (
    id         SERIAL PRIMARY KEY,
    id_linha   INTEGER NOT NULL REFERENCES linhas_roadmap(id) ON DELETE CASCADE,
    nome       VARCHAR(255) NOT NULL,
    ordem      INTEGER      DEFAULT 0
);

CREATE TABLE IF NOT EXISTS colunas_roadmap (
    id          SERIAL PRIMARY KEY,
    id_roadmap  INTEGER NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    nome        VARCHAR(100) NOT NULL,
    data_inicio DATE         NOT NULL,
    data_fim    DATE         NOT NULL,
    ordem       INTEGER      DEFAULT 0
);

CREATE TABLE IF NOT EXISTS projetos_roadmap (
    id          SERIAL PRIMARY KEY,
    id_roadmap  INTEGER NOT NULL REFERENCES roadmaps(id)     ON DELETE CASCADE,
    id_linha    INTEGER NOT NULL REFERENCES linhas_roadmap(id) ON DELETE CASCADE,
    id_subgrupo INTEGER REFERENCES subgrupos_roadmap(id)     ON DELETE SET NULL,
    nome        VARCHAR(255) NOT NULL,
    data_inicio DATE         NOT NULL,
    data_fim    DATE         NOT NULL,
    cor         VARCHAR(7)   DEFAULT '#16a34a',
    status      VARCHAR(50)  DEFAULT 'ativo',
    criado_em   TIMESTAMP    DEFAULT NOW()
);

-- ─── 2. ADICIONAR COLUNAS EM TABELAS JÁ EXISTENTES ────────────
-- Seguro: ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)
-- Execute este bloco se o banco já existia sem essas colunas.

ALTER TABLE tarefas_faceis
    ADD COLUMN IF NOT EXISTS concluida_em         TIMESTAMP,
    ADD COLUMN IF NOT EXISTS observacao_conclusao TEXT;

ALTER TABLE pdfs
    ADD COLUMN IF NOT EXISTS percentual_lido INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS anotacoes       TEXT    DEFAULT '',
    ADD COLUMN IF NOT EXISTS capa            VARCHAR(500) DEFAULT '',
    ADD COLUMN IF NOT EXISTS conteudo_pdf    BYTEA,
    ADD COLUMN IF NOT EXISTS conteudo_capa   BYTEA;

ALTER TABLE cartoes_kanban
    ADD COLUMN IF NOT EXISTS observacoes_conclusao TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS data_conclusao        DATE;

ALTER TABLE compartilhamentos_kanban
    ADD COLUMN IF NOT EXISTS colunas_visiveis TEXT DEFAULT '';

ALTER TABLE acessos_kanban
    ADD COLUMN IF NOT EXISTS papel VARCHAR(20) DEFAULT 'usuario';

ALTER TABLE projetos_roadmap
    ADD COLUMN IF NOT EXISTS id_subgrupo INTEGER REFERENCES subgrupos_roadmap(id) ON DELETE SET NULL;

ALTER TABLE roadmaps
    ADD COLUMN IF NOT EXISTS padrao BOOLEAN DEFAULT FALSE NOT NULL;
