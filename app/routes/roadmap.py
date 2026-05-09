"""app/routes/roadmap.py — Rotas do Roadmap."""

from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import ColunaRoadmap, LinhaRoadmap, ProjetoRoadmap, Roadmap, SubgrupoRoadmap, db

bp_roadmap = Blueprint('roadmap', __name__, url_prefix='/roadmap')


def _roadmap_do_usuario(roadmap_id):
    return Roadmap.query.filter_by(id=roadmap_id, id_usuario=current_user.id).first()


def _parse_date(valor):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


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
            'left_pct': left, 'width_pct': width,
        }

    if not colunas:
        linhas_data = []
        for l in linhas:
            subs = sorted(l.subgrupos, key=lambda s: s.ordem)
            linhas_data.append({
                'id': l.id, 'nome': l.nome, 'cor': l.cor,
                'projetos': [],
                'subgrupos': [{'id': s.id, 'nome': s.nome, 'projetos': []} for s in subs],
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
        # Projetos sem subgrupo (diretos na linha)
        diretos = [calcular(p) for p in sorted(
            (p for p in l.projetos if p.id_subgrupo is None),
            key=lambda x: x.data_inicio,
        )]
        # Projetos por subgrupo
        subgrupos_data = []
        for s in subs:
            ps = [calcular(p) for p in sorted(s.projetos, key=lambda x: x.data_inicio)]
            subgrupos_data.append({'id': s.id, 'nome': s.nome, 'projetos': ps})

        linhas_data.append({
            'id': l.id, 'nome': l.nome, 'cor': l.cor,
            'projetos': diretos,
            'subgrupos': subgrupos_data,
        })

    return colunas_pos, linhas_data, tem_subgrupos


# ── Roadmaps ──────────────────────────────────────────────────────────────────

@bp_roadmap.route('')
@login_required
def lista():
    roadmaps = (Roadmap.query
                .filter_by(id_usuario=current_user.id)
                .order_by(Roadmap.criado_em.desc())
                .all())
    if roadmaps:
        return redirect(url_for('roadmap.ver', roadmap_id=roadmaps[0].id))
    return render_template('roadmap/lista.html', roadmaps=roadmaps)


@bp_roadmap.route('', methods=['POST'])
@login_required
def criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    r = Roadmap(id_usuario=current_user.id, nome=nome)
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
                      .filter_by(id_usuario=current_user.id)
                      .order_by(Roadmap.nome)
                      .all())
    colunas_pos, linhas_data, tem_subgrupos = _posicoes(r)
    subgrupos_map = {
        str(l['id']): l['subgrupos']
        for l in linhas_data
    }
    if tem_subgrupos:
        total_rows = sum(
            max(len(l['subgrupos']) + (1 if l['projetos'] else 0), 1)
            for l in linhas_data
        )
    else:
        total_rows = len(linhas_data)
    return render_template('roadmap/roadmap.html',
                           roadmap=r,
                           todos_roadmaps=todos_roadmaps,
                           colunas_pos=colunas_pos,
                           linhas_data=linhas_data,
                           tem_subgrupos=tem_subgrupos,
                           subgrupos_map=subgrupos_map,
                           total_rows=total_rows)


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
    projeto = ProjetoRoadmap(
        id_roadmap=roadmap_id,
        id_linha=id_linha,
        id_subgrupo=id_subgrupo,
        nome=nome,
        data_inicio=data_inicio,
        data_fim=data_fim,
        cor=dados.get('cor', '#16a34a'),
        status=dados.get('status', 'ativo'),
    )
    db.session.add(projeto)
    db.session.commit()
    return jsonify({
        'id': projeto.id,
        'nome': projeto.nome,
        'data_inicio': str(projeto.data_inicio),
        'data_fim': str(projeto.data_fim),
        'cor': projeto.cor,
        'status': projeto.status,
    }), 201


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
