"""
config.py — Configurações da aplicação Flask.
"""

import os
from datetime import timedelta


class Config:
    """Configurações base da aplicação."""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Upload
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'zip'}


class DevelopmentConfig(Config):
    """Configurações para desenvolvimento."""
    import os
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        basedir = os.path.abspath(os.path.dirname(__file__))
        instance_path = os.path.join(basedir, 'instance')
        os.makedirs(instance_path, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_path, 'neural_notas.db').replace('\\', '/')


class ProductionConfig(Config):
    """Configurações para produção."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Configurações para testes."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Cores e constantes do tema
CORES = {
    "bg":       "#f8fafc",
    "painel":   "#ffffff",
    "cartao":   "#f1f5f9",
    "borda":    "#dbe4ef",
    "destaque": "#2563eb",
    "verde":    "#16a34a",
    "rosa":     "#ef4444",
    "ambar":    "#d97706",
    "roxo":     "#7c3aed",
    "texto":    "#0f172a",
    "apagado":  "#64748b",
}

PRIORIDADE_COR = {
    "baixa":  "#22c55e",
    "media":  "#f59e0b",
    "alta":   "#ef4444",
}

TIPO_ICONE = {
    "pasta":    "🗂",
    "nota":     "📒",
    "caderno":  "📔",
    "pdf":      "📑",
    "planilha": "📊",
    "diagrama": "🔷",
    "jupyter":  "⚗️",
    "tarefa":   "🎯",
    "imagem":   "🖼",
    "python":   "PY",
    "sql":      "SQL",
}
