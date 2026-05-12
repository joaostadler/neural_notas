"""app/routes/roadmap.py — Rotas do Roadmap."""

from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.utils import get_usuario_ativo, verificar_acesso_modulo
from models import (CartaoKanban, ColunaKanban, ColunaRoadmap, LinhaRoadmap,
                    ProjetoRoadmap, Roadmap, SubgrupoRoadmap, db)

bp_roadmap = Blueprint('roadmap', __name__, url_prefix='/roadmap')


@bp_roadmap.before_request
def _verificar_roadmap():
    return verificar_acesso_modulo('roadmap')


def _roadmap_do_usuario(roadmap_id):
    return Roadmap.query.filter_by(id=roadmap_id, id_usuario=get_usuario_ativo().id).first()


def _parse_date(valor):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


def _pack_tracks(projetos_dicts):
    """Greedy track packing: returns list of tracks (each track = list of proj dicts).
    Projects must be pre-sorted by (ordem, data_inicio).
    Non-overlapping projects share a track; overlapping go to separate tracks.
    """
    tracks = []  # list of (proj_list, track_end_date_str)
    for proj in projetos_dicts:
        placed = False
        for i, (track, end) in enumerate(tracks):
            if proj['data_inicio'] > end:
                track.append(proj)
                tracks[i] = (track, proj['data_fim'])
                placed = True
                break
        if not placed:
            tracks.append(([proj], proj['data_fim']))
    return [t for t, _ in tracks]


def _posicoes(roadmap):
    colunas = sorted(roadmap.colunas, key=lambda c: c.ordem)
    linhas = sorted(roadmap.linhas, key=lambda l: l.ordem)
    tem_subgrupos = any(l.subgrupos for l in linhas)

    def _proj_dict(p, left, width):
        return {
            'id': p.id, 'nome': p.nome,
            'data_inicio': str(p.data_inicio), 'data_fim': str(p.data_fim),
            'cor': p.cor, 'status': p.status,
            'id_subgrupo': p.id_subgrupo,
            'descricao': p.descricao or '',
            'ordem': p.ordem or 0,
            'left_pct': left, 'width_pct': width,
        }

    if not colunas:
        linhas_data = []
        for l in linhas:
            subs = sorted(l.subgrupos, key=lambda s: s.ordem)
            linhas_data.append({
                'id': l.id, 'nome': l.nome, 'cor': l.cor,
                'projetos': [], 'tracks': [], 'n_tracks': 0,
                'subgrupos': [
                    {'id': s.id, 'nome': s.nome, 'projetos': [], 'tracks': [], 'n_tracks': 0}
                    for s in subs
                ],
            })
        return [], linhas_data, tem_subgrupos

    data_ini_rm = min(c.data_inicio for c in colunas)
    data_fim_rm = max(c.data_fim for c in colunas)
    total_dias = (data_fim_rm - data_ini_rm).days + 1

    def pct(d):
        return round((d - data_ini_rm).days / total_dias * 100, 4)

    def dur(ini, fim):
        return round(((fim - ini).days + 1) / total_dias * 100, 4)

    def calcular(p):
        left = max(pct(p.data_inicio), 0)
        width = min(dur(p.data_inicio, p.data_fim), 100 - left)
        return _proj_dict(p, left, width)

    colunas_pos = [
        {
            'id': c.id, 'nome': c.nome,
            'data_inicio': str(c.data_inicio), 'data_fim': str(c.data_fim),
            'left_pct': pct(c.data_inicio),
            'width_pct': dur(c.data_inicio, c.data_fim),
        }
        for c in colunas
    ]

    linhas_data = []
    for l in linhas:
        subs = sorted(l.subgrupos, key=lambda s: s.ordem)
        # Projetos sem subgrupo (diretos na linha), ordenados por (ordem, data_inicio)
        diretos = [calcular(p) for p in sorted(
            (p for p in l.projetos if p.id_subgrupo is None),
            key=lambda x: (x.ordem or 0, x.data_inicio),
        )]
        direto_tracks = _pack_tracks(diretos)
        # Projetos por subgrupo
        subgrupos_data = []
        for s in subs:
            ps = [calcular(p) for p in sorted(
                s.projetos, key=lambda x: (x.ordem or 0, x.data_inicio)
            )]
            sub_tracks = _pack_tracks(ps)
            subgrupos_data.append({
                'id': s.id, 'nome': s.nome,
                'projetos': ps, 'tracks': sub_tracks, 'n_tracks': len(sub_tracks),
            })

        linhas_data.append({
            'id': l.id, 'nome': l.nome, 'cor': l.cor,
            'projetos': diretos,
            'tracks': direto_tracks,
            'n_tracks': len(direto_tracks),
            'subgrupos': subgrupos_data,
        })

    return colunas_pos, linhas_data, tem_subgrupos


# ── Roadmaps ──────────────────────────────────────────────────────────────────

@bp_roadmap.route('')
@login_required
def lista():
    roadmaps = (Roadmap.query
                .filter_by(id_usuario=get_usuario_ativo().id)
                .order_by(Roadmap.criado_em.desc())
                .all())
    if roadmaps:
        padrao = next((r for r in roadmaps if r.padrao), None)
        destino = padrao or roadmaps[0]
        return redirect(url_for('roadmap.ver', roadmap_id=destino.id))
    return render_template('roadmap/lista.html', roadmaps=roadmaps)


@bp_roadmap.route('', methods=['POST'])
@login_required
def criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    r = Roadmap(id_usuario=get_usuario_ativo().id, nome=nome)
    db.session.add(r)
    db.session.commit()
    return jsonify({'id': r.id, 'nome': r.nome}), 201


@bp_roadmap.route('/<int:roadmap_id>')
@login_required
def ver(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        flash('Roadmap não encontrado.', 'warning')
        return redirect(url_for('roadmap.lista'))
    todos_roadmaps = (Roadmap.query
                      .filter_by(id_usuario=get_usuario_ativo().id)
                      .order_by(Roadmap.nome)
                      .all())
    colunas_pos, linhas_data, tem_subgrupos = _posicoes(r)
    subgrupos_map = {
        str(l['id']): l['subgrupos']
        for l in linhas_data
    }
    # Build row_tracks: n_tracks per CSS grid row (same order as template renders rows)
    row_tracks = []
    for l in linhas_data:
        n_subs = len(l['subgrupos'])
        tem_diretos = len(l['projetos']) > 0
        if tem_subgrupos:
            if n_subs > 0:
                for sub in l['subgrupos']:
                    row_tracks.append(max(sub['n_tracks'], 1))
                if tem_diretos:
                    row_tracks.append(max(l['n_tracks'], 1))
            else:
                row_tracks.append(max(l['n_tracks'], 1))
        else:
            row_tracks.append(max(l['n_tracks'], 1))
    total_rows = len(row_tracks)
    return render_template('roadmap/roadmap.html',
                           roadmap=r,
                           todos_roadmaps=todos_roadmaps,
                           colunas_pos=colunas_pos,
                           linhas_data=linhas_data,
                           tem_subgrupos=tem_subgrupos,
                           subgrupos_map=subgrupos_map,
                           row_tracks=row_tracks,
                           total_rows=total_rows)


@bp_roadmap.route('/<int:roadmap_id>/padrao', methods=['PUT'])
@login_required
def definir_padrao(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    ativar = dados.get('ativo', True)
    Roadmap.query.filter_by(id_usuario=get_usuario_ativo().id).update({'padrao': False})
    if ativar:
        r.padrao = True
    db.session.commit()
    return jsonify({'ok': True, 'padrao': r.padrao})


@bp_roadmap.route('/<int:roadmap_id>', methods=['PUT'])
@login_required
def atualizar(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados:
        nome = dados['nome'].strip()
        if nome:
            r.nome = nome
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>', methods=['DELETE'])
@login_required
def deletar(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'ok': True})


# ── Linhas ────────────────────────────────────────────────────────────────────

@bp_roadmap.route('/<int:roadmap_id>/linhas', methods=['POST'])
@login_required
def criar_linha(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    max_ordem = db.session.query(
        db.func.max(LinhaRoadmap.ordem)).filter_by(id_roadmap=roadmap_id).scalar() or 0
    linha = LinhaRoadmap(
        id_roadmap=roadmap_id,
        nome=nome,
        cor=dados.get('cor', '#1e293b'),
        ordem=max_ordem + 1,
    )
    db.session.add(linha)
    db.session.commit()
    return jsonify({'id': linha.id, 'nome': linha.nome, 'cor': linha.cor}), 201


@bp_roadmap.route('/<int:roadmap_id>/linhas/<int:linha_id>', methods=['PUT'])
@login_required
def atualizar_linha(roadmap_id, linha_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    linha = LinhaRoadmap.query.filter_by(id=linha_id, id_roadmap=roadmap_id).first()
    if not linha:
        return jsonify({'erro': 'Linha não encontrada'}), 404
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados and dados['nome'].strip():
        linha.nome = dados['nome'].strip()
    if 'cor' in dados:
        linha.cor = dados['cor']
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>/linhas/<int:linha_id>', methods=['DELETE'])
@login_required
def deletar_linha(roadmap_id, linha_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    linha = LinhaRoadmap.query.filter_by(id=linha_id, id_roadmap=roadmap_id).first()
    if not linha:
        return jsonify({'erro': 'Linha não encontrada'}), 404
    db.session.delete(linha)
    db.session.commit()
    return jsonify({'ok': True})


# ── Colunas ───────────────────────────────────────────────────────────────────

@bp_roadmap.route('/<int:roadmap_id>/colunas', methods=['POST'])
@login_required
def criar_coluna(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    data_inicio = _parse_date(dados.get('data_inicio'))
    data_fim = _parse_date(dados.get('data_fim'))
    if not nome or not data_inicio or not data_fim:
        return jsonify({'erro': 'Campos obrigatórios: nome, data_inicio, data_fim'}), 400
    max_ordem = db.session.query(
        db.func.max(ColunaRoadmap.ordem)).filter_by(id_roadmap=roadmap_id).scalar() or 0
    coluna = ColunaRoadmap(
        id_roadmap=roadmap_id,
        nome=nome,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ordem=max_ordem + 1,
    )
    db.session.add(coluna)
    db.session.commit()
    return jsonify({
        'id': coluna.id,
        'nome': coluna.nome,
        'data_inicio': str(coluna.data_inicio),
        'data_fim': str(coluna.data_fim),
    }), 201


@bp_roadmap.route('/<int:roadmap_id>/colunas/<int:coluna_id>', methods=['PUT'])
@login_required
def atualizar_coluna(roadmap_id, coluna_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    coluna = ColunaRoadmap.query.filter_by(id=coluna_id, id_roadmap=roadmap_id).first()
    if not coluna:
        return jsonify({'erro': 'Coluna não encontrada'}), 404
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados and dados['nome'].strip():
        coluna.nome = dados['nome'].strip()
    if 'data_inicio' in dados:
        d = _parse_date(dados['data_inicio'])
        if d:
            coluna.data_inicio = d
    if 'data_fim' in dados:
        d = _parse_date(dados['data_fim'])
        if d:
            coluna.data_fim = d
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>/colunas/<int:coluna_id>', methods=['DELETE'])
@login_required
def deletar_coluna(roadmap_id, coluna_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    coluna = ColunaRoadmap.query.filter_by(id=coluna_id, id_roadmap=roadmap_id).first()
    if not coluna:
        return jsonify({'erro': 'Coluna não encontrada'}), 404
    db.session.delete(coluna)
    db.session.commit()
    return jsonify({'ok': True})


# ── Projetos ──────────────────────────────────────────────────────────────────

@bp_roadmap.route('/cartoes/buscar')
@login_required
def buscar_cartoes():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify([])
    cartoes = (CartaoKanban.query
               .join(ColunaKanban, CartaoKanban.id_coluna == ColunaKanban.id)
               .filter(ColunaKanban.id_usuario == get_usuario_ativo().id,
                       CartaoKanban.titulo.ilike(f'%{q}%'))
               .order_by(CartaoKanban.titulo)
               .limit(8).all())
    return jsonify([
        {'id': c.id, 'titulo': c.titulo, 'coluna': c.coluna.nome}
        for c in cartoes
    ])


def _vincular_cartoes(projeto, cartoes_ids):
    if not cartoes_ids:
        projeto.cartoes = []
        return
    cartoes = (CartaoKanban.query
               .join(ColunaKanban, CartaoKanban.id_coluna == ColunaKanban.id)
               .filter(CartaoKanban.id.in_(cartoes_ids),
                       ColunaKanban.id_usuario == get_usuario_ativo().id)
               .all())
    projeto.cartoes = cartoes


@bp_roadmap.route('/<int:roadmap_id>/projetos', methods=['POST'])
@login_required
def criar_projeto(roadmap_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    id_linha = dados.get('id_linha')
    data_inicio = _parse_date(dados.get('data_inicio'))
    data_fim = _parse_date(dados.get('data_fim'))
    if not nome or not id_linha or not data_inicio or not data_fim:
        return jsonify({'erro': 'Campos obrigatórios: nome, id_linha, data_inicio, data_fim'}), 400
    linha = LinhaRoadmap.query.filter_by(id=id_linha, id_roadmap=roadmap_id).first()
    if not linha:
        return jsonify({'erro': 'Linha não encontrada'}), 404
    id_subgrupo = dados.get('id_subgrupo') or None
    if id_subgrupo:
        sub = SubgrupoRoadmap.query.filter_by(id=id_subgrupo, id_linha=id_linha).first()
        id_subgrupo = sub.id if sub else None
    max_ordem = (db.session.query(db.func.max(ProjetoRoadmap.ordem))
                 .filter_by(id_roadmap=roadmap_id, id_linha=id_linha, id_subgrupo=id_subgrupo)
                 .scalar() or 0)
    projeto = ProjetoRoadmap(
        id_roadmap=roadmap_id,
        id_linha=id_linha,
        id_subgrupo=id_subgrupo,
        nome=nome,
        descricao=dados.get('descricao', ''),
        ordem=max_ordem + 1,
        data_inicio=data_inicio,
        data_fim=data_fim,
        cor=dados.get('cor', '#16a34a'),
        status=dados.get('status', 'ativo'),
    )
    db.session.add(projeto)
    db.session.flush()  # gera o id antes de vincular
    _vincular_cartoes(projeto, dados.get('cartoes_ids') or [])
    db.session.commit()
    return jsonify({
        'id': projeto.id,
        'nome': projeto.nome,
        'data_inicio': str(projeto.data_inicio),
        'data_fim': str(projeto.data_fim),
        'cor': projeto.cor,
        'status': projeto.status,
    }), 201


@bp_roadmap.route('/<int:roadmap_id>/projetos/<int:projeto_id>', methods=['GET'])
@login_required
def detalhe_projeto(roadmap_id, projeto_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    projeto = ProjetoRoadmap.query.filter_by(id=projeto_id, id_roadmap=roadmap_id).first()
    if not projeto:
        return jsonify({'erro': 'Projeto não encontrado'}), 404
    return jsonify({
        'id': projeto.id,
        'descricao': projeto.descricao or '',
        'cartoes': [
            {'id': c.id, 'titulo': c.titulo, 'coluna': c.coluna.nome}
            for c in projeto.cartoes
        ],
    })


@bp_roadmap.route('/<int:roadmap_id>/projetos/<int:projeto_id>', methods=['PUT'])
@login_required
def atualizar_projeto(roadmap_id, projeto_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    projeto = ProjetoRoadmap.query.filter_by(id=projeto_id, id_roadmap=roadmap_id).first()
    if not projeto:
        return jsonify({'erro': 'Projeto não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados and dados['nome'].strip():
        projeto.nome = dados['nome'].strip()
    if 'cor' in dados:
        projeto.cor = dados['cor']
    if 'status' in dados:
        projeto.status = dados['status']
    if 'data_inicio' in dados:
        d = _parse_date(dados['data_inicio'])
        if d:
            projeto.data_inicio = d
    if 'data_fim' in dados:
        d = _parse_date(dados['data_fim'])
        if d:
            projeto.data_fim = d
    if 'id_linha' in dados:
        l = LinhaRoadmap.query.filter_by(id=dados['id_linha'], id_roadmap=roadmap_id).first()
        if l:
            projeto.id_linha = dados['id_linha']
            projeto.id_subgrupo = None  # limpa subgrupo ao trocar de linha
    if 'id_subgrupo' in dados:
        sid = dados['id_subgrupo'] or None
        if sid:
            sub = SubgrupoRoadmap.query.filter_by(id=sid, id_linha=projeto.id_linha).first()
            projeto.id_subgrupo = sub.id if sub else None
        else:
            projeto.id_subgrupo = None
    if 'descricao' in dados:
        projeto.descricao = dados['descricao']
    if 'cartoes_ids' in dados:
        _vincular_cartoes(projeto, dados['cartoes_ids'] or [])
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>/projetos/<int:projeto_id>', methods=['DELETE'])
@login_required
def deletar_projeto(roadmap_id, projeto_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    projeto = ProjetoRoadmap.query.filter_by(id=projeto_id, id_roadmap=roadmap_id).first()
    if not projeto:
        return jsonify({'erro': 'Projeto não encontrado'}), 404
    db.session.delete(projeto)
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>/projetos/<int:projeto_id>/reordenar', methods=['PUT'])
@login_required
def reordenar_projeto(roadmap_id, projeto_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    projeto = ProjetoRoadmap.query.filter_by(
        id=projeto_id, id_roadmap=roadmap_id).first()
    if not projeto:
        return jsonify({'erro': 'Projeto não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    swap_com = dados.get('swap_com')
    if not swap_com:
        return jsonify({'erro': 'swap_com é obrigatório'}), 400
    outro = ProjetoRoadmap.query.filter_by(
        id=swap_com, id_roadmap=roadmap_id).first()
    if not outro:
        return jsonify({'erro': 'Projeto alvo não encontrado'}), 404
    projeto.ordem, outro.ordem = outro.ordem, projeto.ordem
    db.session.commit()
    return jsonify({'ok': True})


# ── Subgrupos ─────────────────────────────────────────────────────────────────

def _linha_do_roadmap(roadmap_id, linha_id):
    return LinhaRoadmap.query.filter_by(id=linha_id, id_roadmap=roadmap_id).first()


@bp_roadmap.route('/<int:roadmap_id>/linhas/<int:linha_id>/subgrupos', methods=['POST'])
@login_required
def criar_subgrupo(roadmap_id, linha_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    linha = _linha_do_roadmap(roadmap_id, linha_id)
    if not linha:
        return jsonify({'erro': 'Linha não encontrada'}), 404
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    max_ordem = db.session.query(
        db.func.max(SubgrupoRoadmap.ordem)).filter_by(id_linha=linha_id).scalar() or 0
    sub = SubgrupoRoadmap(id_linha=linha_id, nome=nome, ordem=max_ordem + 1)
    db.session.add(sub)
    db.session.commit()
    return jsonify({'id': sub.id, 'nome': sub.nome}), 201


@bp_roadmap.route('/<int:roadmap_id>/linhas/<int:linha_id>/subgrupos/<int:sub_id>', methods=['PUT'])
@login_required
def atualizar_subgrupo(roadmap_id, linha_id, sub_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    sub = SubgrupoRoadmap.query.filter_by(id=sub_id, id_linha=linha_id).first()
    if not sub:
        return jsonify({'erro': 'Subgrupo não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    if 'nome' in dados and dados['nome'].strip():
        sub.nome = dados['nome'].strip()
    db.session.commit()
    return jsonify({'ok': True})


@bp_roadmap.route('/<int:roadmap_id>/linhas/<int:linha_id>/subgrupos/<int:sub_id>', methods=['DELETE'])
@login_required
def deletar_subgrupo(roadmap_id, linha_id, sub_id):
    r = _roadmap_do_usuario(roadmap_id)
    if not r:
        return jsonify({'erro': 'Não encontrado'}), 404
    sub = SubgrupoRoadmap.query.filter_by(id=sub_id, id_linha=linha_id).first()
    if not sub:
        return jsonify({'erro': 'Subgrupo não encontrado'}), 404
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'ok': True})
