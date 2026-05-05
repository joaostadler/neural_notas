"""app/routes/kanban.py — Rotas do quadro Kanban."""

import os
from io import BytesIO
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from models import CartaoKanban, ColunaKanban, ExecucaoCartao, HistoricoEtapas, db

bp_kanban = Blueprint('kanban', __name__, url_prefix='/kanban')

COLUNAS_PADRAO = [
    {'nome': 'A Fazer',      'cor': '#64748b'},
    {'nome': 'Aprovado',     'cor': "#501d5a"},
    {'nome': 'Em Andamento', 'cor': '#2563eb'},
    {'nome': 'Impedimento',  'cor': "#eb2525"},
    {'nome': 'Em Revisão',   'cor': '#d97706'},
    {'nome': 'Concluído',    'cor': '#16a34a'},
]


def _coluna_do_usuario(coluna_id):
    return ColunaKanban.query.filter_by(id=coluna_id, id_usuario=current_user.id).first()


def _cartao_do_usuario(cartao_id):
    return (
        CartaoKanban.query
        .join(ColunaKanban)
        .filter(CartaoKanban.id == cartao_id, ColunaKanban.id_usuario == current_user.id)
        .first()
    )


def _proxima_ordem_coluna():
    ultima = db.session.query(db.func.max(ColunaKanban.ordem)).filter_by(id_usuario=current_user.id).scalar()
    return (ultima or 0) + 1


def _proxima_ordem_cartao(coluna_id):
    ultima = db.session.query(db.func.max(CartaoKanban.ordem)).filter_by(id_coluna=coluna_id).scalar()
    return (ultima or 0) + 1


@bp_kanban.route('')
@login_required
def kanban():
    colunas = (
        ColunaKanban.query.filter_by(id_usuario=current_user.id)
        .order_by(ColunaKanban.ordem)
        .all()
    )

    if not colunas:
        for i, col in enumerate(COLUNAS_PADRAO):
            db.session.add(ColunaKanban(
                id_usuario=current_user.id,
                nome=col['nome'],
                cor=col['cor'],
                ordem=i + 1,
            ))
        db.session.commit()
        colunas = (
            ColunaKanban.query.filter_by(id_usuario=current_user.id)
            .order_by(ColunaKanban.ordem)
            .all()
        )

    ultima_coluna = colunas[-1] if colunas else None
    ultima_coluna_id = ultima_coluna.id if ultima_coluna else None

    # Data de conclusão: entrada mais recente de cada cartão na última coluna
    conclusoes = {}
    if ultima_coluna:
        for h in HistoricoEtapas.query.filter_by(id_coluna=ultima_coluna.id).all():
            if h.id_cartao not in conclusoes or h.data_entrada > conclusoes[h.id_cartao]:
                conclusoes[h.id_cartao] = h.data_entrada

    for col in colunas:
        col.cartoes_ordenados = sorted(col.cartoes, key=lambda c: c.ordem)

    return render_template(
        'kanban/kanban.html',
        colunas=colunas,
        ultima_coluna_id=ultima_coluna_id,
        conclusoes=conclusoes,
    )


# ── Colunas ───────────────────────────────────────────────────────────────────

@bp_kanban.route('/colunas', methods=['POST'])
@login_required
def criar_coluna():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    cor = (dados.get('cor') or '#4a9eff').strip()

    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400

    coluna = ColunaKanban(
        id_usuario=current_user.id,
        nome=nome,
        cor=cor,
        ordem=_proxima_ordem_coluna(),
    )
    db.session.add(coluna)
    db.session.commit()
    return jsonify({'id': coluna.id, 'nome': coluna.nome, 'cor': coluna.cor, 'ordem': coluna.ordem})


@bp_kanban.route('/colunas/<int:id>', methods=['PUT'])
@login_required
def editar_coluna(id):
    coluna = _coluna_do_usuario(id)
    if not coluna:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    cor = (dados.get('cor') or '').strip()

    if nome:
        coluna.nome = nome
    if cor:
        coluna.cor = cor
    db.session.commit()
    return jsonify({'ok': True, 'nome': coluna.nome, 'cor': coluna.cor})


@bp_kanban.route('/colunas/<int:id>', methods=['DELETE'])
@login_required
def excluir_coluna(id):
    coluna = _coluna_do_usuario(id)
    if not coluna:
        return jsonify({'erro': 'Não encontrado'}), 404

    db.session.delete(coluna)
    db.session.commit()
    return jsonify({'ok': True})


# ── Cartões ───────────────────────────────────────────────────────────────────

@bp_kanban.route('/cartoes', methods=['POST'])
@login_required
def criar_cartao():
    dados = request.get_json(silent=True) or {}
    titulo = (dados.get('titulo') or '').strip()
    id_coluna = dados.get('id_coluna')

    if not titulo:
        return jsonify({'erro': 'Título obrigatório'}), 400
    if not id_coluna or not _coluna_do_usuario(id_coluna):
        return jsonify({'erro': 'Coluna inválida'}), 400

    cartao = CartaoKanban(
        id_coluna=id_coluna,
        titulo=titulo,
        descricao=dados.get('descricao', ''),
        etiquetas=dados.get('etiquetas', ''),
        prioridade=dados.get('prioridade', 'baixa'),
        ordem=_proxima_ordem_cartao(id_coluna),
    )
    db.session.add(cartao)
    db.session.flush()

    coluna = _coluna_do_usuario(id_coluna)
    db.session.add(HistoricoEtapas(
        id_cartao=cartao.id,
        id_coluna=id_coluna,
        nome_coluna=coluna.nome,
    ))
    db.session.commit()

    return jsonify({
        'id': cartao.id,
        'titulo': cartao.titulo,
        'descricao': cartao.descricao,
        'etiquetas': cartao.etiquetas,
        'prioridade': cartao.prioridade,
        'ordem': cartao.ordem,
        'criado_em': cartao.criado_em.strftime('%Y-%m-%d'),
    })


@bp_kanban.route('/cartoes/<int:id>', methods=['PUT'])
@login_required
def editar_cartao(id):
    cartao = _cartao_do_usuario(id)
    if not cartao:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    titulo = (dados.get('titulo') or '').strip()

    if titulo:
        cartao.titulo = titulo
    if 'descricao' in dados:
        cartao.descricao = dados['descricao']
    if 'etiquetas' in dados:
        cartao.etiquetas = dados['etiquetas']
    if 'prioridade' in dados and dados['prioridade'] in ('baixa', 'media', 'alta'):
        cartao.prioridade = dados['prioridade']

    db.session.commit()
    return jsonify({'ok': True})


@bp_kanban.route('/cartoes/<int:id>', methods=['DELETE'])
@login_required
def excluir_cartao(id):
    cartao = _cartao_do_usuario(id)
    if not cartao:
        return jsonify({'erro': 'Não encontrado'}), 404

    db.session.delete(cartao)
    db.session.commit()
    return jsonify({'ok': True})


@bp_kanban.route('/cartoes/<int:id>/mover', methods=['POST'])
@login_required
def mover_cartao(id):
    cartao = _cartao_do_usuario(id)
    if not cartao:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    nova_coluna_id = dados.get('id_coluna')
    nova_ordem = dados.get('ordem', 0)
    observacoes_conclusao = dados.get('observacoes_conclusao', '').strip()

    if not nova_coluna_id or not _coluna_do_usuario(nova_coluna_id):
        return jsonify({'erro': 'Coluna inválida'}), 400

    colunas = (
        ColunaKanban.query.filter_by(id_usuario=current_user.id)
        .order_by(ColunaKanban.ordem)
        .all()
    )
    ultima_coluna_id = colunas[-1].id if colunas else None

    if nova_coluna_id == ultima_coluna_id and not observacoes_conclusao:
        return jsonify({'erro': 'Observações da conclusão são obrigatórias'}), 400

    coluna_antiga = cartao.id_coluna
    cartao.id_coluna = nova_coluna_id
    cartao.ordem = nova_ordem

    if nova_coluna_id == ultima_coluna_id:
        cartao.observacoes_conclusao = observacoes_conclusao
    elif coluna_antiga == ultima_coluna_id:
        cartao.observacoes_conclusao = ''

    if coluna_antiga != nova_coluna_id:
        nova_coluna = _coluna_do_usuario(nova_coluna_id)
        db.session.add(HistoricoEtapas(
            id_cartao=cartao.id,
            id_coluna=nova_coluna_id,
            nome_coluna=nova_coluna.nome,
        ))

    db.session.commit()
    return jsonify({'ok': True})


@bp_kanban.route('/upload-imagem', methods=['POST'])
@login_required
def upload_imagem_kanban():
    from PIL import Image

    arquivo = request.files.get('imagem')
    if not arquivo or not arquivo.filename:
        return jsonify({'erro': 'Arquivo inválido'}), 400

    ext = arquivo.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
        return jsonify({'erro': 'Formato inválido'}), 400

    pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], 'kanban', str(current_user.id))
    os.makedirs(pasta, exist_ok=True)

    nome_arquivo = f'{uuid4().hex}.{"png" if ext == "png" else "jpg"}'
    caminho_abs = os.path.join(pasta, nome_arquivo)

    img = Image.open(BytesIO(arquivo.read()))
    img = img.convert('RGBA') if img.mode in ('RGBA', 'LA', 'P') else img.convert('RGB')
    max_w = 400
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

    fmt = 'PNG' if ext == 'png' else 'JPEG'
    if fmt == 'JPEG' and img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(caminho_abs, fmt, quality=85)

    caminho_rel = os.path.relpath(caminho_abs, current_app.static_folder).replace('\\', '/')
    return jsonify({'url': f'/static/{caminho_rel}'})


@bp_kanban.route('/cartoes/<int:id>/execucoes', methods=['GET'])
@login_required
def listar_execucoes(id):
    cartao = _cartao_do_usuario(id)
    if not cartao:
        return jsonify({'erro': 'Não encontrado'}), 404
    execucoes = sorted(cartao.execucoes, key=lambda e: e.criado_em, reverse=True)
    return jsonify([{
        'id': e.id,
        'texto': e.texto,
        'concluida': e.concluida,
        'criado_em': e.criado_em.strftime('%d/%m/%Y %H:%M'),
    } for e in execucoes])


@bp_kanban.route('/cartoes/<int:id>/execucoes', methods=['POST'])
@login_required
def criar_execucao(id):
    cartao = _cartao_do_usuario(id)
    if not cartao:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    texto = (dados.get('texto') or '').strip()
    if not texto:
        return jsonify({'erro': 'Texto obrigatório'}), 400
    execucao = ExecucaoCartao(id_cartao=id, texto=texto)
    db.session.add(execucao)
    db.session.commit()
    return jsonify({
        'id': execucao.id,
        'texto': execucao.texto,
        'concluida': execucao.concluida,
        'criado_em': execucao.criado_em.strftime('%d/%m/%Y %H:%M'),
    })


@bp_kanban.route('/execucoes/<int:id>', methods=['DELETE'])
@login_required
def excluir_execucao(id):
    execucao = (
        ExecucaoCartao.query
        .join(CartaoKanban)
        .join(ColunaKanban)
        .filter(ExecucaoCartao.id == id, ColunaKanban.id_usuario == current_user.id)
        .first()
    )
    if not execucao:
        return jsonify({'erro': 'Não encontrado'}), 404
    db.session.delete(execucao)
    db.session.commit()
    return jsonify({'ok': True})


@bp_kanban.route('/execucoes/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_execucao(id):
    execucao = (
        ExecucaoCartao.query
        .join(CartaoKanban)
        .join(ColunaKanban)
        .filter(ExecucaoCartao.id == id, ColunaKanban.id_usuario == current_user.id)
        .first()
    )
    if not execucao:
        return jsonify({'erro': 'Não encontrado'}), 404
    execucao.concluida = not execucao.concluida
    db.session.commit()
    return jsonify({'ok': True, 'concluida': execucao.concluida})


@bp_kanban.route('/reordenar', methods=['POST'])
@login_required
def reordenar():
    dados = request.get_json(silent=True) or {}

    for col_data in dados.get('colunas', []):
        coluna = _coluna_do_usuario(col_data['id'])
        if coluna:
            coluna.ordem = col_data['ordem']

    for card_data in dados.get('cartoes', []):
        cartao = _cartao_do_usuario(card_data['id'])
        if cartao:
            nova_coluna_id = card_data.get('id_coluna')
            if nova_coluna_id and _coluna_do_usuario(nova_coluna_id):
                coluna_antiga = cartao.id_coluna
                cartao.id_coluna = nova_coluna_id
                cartao.ordem = card_data['ordem']

                if coluna_antiga != nova_coluna_id:
                    nova_coluna = _coluna_do_usuario(nova_coluna_id)
                    db.session.add(HistoricoEtapas(
                        id_cartao=cartao.id,
                        id_coluna=nova_coluna_id,
                        nome_coluna=nova_coluna.nome,
                    ))

    db.session.commit()
    return jsonify({'ok': True})
