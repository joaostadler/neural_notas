"""
app/routes/auth.py — Rotas de autenticação (login, registro, logout).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from models import db, Usuario

bp_auth = Blueprint('auth', __name__, url_prefix='/auth')


@bp_auth.route('/register', methods=['GET', 'POST'])
def register():
    """Página e lógica de registro de novo usuário."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        usuario = request.form.get('usuario', '').strip().lower()
        senha = request.form.get('senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        # Validações
        if not all([nome, usuario, senha]):
            flash('Todos os campos são obrigatórios.', 'erro')
            return redirect(url_for('auth.register'))

        if len(usuario) < 3:
            flash('Usuário deve ter pelo menos 3 caracteres.', 'erro')
            return redirect(url_for('auth.register'))

        if len(senha) < 4:
            flash('Senha deve ter pelo menos 4 caracteres.', 'erro')
            return redirect(url_for('auth.register'))

        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'erro')
            return redirect(url_for('auth.register'))

        # Verificar se usuário já existe
        if Usuario.query.filter_by(usuario=usuario).first():
            flash('Este usuário já existe.', 'erro')
            return redirect(url_for('auth.register'))

        # Criar novo usuário
        novo_usuario = Usuario(nome=nome, usuario=usuario)
        novo_usuario.definir_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Cadastro realizado com sucesso! Faça login para continuar.', 'sucesso')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@bp_auth.route('/login', methods=['GET', 'POST'])
def login():
    """Página e lógica de login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip().lower()
        senha = request.form.get('senha', '')

        usuario_obj = Usuario.query.filter_by(usuario=usuario).first()

        if usuario_obj and usuario_obj.verificar_senha(senha):
            login_user(usuario_obj, remember=request.form.get('lembrar'))
            return redirect(url_for('main.dashboard'))
        else:
            flash('Usuário ou senha inválidos.', 'erro')

    return render_template('auth/login.html')


@bp_auth.route('/logout')
def logout():
    """Logout do usuário."""
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))
