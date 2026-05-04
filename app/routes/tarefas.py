"""app/routes/tarefas.py — Rotas de Tarefas Rápidas."""

from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from models import TarefaFacil, db

bp_tarefas = Blueprint('tarefas', __name__, url_prefix='/tarefas')


def _tarefa_do_usuario(tarefa_id):
    return TarefaFacil.query.filter_by(id=tarefa_id, id_usuario=current_user.id).first()


@bp_tarefas.route('')
@login_required
def tarefas():
    itens = (
        TarefaFacil.query
        .filter_by(id_usuario=current_user.id)
        .order_by(TarefaFacil.data_tarefa.desc(), TarefaFacil.criado_em.desc())
        .all()
    )
    return render_template('tarefas/tarefas.html', tarefas=itens)


@bp_tarefas.route('', methods=['POST'])
@login_required
def criar_tarefa():
    dados = request.get_json(silent=True) or {}
    descricao = (dados.get('descricao') or '').strip()
    data_str = (dados.get('data_tarefa') or '').strip()

    if not descricao:
        return jsonify({'erro': 'Descrição obrigatória'}), 400

    try:
        data_obj = date.fromisoformat(data_str) if data_str else date.today()
    except ValueError:
        return jsonify({'erro': 'Data inválida'}), 400

    tarefa = TarefaFacil(
        id_usuario=current_user.id,
        data_tarefa=data_obj,
        solicitante=(dados.get('solicitante') or '').strip(),
        descricao=descricao,
        concluida=False,
    )
    db.session.add(tarefa)
    db.session.commit()

    return jsonify({
        'id': tarefa.id,
        'data_tarefa': tarefa.data_tarefa.isoformat(),
        'solicitante': tarefa.solicitante,
        'descricao': tarefa.descricao,
        'concluida': tarefa.concluida,
    }), 201


@bp_tarefas.route('/<int:id>', methods=['PUT'])
@login_required
def editar_tarefa(id):
    tarefa = _tarefa_do_usuario(id)
    if not tarefa:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    descricao = (dados.get('descricao') or '').strip()
    data_str = (dados.get('data_tarefa') or '').strip()

    if descricao:
        tarefa.descricao = descricao
    if 'solicitante' in dados:
        tarefa.solicitante = (dados['solicitante'] or '').strip()
    if data_str:
        try:
            tarefa.data_tarefa = date.fromisoformat(data_str)
        except ValueError:
            return jsonify({'erro': 'Data inválida'}), 400

    db.session.commit()
    return jsonify({'ok': True})


@bp_tarefas.route('/<int:id>', methods=['DELETE'])
@login_required
def excluir_tarefa(id):
    tarefa = _tarefa_do_usuario(id)
    if not tarefa:
        return jsonify({'erro': 'Não encontrado'}), 404

    db.session.delete(tarefa)
    db.session.commit()
    return jsonify({'ok': True})


@bp_tarefas.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_tarefa(id):
    tarefa = _tarefa_do_usuario(id)
    if not tarefa:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    tarefa.concluida = not tarefa.concluida
    if tarefa.concluida:
        tarefa.concluida_em = datetime.utcnow()
        obs = (dados.get('observacao') or '').strip()
        tarefa.observacao_conclusao = obs if obs else None
    else:
        tarefa.concluida_em = None
        tarefa.observacao_conclusao = None
    db.session.commit()
    concluida_em_str = tarefa.concluida_em.strftime('%d/%m/%Y') if tarefa.concluida_em else None
    return jsonify({
        'ok': True,
        'concluida': tarefa.concluida,
        'concluida_em': concluida_em_str,
        'observacao': tarefa.observacao_conclusao or '',
    })
