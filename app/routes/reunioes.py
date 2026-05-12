"""app/routes/reunioes.py — Rotas de Reuniões."""

import json
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, render_template, request, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.utils import get_usuario_ativo, verificar_acesso_modulo
from models import Reuniao, db

bp_reunioes = Blueprint('reunioes', __name__, url_prefix='/reunioes')


@bp_reunioes.before_request
def _verificar_reunioes():
    return verificar_acesso_modulo('reunioes')


_ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
_MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
          'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def _ext_ok(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in _ALLOWED_IMG


def _upload_dir():
    return os.path.join(current_app.config['UPLOAD_FOLDER'], 'reunioes')


def _reuniao_do_usuario(reuniao_id):
    return Reuniao.query.filter_by(id=reuniao_id, id_usuario=get_usuario_ativo().id).first()


def _inicio_semana(ref: date) -> date:
    return ref - timedelta(days=ref.weekday())


def _label_semana(inicio: date, fim: date) -> str:
    if inicio.month == fim.month:
        return f'{inicio.day}–{fim.day} {_MESES[inicio.month - 1]} {inicio.year}'
    if inicio.year == fim.year:
        return (f'{inicio.day} {_MESES[inicio.month - 1]}'
                f' – {fim.day} {_MESES[fim.month - 1]} {inicio.year}')
    return (f'{inicio.day} {_MESES[inicio.month - 1]} {inicio.year}'
            f' – {fim.day} {_MESES[fim.month - 1]} {fim.year}')


def _serializar(r: Reuniao) -> dict:
    return {
        'id': r.id,
        'nome': r.nome,
        'equipe': r.equipe or '',
        'data_reuniao': r.data_reuniao.isoformat(),
        'hora_inicio': r.hora_inicio or '',
        'hora_fim': r.hora_fim or '',
        'participantes': r.participantes or '',
        'anotacoes': r.anotacoes or '',
        'imagens': json.loads(r.imagens_json or '[]'),
    }


@bp_reunioes.route('/lista')
@login_required
def lista_reunioes():
    q = request.args.get('q', '').strip()
    query = Reuniao.query.filter_by(id_usuario=get_usuario_ativo().id)
    if q:
        query = query.filter(Reuniao.nome.ilike(f'%{q}%'))
    reunioes = query.order_by(Reuniao.data_reuniao.desc()).limit(20).all()
    return jsonify([{
        'id': r.id,
        'nome': r.nome,
        'data': r.data_reuniao.isoformat(),
        'hora_inicio': r.hora_inicio,
    } for r in reunioes])


@bp_reunioes.route('')
@login_required
def reunioes():
    semana_str = request.args.get('semana')
    try:
        ref = date.fromisoformat(semana_str) if semana_str else date.today()
        inicio = _inicio_semana(ref)
    except ValueError:
        inicio = _inicio_semana(date.today())

    fim = inicio + timedelta(days=6)

    itens = (
        Reuniao.query
        .filter(
            Reuniao.id_usuario == get_usuario_ativo().id,
            Reuniao.data_reuniao >= inicio,
            Reuniao.data_reuniao <= fim,
        )
        .order_by(Reuniao.data_reuniao, Reuniao.hora_inicio)
        .all()
    )

    dias = [inicio + timedelta(days=i) for i in range(7)]
    por_dia = {d: [] for d in dias}
    for r in itens:
        if r.data_reuniao in por_dia:
            por_dia[r.data_reuniao].append(r)

    return render_template(
        'reunioes/reunioes.html',
        dias=dias,
        por_dia=por_dia,
        hoje=date.today(),
        label_semana=_label_semana(inicio, fim),
        semana_anterior=(inicio - timedelta(days=7)).isoformat(),
        proxima_semana=(inicio + timedelta(days=7)).isoformat(),
        hoje_semana=_inicio_semana(date.today()).isoformat(),
    )


@bp_reunioes.route('', methods=['POST'])
@login_required
def criar_reuniao():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    data_str = (dados.get('data_reuniao') or '').strip()

    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    if not data_str:
        return jsonify({'erro': 'Data obrigatória'}), 400

    try:
        data_obj = date.fromisoformat(data_str)
    except ValueError:
        return jsonify({'erro': 'Data inválida'}), 400

    r = Reuniao(
        id_usuario=get_usuario_ativo().id,
        nome=nome,
        equipe=(dados.get('equipe') or '').strip(),
        data_reuniao=data_obj,
        hora_inicio=(dados.get('hora_inicio') or '').strip(),
        hora_fim=(dados.get('hora_fim') or '').strip(),
        participantes=(dados.get('participantes') or '').strip(),
        anotacoes=(dados.get('anotacoes') or '').strip(),
        imagens_json='[]',
    )
    db.session.add(r)
    db.session.commit()

    return jsonify({'id': r.id, 'ok': True}), 201


@bp_reunioes.route('/<int:id>', methods=['GET'])
@login_required
def get_reuniao(id):
    r = _reuniao_do_usuario(id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    return jsonify(_serializar(r))


@bp_reunioes.route('/<int:id>', methods=['PUT'])
@login_required
def editar_reuniao(id):
    r = _reuniao_do_usuario(id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}

    if 'nome' in dados:
        nome = (dados['nome'] or '').strip()
        if not nome:
            return jsonify({'erro': 'Nome obrigatório'}), 400
        r.nome = nome

    if 'data_reuniao' in dados:
        try:
            r.data_reuniao = date.fromisoformat(dados['data_reuniao'])
        except ValueError:
            return jsonify({'erro': 'Data inválida'}), 400

    for campo in ('equipe', 'hora_inicio', 'hora_fim', 'participantes', 'anotacoes'):
        if campo in dados:
            setattr(r, campo, (dados[campo] or '').strip())

    r.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


@bp_reunioes.route('/<int:id>', methods=['DELETE'])
@login_required
def excluir_reuniao(id):
    r = _reuniao_do_usuario(id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'ok': True})


@bp_reunioes.route('/<int:id>/imagem', methods=['POST'])
@login_required
def upload_imagem(id):
    r = _reuniao_do_usuario(id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404

    f = request.files.get('imagem')
    if not f or not f.filename or not _ext_ok(f.filename):
        return jsonify({'erro': 'Arquivo inválido'}), 400

    pasta = _upload_dir()
    os.makedirs(pasta, exist_ok=True)

    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    nome_arquivo = f'{ts}_{secure_filename(f.filename)}'
    f.save(os.path.join(pasta, nome_arquivo))

    caminho_rel = f'uploads/reunioes/{nome_arquivo}'
    imgs = json.loads(r.imagens_json or '[]')
    imgs.append(caminho_rel)
    r.imagens_json = json.dumps(imgs)
    db.session.commit()

    return jsonify({'ok': True, 'caminho': caminho_rel}), 201


@bp_reunioes.route('/<int:id>/imagem', methods=['DELETE'])
@login_required
def remover_imagem(id):
    r = _reuniao_do_usuario(id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    caminho = dados.get('caminho', '')
    imgs = json.loads(r.imagens_json or '[]')
    if caminho in imgs:
        imgs.remove(caminho)
        r.imagens_json = json.dumps(imgs)
        db.session.commit()

    return jsonify({'ok': True})
