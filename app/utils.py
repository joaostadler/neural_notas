"""app/utils.py — Utilitários de permissão e contexto de usuário."""

from functools import wraps

from flask import abort, flash, redirect, request, session, url_for
from flask_login import current_user

MODULOS = ('biblioteca', 'kanban', 'tarefas', 'reunioes', 'roadmap')

# Endpoints do main blueprint que não exigem permissão de biblioteca
_ENDPOINTS_LIVRES = frozenset({'main.index', 'main.dashboard', 'main.health', 'static', None})


def get_usuario_ativo():
    """Retorna o usuário efetivo.

    Quando um admin está visualizando outro usuário via sessão,
    retorna o usuário-alvo. Caso contrário retorna current_user.
    """
    if current_user.is_authenticated and current_user.papel == 'admin':
        vid = session.get('admin_visualizando_id')
        if vid and vid != current_user.id:
            from models import Usuario
            u = Usuario.query.get(vid)
            if u:
                return u
    return current_user


def get_permissoes(usuario_id):
    """Retorna PermissaoUsuario do usuário, criando registro com defaults se não existir."""
    from models import PermissaoUsuario, db
    p = PermissaoUsuario.query.get(usuario_id)
    if not p:
        p = PermissaoUsuario(id_usuario=usuario_id)
        db.session.add(p)
        db.session.commit()
    return p


def verificar_acesso_modulo(modulo):
    """Verifica se current_user tem acesso ao módulo.

    Retorna None se permitido, ou Response apropriada se bloqueado.
    - Navegação de página (Sec-Fetch-Mode: navigate): redireciona ao dashboard com flash.
    - Requisição AJAX/fetch: retorna 403 JSON sem redirecionar (evita loop e flash duplicado).
    Admins sempre têm acesso total.
    """
    if not current_user.is_authenticated:
        return None
    if current_user.papel == 'admin':
        return None
    if modulo == 'biblioteca' and request.endpoint in _ENDPOINTS_LIVRES:
        return None
    perms = get_permissoes(current_user.id)
    if not getattr(perms, modulo, True):
        # Sec-Fetch-Mode: navigate → navegação real de página; qualquer outra coisa → AJAX/fetch
        if request.headers.get('Sec-Fetch-Mode', 'navigate') == 'navigate':
            flash('Você não tem acesso a esta área.', 'erro')
            return redirect(url_for('main.dashboard'))
        from flask import jsonify, make_response
        return make_response(jsonify({'erro': 'Sem acesso a esta área'}), 403)
    return None


def requer_admin(f):
    """Decorator que restringe a rota a usuários com papel 'admin'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.papel != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated
