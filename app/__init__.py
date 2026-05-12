"""
app/__init__.py — Factory da aplicação Flask.
"""

import os
from flask import Flask
from flask_login import LoginManager
from models import db, Usuario
from config import DevelopmentConfig, ProductionConfig


def criar_app(config=None):
    """Factory para criar a aplicação Flask."""
    app = Flask(__name__)

    # Configuração
    if config is None:
        config = os.environ.get('FLASK_ENV', 'development')
    
    if config == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Criar diretórios necessários
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('instance', exist_ok=True)

    # Inicializar extensões
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'

    @login_manager.user_loader
    def carregar_usuario(user_id):
        return Usuario.query.get(int(user_id))

    # Criar tabelas e migrar
    with app.app_context():
        db.create_all()

        dialect = db.engine.dialect.name  # 'sqlite' ou 'postgresql'

        if dialect == 'postgresql':
            # PostgreSQL: IF NOT EXISTS é suportado — roda tudo em uma transação
            pg_stmts = """
                ALTER TABLE usuarios
                    ADD COLUMN IF NOT EXISTS papel VARCHAR(10) NOT NULL DEFAULT 'usuario';

                ALTER TABLE tarefas_faceis
                    ADD COLUMN IF NOT EXISTS concluida_em         TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS observacao_conclusao TEXT;

                ALTER TABLE pdfs
                    ADD COLUMN IF NOT EXISTS percentual_lido INTEGER     DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS anotacoes       TEXT        DEFAULT '',
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
                    ADD COLUMN IF NOT EXISTS id_subgrupo INTEGER
                        REFERENCES subgrupos_roadmap(id) ON DELETE SET NULL;

                ALTER TABLE projetos_roadmap
                    ADD COLUMN IF NOT EXISTS descricao TEXT DEFAULT '';

                ALTER TABLE roadmaps
                    ADD COLUMN IF NOT EXISTS padrao BOOLEAN DEFAULT FALSE NOT NULL;

                ALTER TABLE projetos_roadmap
                    ADD COLUMN IF NOT EXISTS ordem INTEGER DEFAULT 0;

                ALTER TABLE colunas_kanban
                    ADD COLUMN IF NOT EXISTS id_quadro INTEGER
                        REFERENCES quadros_kanban(id) ON DELETE CASCADE;
            """
            for stmt in pg_stmts.strip().split(';'):
                stmt = stmt.strip()
                if stmt:
                    try:
                        db.session.execute(db.text(stmt))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
        else:
            # SQLite: não suporta IF NOT EXISTS em ALTER TABLE — ignora erro de duplicata
            for stmt in [
                "ALTER TABLE usuarios ADD COLUMN papel VARCHAR(10) NOT NULL DEFAULT 'usuario'",
                'ALTER TABLE tarefas_faceis ADD COLUMN concluida_em DATETIME',
                'ALTER TABLE tarefas_faceis ADD COLUMN observacao_conclusao TEXT',
                'ALTER TABLE pdfs ADD COLUMN percentual_lido INTEGER DEFAULT 0',
                "ALTER TABLE pdfs ADD COLUMN anotacoes TEXT DEFAULT ''",
                "ALTER TABLE pdfs ADD COLUMN capa VARCHAR(500) DEFAULT ''",
                "ALTER TABLE cartoes_kanban ADD COLUMN observacoes_conclusao TEXT DEFAULT ''",
                'ALTER TABLE pdfs ADD COLUMN conteudo_pdf BLOB',
                'ALTER TABLE pdfs ADD COLUMN conteudo_capa BLOB',
                "ALTER TABLE compartilhamentos_kanban ADD COLUMN colunas_visiveis TEXT DEFAULT ''",
                "ALTER TABLE acessos_kanban ADD COLUMN papel VARCHAR(20) DEFAULT 'usuario'",
                'ALTER TABLE projetos_roadmap ADD COLUMN id_subgrupo INTEGER REFERENCES subgrupos_roadmap(id)',
                'ALTER TABLE cartoes_kanban ADD COLUMN data_conclusao DATE',
                'ALTER TABLE roadmaps ADD COLUMN padrao BOOLEAN DEFAULT 0',
                "ALTER TABLE projetos_roadmap ADD COLUMN descricao TEXT DEFAULT ''",
                'ALTER TABLE projetos_roadmap ADD COLUMN ordem INTEGER DEFAULT 0',
                'ALTER TABLE colunas_kanban ADD COLUMN id_quadro INTEGER REFERENCES quadros_kanban(id)',
            ]:
                try:
                    db.session.execute(db.text(stmt))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        # Garantir que o admin padrão sempre seja admin
        admin_padrao = app.config.get('ADMIN_PADRAO')
        if admin_padrao:
            u = Usuario.query.filter_by(usuario=admin_padrao).first()
            if u and u.papel != 'admin':
                u.papel = 'admin'
                db.session.commit()

    # Context processor: expõe admin_visualizando e modulos_permitidos a todos os templates
    @app.context_processor
    def _inject_admin_context():
        from flask_login import current_user
        from flask import session as _session
        ctx = {'admin_visualizando': None, 'modulos_permitidos': None}

        if not current_user.is_authenticated:
            return ctx

        if current_user.papel == 'admin':
            vid = _session.get('admin_visualizando_id')
            if vid and vid != current_user.id:
                u = Usuario.query.get(vid)
                if u:
                    ctx['admin_visualizando'] = u
        else:
            from app.utils import get_permissoes, MODULOS
            p = get_permissoes(current_user.id)
            ctx['modulos_permitidos'] = {m: getattr(p, m) for m in MODULOS}

        return ctx

    # Registrar blueprints
    from app.routes.auth import bp_auth
    from app.routes.main import bp_main
    from app.routes.kanban import bp_kanban
    from app.routes.tarefas import bp_tarefas
    from app.routes.usuario import bp_usuario
    from app.routes.roadmap import bp_roadmap
    from app.routes.reunioes import bp_reunioes

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_kanban)
    app.register_blueprint(bp_tarefas)
    app.register_blueprint(bp_usuario)
    app.register_blueprint(bp_roadmap)
    app.register_blueprint(bp_reunioes)

    return app
