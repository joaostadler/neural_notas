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
        for stmt in [
            'ALTER TABLE tarefas_faceis ADD COLUMN concluida_em DATETIME',
            'ALTER TABLE tarefas_faceis ADD COLUMN observacao_conclusao TEXT',
            'ALTER TABLE pdfs ADD COLUMN percentual_lido INTEGER DEFAULT 0',
            'ALTER TABLE pdfs ADD COLUMN anotacoes TEXT DEFAULT \'\'',
            "ALTER TABLE pdfs ADD COLUMN capa VARCHAR(500) DEFAULT ''",
            "ALTER TABLE cartoes_kanban ADD COLUMN observacoes_conclusao TEXT DEFAULT ''",
            'ALTER TABLE pdfs ADD COLUMN conteudo_pdf BLOB',
            'ALTER TABLE pdfs ADD COLUMN conteudo_capa BLOB',
            "ALTER TABLE compartilhamentos_kanban ADD COLUMN colunas_visiveis TEXT DEFAULT ''",
            "ALTER TABLE acessos_kanban ADD COLUMN papel VARCHAR(20) DEFAULT 'usuario'",
            'ALTER TABLE projetos_roadmap ADD COLUMN id_subgrupo INTEGER REFERENCES subgrupos_roadmap(id)',
            'ALTER TABLE cartoes_kanban ADD COLUMN data_conclusao DATE',
        ]:
            try:
                db.session.execute(db.text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()

    # Registrar blueprints
    from app.routes.auth import bp_auth
    from app.routes.main import bp_main
    from app.routes.kanban import bp_kanban
    from app.routes.tarefas import bp_tarefas
    from app.routes.usuario import bp_usuario
    from app.routes.roadmap import bp_roadmap

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_kanban)
    app.register_blueprint(bp_tarefas)
    app.register_blueprint(bp_usuario)
    app.register_blueprint(bp_roadmap)

    return app
