"""app/routes/usuario.py — Perfil do usuário e configuração de compartilhamento do kanban."""

import secrets

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for, flash
from flask_login import current_user, login_required

from app.utils import get_permissoes, requer_admin, MODULOS
from models import AcessoKanban, CompartilhamentoKanban, ColunaKanban, PermissaoUsuario, Usuario, db

bp_usuario = Blueprint('usuario', __name__, url_prefix='/usuario')


def _obter_ou_criar_compartilhamento():
    comp = current_user.compartilhamento_kanban
    if not comp:
        comp = CompartilhamentoKanban(id_usuario=current_user.id)
        db.session.add(comp)
        db.session.commit()
    return comp


@bp_usuario.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        senha_atual = request.form.get('senha_atual', '')
        nova_senha = request.form.get('nova_senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        if nome and nome != current_user.nome:
            current_user.nome = nome
            db.session.commit()
            flash('Nome atualizado com sucesso.', 'sucesso')

        if senha_atual:
            if not current_user.verificar_senha(senha_atual):
                flash('Senha atual incorreta.', 'erro')
            elif len(nova_senha) < 4:
                flash('Nova senha deve ter pelo menos 4 caracteres.', 'erro')
            elif nova_senha != confirmar_senha:
                flash('As senhas não conferem.', 'erro')
            else:
                current_user.definir_senha(nova_senha)
                db.session.commit()
                flash('Senha alterada com sucesso.', 'sucesso')

        return redirect(url_for('usuario.perfil'))

    comp = _obter_ou_criar_compartilhamento()
    colunas = (
        ColunaKanban.query.filter_by(id_usuario=current_user.id)
        .order_by(ColunaKanban.ordem)
        .all()
    )

    colunas_visiveis_ids = set()
    if comp.colunas_visiveis:
        colunas_visiveis_ids = {int(x) for x in comp.colunas_visiveis.split(',') if x.strip().isdigit()}

    link_publico = url_for('kanban.kanban_publico', token=comp.token, _external=True) if comp.ativo else None

    return render_template(
        'usuario/perfil.html',
        comp=comp,
        colunas=colunas,
        colunas_visiveis_ids=colunas_visiveis_ids,
        link_publico=link_publico,
    )


@bp_usuario.route('/kanban-share/toggle', methods=['POST'])
@login_required
def toggle_share():
    comp = _obter_ou_criar_compartilhamento()
    comp.ativo = not comp.ativo
    db.session.commit()
    link = url_for('kanban.kanban_publico', token=comp.token, _external=True) if comp.ativo else None
    return jsonify({'ativo': comp.ativo, 'link': link})


@bp_usuario.route('/kanban-share/regenerar', methods=['POST'])
@login_required
def regenerar_token():
    comp = _obter_ou_criar_compartilhamento()
    comp.token = secrets.token_urlsafe(32)
    db.session.commit()
    link = url_for('kanban.kanban_publico', token=comp.token, _external=True) if comp.ativo else None
    return jsonify({'token': comp.token, 'link': link})


@bp_usuario.route('/kanban-share/colunas', methods=['POST'])
@login_required
def salvar_colunas_share():
    dados = request.get_json(silent=True) or {}
    ids = dados.get('ids', [])

    # Valida que os IDs pertencem ao usuário
    colunas_validas = {
        c.id for c in ColunaKanban.query.filter_by(id_usuario=current_user.id).all()
    }
    ids_validos = [str(i) for i in ids if int(i) in colunas_validas]

    comp = _obter_ou_criar_compartilhamento()
    comp.colunas_visiveis = ','.join(ids_validos)
    db.session.commit()
    return jsonify({'ok': True})


# ── Compartilhamento com usuários cadastrados ─────────────────────────────────

@bp_usuario.route('/kanban-usuarios', methods=['GET'])
@login_required
def listar_usuarios_acesso():
    """Retorna todos os usuários com flag de acesso e papel atual."""
    acessos = {
        a.id_convidado: a
        for a in AcessoKanban.query.filter_by(id_dono=current_user.id).all()
    }
    usuarios = Usuario.query.filter(Usuario.id != current_user.id).order_by(Usuario.nome).all()
    resultado = []
    for u in usuarios:
        acesso = acessos.get(u.id)
        resultado.append({
            'id': u.id,
            'nome': u.nome,
            'usuario': u.usuario,
            'tem_acesso': acesso is not None,
            'papel': acesso.papel if acesso else None,
        })
    return jsonify(resultado)


@bp_usuario.route('/kanban-acesso', methods=['POST'])
@login_required
def conceder_acesso():
    """Concede ou atualiza acesso de um usuário ao kanban."""
    dados = request.get_json(silent=True) or {}
    id_convidado = dados.get('id_convidado')
    papel = dados.get('papel', 'usuario')

    if not id_convidado or id_convidado == current_user.id:
        return jsonify({'erro': 'Usuário inválido'}), 400
    if papel not in ('admin', 'usuario'):
        return jsonify({'erro': 'Papel inválido'}), 400
    if not Usuario.query.get(id_convidado):
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    acesso = AcessoKanban.query.filter_by(
        id_dono=current_user.id, id_convidado=id_convidado
    ).first()
    if acesso:
        acesso.papel = papel
    else:
        acesso = AcessoKanban(id_dono=current_user.id, id_convidado=id_convidado, papel=papel)
        db.session.add(acesso)
    db.session.commit()
    return jsonify({'ok': True, 'papel': papel})


@bp_usuario.route('/kanban-acesso/<int:id_convidado>', methods=['DELETE'])
@login_required
def revogar_acesso(id_convidado):
    """Remove o acesso de um usuário ao kanban."""
    acesso = AcessoKanban.query.filter_by(
        id_dono=current_user.id, id_convidado=id_convidado
    ).first()
    if acesso:
        db.session.delete(acesso)
        db.session.commit()
    return jsonify({'ok': True})


# ── Painel de administração ───────────────────────────────────────────────────

@bp_usuario.route('/admin/usuarios')
@login_required
@requer_admin
def admin_usuarios():
    """Lista todos os usuários para gerenciamento."""
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    visualizando_id = session.get('admin_visualizando_id')
    return render_template('admin/usuarios.html', usuarios=usuarios, visualizando_id=visualizando_id)


@bp_usuario.route('/admin/visualizar/<int:user_id>', methods=['POST'])
@login_required
@requer_admin
def admin_visualizar(user_id):
    """Inicia visualização como outro usuário."""
    if user_id == current_user.id:
        session.pop('admin_visualizando_id', None)
    else:
        usuario = Usuario.query.get_or_404(user_id)
        session['admin_visualizando_id'] = usuario.id
    return redirect(url_for('main.dashboard'))


@bp_usuario.route('/admin/voltar', methods=['POST'])
@login_required
@requer_admin
def admin_voltar():
    """Encerra visualização como outro usuário."""
    session.pop('admin_visualizando_id', None)
    return redirect(url_for('usuario.admin_usuarios'))


@bp_usuario.route('/admin/papel', methods=['POST'])
@login_required
@requer_admin
def admin_set_papel():
    """Altera o papel (admin/usuario) de um usuário."""
    dados = request.get_json(silent=True) or {}
    user_id = dados.get('id')
    papel = dados.get('papel')

    if not user_id or papel not in ('admin', 'usuario'):
        return jsonify({'erro': 'Dados inválidos'}), 400
    if user_id == current_user.id:
        return jsonify({'erro': 'Não é possível alterar o próprio papel'}), 400

    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    from flask import current_app
    admin_padrao = current_app.config.get('ADMIN_PADRAO')
    if admin_padrao and usuario.usuario == admin_padrao:
        return jsonify({'erro': 'O admin padrão do sistema não pode ser rebaixado'}), 403

    usuario.papel = papel
    db.session.commit()
    return jsonify({'ok': True, 'papel': papel})


# ── Permissões de módulos por usuário ─────────────────────────────────────────

@bp_usuario.route('/admin/permissoes/<int:user_id>', methods=['GET'])
@login_required
@requer_admin
def admin_get_permissoes(user_id):
    """Retorna as permissões de módulos de um usuário."""
    p = get_permissoes(user_id)
    return jsonify({m: getattr(p, m) for m in MODULOS})


@bp_usuario.route('/admin/permissoes/<int:user_id>', methods=['POST'])
@login_required
@requer_admin
def admin_set_permissao(user_id):
    """Ativa/desativa um módulo para um usuário."""
    dados = request.get_json(silent=True) or {}
    modulo = dados.get('modulo')
    valor = dados.get('valor')

    if modulo not in MODULOS or not isinstance(valor, bool):
        return jsonify({'erro': 'Dados inválidos'}), 400
    if user_id == current_user.id:
        return jsonify({'erro': 'Não é possível alterar as próprias permissões'}), 400

    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    p = get_permissoes(user_id)
    setattr(p, modulo, valor)
    db.session.commit()
    return jsonify({'ok': True})


@bp_usuario.route('/admin/redefinir-senha/<int:user_id>', methods=['POST'])
@login_required
@requer_admin
def admin_redefinir_senha(user_id):
    """Redefine a senha de um usuário."""
    if user_id == current_user.id:
        return jsonify({'erro': 'Use a seção de perfil para alterar a própria senha'}), 400

    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({'erro': 'Usuário não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    nova_senha = dados.get('senha', '').strip()
    if len(nova_senha) < 4:
        return jsonify({'erro': 'A senha deve ter pelo menos 4 caracteres'}), 400

    usuario.definir_senha(nova_senha)
    db.session.commit()
    return jsonify({'ok': True})


@bp_usuario.route('/admin/todos-usuarios')
@login_required
@requer_admin
def admin_todos_usuarios():
    """Retorna todos os usuários com seus papéis e permissões (para o painel no perfil)."""
    usuarios = Usuario.query.filter(Usuario.id != current_user.id).order_by(Usuario.nome).all()
    resultado = []
    for u in usuarios:
        p = get_permissoes(u.id)
        resultado.append({
            'id': u.id,
            'nome': u.nome,
            'usuario': u.usuario,
            'papel': u.papel,
            'permissoes': {m: getattr(p, m) for m in MODULOS},
        })
    return jsonify(resultado)
