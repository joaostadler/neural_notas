"""
models.py — Modelos SQLAlchemy para NeuralNotes Web.

Todas as tabelas e colunas em português-BR para facilitar
o entendimento do código.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    """Modelo de usuário com autenticação."""
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    usuario = db.Column(db.String(80), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    topicos = db.relationship('Topico', backref='usuario', lazy=True, cascade='all, delete-orphan')
    colunas_kanban = db.relationship('ColunaKanban', backref='usuario', lazy=True, cascade='all, delete-orphan')
    tarefas_faceis = db.relationship('TarefaFacil', backref='usuario', lazy=True, cascade='all, delete-orphan')
    icones_customizados = db.relationship('IconeCustomizado', backref='usuario', lazy=True, cascade='all, delete-orphan')

    def definir_senha(self, senha: str) -> None:
        """Define e faz hash da senha."""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha: str) -> bool:
        """Verifica se a senha fornecida está correta."""
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f'<Usuario {self.usuario}>'


class Topico(db.Model):
    """Modelo de tópicos hierárquicos."""
    __tablename__ = 'topicos'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    id_pai = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'))
    nome = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # nota, caderno, diagrama, jupyter, pdf, planilha, imagem, pasta
    icone = db.Column(db.String(10), default='📄')
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    subtopicos = db.relationship('Topico', backref=db.backref('pai', remote_side=[id]), cascade='all, delete-orphan')
    notas = db.relationship('Nota', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    cadernos = db.relationship('Caderno', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    diagramas = db.relationship('Diagrama', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    celulas_jupyter = db.relationship('CelulaJupyter', backref='topico', lazy=True, cascade='all, delete-orphan')
    pdfs = db.relationship('PDF', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    planilhas = db.relationship('Planilha', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    imagens = db.relationship('Imagem', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    codigos = db.relationship('Codigo', backref='topico', lazy=True, cascade='all, delete-orphan', uselist=False)
    cartoes_kanban = db.relationship('CartaoKanban', backref='topico_pai', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_topicos_usuario_pai', 'id_usuario', 'id_pai'),
    )

    def __repr__(self):
        return f'<Topico {self.nome}>'


class Nota(db.Model):
    """Modelo de notas de texto."""
    __tablename__ = 'notas'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    conteudo = db.Column(db.Text, default='')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    etiquetas = db.relationship('Etiqueta', backref='nota', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Nota {self.titulo}>'


class Etiqueta(db.Model):
    """Modelo de tags/etiquetas para notas."""
    __tablename__ = 'etiquetas'

    id = db.Column(db.Integer, primary_key=True)
    id_nota = db.Column(db.Integer, db.ForeignKey('notas.id', ondelete='CASCADE'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Etiqueta {self.nome}>'


class Caderno(db.Model):
    """Modelo de cadernos pautados."""
    __tablename__ = 'cadernos'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    conteudo = db.Column(db.Text, default='')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Caderno {self.titulo}>'


class ColunaKanban(db.Model):
    """Modelo de colunas do quadro kanban."""
    __tablename__ = 'colunas_kanban'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    nome = db.Column(db.String(255), nullable=False)
    cor = db.Column(db.String(7), default='#4a9eff')
    ordem = db.Column(db.Integer, default=0)

    # Relacionamentos
    cartoes = db.relationship('CartaoKanban', backref='coluna', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_colunas_kanban_usuario_ordem', 'id_usuario', 'ordem'),
    )

    def __repr__(self):
        return f'<ColunaKanban {self.nome}>'


class CartaoKanban(db.Model):
    """Modelo de cartões do quadro kanban."""
    __tablename__ = 'cartoes_kanban'

    id = db.Column(db.Integer, primary_key=True)
    id_coluna = db.Column(db.Integer, db.ForeignKey('colunas_kanban.id', ondelete='CASCADE'), nullable=False)
    id_topico_pai = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='SET NULL'))
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, default='')
    etiquetas = db.Column(db.String(255), default='')
    prioridade = db.Column(db.String(50), default='baixa')  # baixa, media, alta
    ordem = db.Column(db.Integer, default=0)
    visivel_sidebar = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes_conclusao = db.Column(db.Text, default='')

    # Relacionamentos
    historico_etapas = db.relationship('HistoricoEtapas', backref='cartao', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_cartoes_kanban_coluna_ordem', 'id_coluna', 'ordem'),
    )

    def __repr__(self):
        return f'<CartaoKanban {self.titulo}>'


class HistoricoEtapas(db.Model):
    """Modelo de histórico de movimentação de cartões."""
    __tablename__ = 'historico_etapas'

    id = db.Column(db.Integer, primary_key=True)
    id_cartao = db.Column(db.Integer, db.ForeignKey('cartoes_kanban.id', ondelete='CASCADE'), nullable=False)
    id_coluna = db.Column(db.Integer, db.ForeignKey('colunas_kanban.id', ondelete='CASCADE'), nullable=False)
    nome_coluna = db.Column(db.String(255), nullable=False)
    data_entrada = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_historico_etapas_cartao_coluna', 'id_cartao', 'id_coluna'),
    )

    def __repr__(self):
        return f'<HistoricoEtapas cartao={self.id_cartao} coluna={self.id_coluna}>'


class Diagrama(db.Model):
    """Modelo de diagramas."""
    __tablename__ = 'diagramas'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    dados_json = db.Column(db.Text, default='{"formas":[],"conexoes":[]}')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Diagrama {self.titulo}>'


class CelulaJupyter(db.Model):
    """Modelo de células do notebook Jupyter."""
    __tablename__ = 'celulas_jupyter'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False)
    tipo = db.Column(db.String(50), default='codigo')  # codigo, markdown
    conteudo = db.Column(db.Text, default='')
    saida = db.Column(db.Text, default='')
    numero_execucao = db.Column(db.Integer, default=0)
    ordem = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<CelulaJupyter tipo={self.tipo}>'


class IconeCustomizado(db.Model):
    """Ícones customizados por tipo de tópico, por usuário."""
    __tablename__ = 'icones_customizados'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    caminho = db.Column(db.String(500), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('id_usuario', 'tipo', name='uq_icone_usuario_tipo'),
    )

    def __repr__(self):
        return f'<IconeCustomizado {self.tipo}>'


class PDF(db.Model):
    """Modelo de PDFs."""
    __tablename__ = 'pdfs'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    caminho = db.Column(db.String(500), default='')
    capa = db.Column(db.String(500), default='')
    conteudo_pdf = db.Column(db.LargeBinary, nullable=True)
    conteudo_capa = db.Column(db.LargeBinary, nullable=True)
    percentual_lido = db.Column(db.Integer, default=0)
    anotacoes = db.Column(db.Text, default='')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PDF {self.titulo}>'


class Planilha(db.Model):
    """Modelo de planilhas."""
    __tablename__ = 'planilhas'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    dados_json = db.Column(db.Text, default='{}')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Planilha {self.titulo}>'


class Imagem(db.Model):
    """Modelo de imagens."""
    __tablename__ = 'imagens'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    caminho = db.Column(db.String(500), default='')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Imagem {self.titulo}>'


class Codigo(db.Model):
    """Modelo para arquivos de código (Python, SQL)."""
    __tablename__ = 'codigos'

    id = db.Column(db.Integer, primary_key=True)
    id_topico = db.Column(db.Integer, db.ForeignKey('topicos.id', ondelete='CASCADE'), nullable=False, unique=True)
    titulo = db.Column(db.String(255), default='')
    conteudo = db.Column(db.Text, default='')
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Codigo {self.titulo}>'


class TarefaFacil(db.Model):
    """Modelo de tarefas simples."""
    __tablename__ = 'tarefas_faceis'

    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    data_tarefa = db.Column(db.Date, nullable=False)
    solicitante = db.Column(db.String(255), default='')
    descricao = db.Column(db.Text, nullable=False)
    concluida = db.Column(db.Boolean, default=False)
    concluida_em = db.Column(db.DateTime, nullable=True)
    observacao_conclusao = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_tarefas_faceis_usuario_data', 'id_usuario', 'concluida', 'data_tarefa'),
    )

    def __repr__(self):
        return f'<TarefaFacil {self.descricao[:50]}>'
