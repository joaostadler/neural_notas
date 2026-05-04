"""
app/routes/main.py - Rotas principais da interface web.
"""

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from models import (
    Caderno, CartaoKanban, CelulaJupyter, ColunaKanban,
    Codigo, Diagrama, HistoricoEtapas, Imagem, Nota, PDF,
    Planilha, TarefaFacil, Topico, db,
)

bp_main = Blueprint('main', __name__)

TIPOS_DOCUMENTO = {
    'pasta':    {'icone': '🗂',  'label': 'Pasta'},
    'nota':     {'icone': '📒', 'label': 'Nota'},
    'caderno':  {'icone': '📔', 'label': 'Caderno'},
    'planilha': {'icone': '📊', 'label': 'Planilha'},
    'diagrama': {'icone': '🔷', 'label': 'Diagrama'},
    'jupyter':  {'icone': '⚗️',  'label': 'Notebook'},
    'tarefa':   {'icone': '🎯', 'label': 'Tarefa'},
    'imagem':   {'icone': '🖼',  'label': 'Imagem'},
    'python':   {'icone': 'PY',  'label': 'Python'},
    'sql':      {'icone': 'SQL', 'label': 'SQL'},
    'biblioteca': {'icone': '📚', 'label': 'Biblioteca'},
}


def _topico_do_usuario(topico_id):
    if not topico_id:
        return None
    return Topico.query.filter_by(id=topico_id, id_usuario=current_user.id).first()


def _eh_container(topico):
    return topico and topico.tipo in ('pasta', 'biblioteca')


def _proxima_ordem(id_pai):
    ultima_ordem = (
        db.session.query(db.func.max(Topico.ordem))
        .filter_by(id_usuario=current_user.id, id_pai=id_pai)
        .scalar()
    )
    return (ultima_ordem or 0) + 1


def _criar_conteudo_inicial(topico, tipo):
    if tipo in ('nota', 'tarefa'):
        db.session.add(Nota(id_topico=topico.id, titulo=topico.nome, conteudo=''))
    elif tipo == 'caderno':
        db.session.add(Caderno(id_topico=topico.id, titulo=topico.nome, conteudo=''))
    elif tipo == 'planilha':
        db.session.add(Planilha(id_topico=topico.id, titulo=topico.nome, dados_json='{"colunas":["A","B","C"],"linhas":[["","",""],["","",""],["","",""]]}'))
    elif tipo == 'jupyter':
        db.session.add(CelulaJupyter(id_topico=topico.id, tipo='markdown', conteudo=f'# {topico.nome}', ordem=1))
    elif tipo == 'diagrama':
        db.session.add(Diagrama(id_topico=topico.id, titulo=topico.nome, dados_json=''))
    elif tipo == 'python':
        db.session.add(Codigo(id_topico=topico.id, titulo=topico.nome, conteudo='# Python\n'))
    elif tipo == 'sql':
        db.session.add(Codigo(id_topico=topico.id, titulo=topico.nome, conteudo='-- SQL\n'))


def _caminho_static_seguro(caminho_relativo):
    """Converte um caminho salvo no banco em arquivo dentro de app/static."""
    if not caminho_relativo:
        return None

    static_root = Path(current_app.static_folder).resolve()
    arquivo = (static_root / caminho_relativo).resolve()
    try:
        arquivo.relative_to(static_root)
    except ValueError:
        current_app.logger.warning('Ignorando caminho fora da pasta static: %s', caminho_relativo)
        return None
    return arquivo


def _coletar_arquivos_do_topico(topico):
    arquivos = []

    if topico.pdfs and topico.pdfs.caminho:
        arquivos.append(topico.pdfs.caminho)
    if topico.imagens and topico.imagens.caminho:
        arquivos.append(topico.imagens.caminho)

    for subtopico in topico.subtopicos:
        arquivos.extend(_coletar_arquivos_do_topico(subtopico))

    return arquivos


def _remover_arquivos_static(caminhos_relativos):
    uploads_root = Path(current_app.config['UPLOAD_FOLDER']).resolve()

    for caminho_relativo in caminhos_relativos:
        arquivo = _caminho_static_seguro(caminho_relativo)
        if not arquivo or not arquivo.is_file():
            continue

        try:
            arquivo.unlink()
            pasta = arquivo.parent
            while pasta != uploads_root and uploads_root in pasta.parents:
                try:
                    pasta.rmdir()
                except OSError:
                    break
                pasta = pasta.parent
        except OSError as exc:
            current_app.logger.warning('Nao foi possivel remover arquivo %s: %s', arquivo, exc)


@bp_main.route('/')
def index():
    """Pagina inicial."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@bp_main.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal do usuario."""
    topicos = (
        Topico.query.filter_by(id_usuario=current_user.id, id_pai=None)
        .order_by(Topico.ordem, Topico.nome)
        .all()
    )

    tarefas_recentes = (
        TarefaFacil.query.filter_by(id_usuario=current_user.id, concluida=False)
        .order_by(desc(TarefaFacil.data_tarefa))
        .limit(5)
        .all()
    )

    return render_template(
        'main/dashboard.html',
        topicos=topicos,
        tipos_documento=TIPOS_DOCUMENTO,
        tarefas_recentes=tarefas_recentes,
    )


@bp_main.route('/topicos/criar', methods=['POST'])
@login_required
def criar_topico():
    """Cria pastas e documentos dentro da arvore lateral."""
    nome = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo', '').strip()
    id_pai_raw = request.form.get('id_pai', '').strip()
    id_pai = int(id_pai_raw) if id_pai_raw.isdigit() else None

    if not nome:
        flash('Informe um nome para criar o item.', 'erro')
        return redirect(url_for('main.dashboard'))

    if tipo not in TIPOS_DOCUMENTO:
        flash('Tipo de item invalido.', 'erro')
        return redirect(url_for('main.dashboard'))

    if id_pai and not _eh_container(_topico_do_usuario(id_pai)):
        flash('A pasta de destino nao foi encontrada.', 'erro')
        return redirect(url_for('main.dashboard'))

    topico = Topico(
        id_usuario=current_user.id,
        id_pai=id_pai,
        nome=nome,
        tipo=tipo,
        icone=TIPOS_DOCUMENTO[tipo]['icone'],
        ordem=_proxima_ordem(id_pai),
    )
    db.session.add(topico)
    db.session.flush()  # Garante que o topico tem um ID antes de criar o conteúdo
    _criar_conteudo_inicial(topico, tipo)
    db.session.commit()

    flash(f'{TIPOS_DOCUMENTO[tipo]["label"]} criado com sucesso.', 'sucesso')
    return redirect(url_for('main.dashboard'))


@bp_main.route('/pdf/importar', methods=['POST'])
@login_required
def importar_pdf():
    """Importa um PDF como item da arvore lateral."""
    arquivo = request.files.get('arquivo_pdf')
    id_pai_raw = request.form.get('id_pai_pdf', '').strip()
    id_pai = int(id_pai_raw) if id_pai_raw.isdigit() else None

    if id_pai and not _eh_container(_topico_do_usuario(id_pai)):
        flash('A pasta de destino nao foi encontrada.', 'erro')
        return redirect(url_for('main.dashboard'))

    if not arquivo or not arquivo.filename:
        flash('Escolha um arquivo PDF para importar.', 'erro')
        return redirect(url_for('main.dashboard'))

    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro.lower().endswith('.pdf'):
        flash('Somente arquivos PDF podem ser importados aqui.', 'erro')
        return redirect(url_for('main.dashboard'))

    pasta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], 'pdfs', str(current_user.id))
    os.makedirs(pasta_pdf, exist_ok=True)
    nome_arquivo = f'{uuid4().hex}_{nome_seguro}'
    caminho_absoluto = os.path.join(pasta_pdf, nome_arquivo)
    arquivo.save(caminho_absoluto)

    titulo = os.path.splitext(nome_seguro)[0] or 'PDF importado'
    caminho_relativo = os.path.relpath(caminho_absoluto, current_app.static_folder).replace('\\', '/')
    topico = Topico(
        id_usuario=current_user.id,
        id_pai=id_pai,
        nome=titulo,
        tipo='pdf',
        icone='PDF',
        ordem=_proxima_ordem(id_pai),
    )
    db.session.add(topico)
    db.session.flush()  # Garante que o topico tem um ID antes de criar o PDF
    db.session.add(PDF(id_topico=topico.id, titulo=titulo, caminho=caminho_relativo))
    db.session.commit()

    flash('PDF importado com sucesso.', 'sucesso')
    return redirect(url_for('main.dashboard'))


# ── Visualização e edição de conteúdo ─────────────────────────────────────────

_TMPL_CONTEUDO = {
    'nota':     'content/_nota.html',
    'tarefa':   'content/_nota.html',
    'caderno':  'content/_caderno.html',
    'pdf':      'content/_pdf.html',
    'imagem':   'content/_imagem.html',
    'planilha': 'content/_planilha.html',
    'jupyter':  'content/_jupyter.html',
    'diagrama': 'content/_diagrama.html',
    'python':     'content/_python.html',
    'sql':        'content/_sql.html',
    'biblioteca': 'content/_biblioteca.html',
}


@bp_main.route('/topico/<int:id>')
@login_required
def ver_topico(id):
    topico = _topico_do_usuario(id)
    if not topico:
        return '', 404

    tmpl = _TMPL_CONTEUDO.get(topico.tipo)
    if not tmpl:
        return '', 404

    if topico.tipo in ('nota', 'tarefa'):
        conteudo = topico.notas
    elif topico.tipo == 'caderno':
        conteudo = topico.cadernos
    elif topico.tipo == 'pdf':
        conteudo = topico.pdfs
    elif topico.tipo == 'imagem':
        conteudo = topico.imagens
    elif topico.tipo == 'planilha':
        conteudo = topico.planilhas
    elif topico.tipo == 'diagrama':
        conteudo = topico.diagramas
    elif topico.tipo == 'jupyter':
        conteudo = sorted(topico.celulas_jupyter, key=lambda c: c.ordem)
    elif topico.tipo in ('python', 'sql'):
        conteudo = topico.codigos
    elif topico.tipo == 'biblioteca':
        conteudo = (
            Topico.query
            .filter_by(id_usuario=current_user.id, id_pai=topico.id, tipo='pdf')
            .order_by(Topico.ordem, Topico.nome)
            .all()
        )
    else:
        conteudo = None

    return render_template(tmpl, topico=topico, conteudo=conteudo)


@bp_main.route('/topicos/<int:id>/renomear', methods=['POST'])
@login_required
def renomear_topico(id):
    topico = _topico_do_usuario(id)
    if not topico:
        return jsonify({'erro': 'Não encontrado'}), 404
    dados = request.get_json(silent=True) or {}
    nome = dados.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome inválido'}), 400
    topico.nome = nome
    db.session.commit()
    return jsonify({'ok': True})


@bp_main.route('/topicos/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_topico(id):
    topico = _topico_do_usuario(id)
    if not topico:
        return jsonify({'erro': 'Não encontrado'}), 404
    arquivos_para_remover = _coletar_arquivos_do_topico(topico)
    try:
        db.session.delete(topico)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

    _remover_arquivos_static(arquivos_para_remover)
    return jsonify({'ok': True})


@bp_main.route('/topicos/<int:id>/mover', methods=['POST'])
@login_required
def mover_topico(id):
    topico = _topico_do_usuario(id)
    if not topico:
        return jsonify({'erro': 'Não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    novo_pai_raw = dados.get('id_pai')
    novo_pai_id = int(novo_pai_raw) if novo_pai_raw is not None else None

    if novo_pai_id is not None:
        pai = _topico_do_usuario(novo_pai_id)
        if not _eh_container(pai):
            return jsonify({'erro': 'Destino deve ser uma pasta ou biblioteca'}), 400
        if novo_pai_id == topico.id:
            return jsonify({'erro': 'Não é possível mover para si mesmo'}), 400
        if _eh_descendente(topico.id, novo_pai_id):
            return jsonify({'erro': 'Não é possível mover para uma subpasta'}), 400

    topico.id_pai = novo_pai_id
    topico.ordem = _proxima_ordem(novo_pai_id)
    db.session.commit()
    return jsonify({'ok': True})


def _eh_descendente(topico_id, candidato_pai_id):
    """Retorna True se candidato_pai_id está na subárvore de topico_id (detecta ciclo)."""
    current_id = candidato_pai_id
    visitados = set()
    while current_id:
        if current_id == topico_id:
            return True
        if current_id in visitados:
            break
        visitados.add(current_id)
        current_id = db.session.query(Topico.id_pai).filter_by(
            id=current_id, id_usuario=current_user.id
        ).scalar()
    return False


@bp_main.route('/topico/<int:id>/salvar', methods=['POST'])
@login_required
def salvar_topico(id):
    topico = _topico_do_usuario(id)
    if not topico:
        return jsonify({'erro': 'não encontrado'}), 404

    dados = request.get_json(silent=True) or {}
    try:
        if topico.tipo in ('nota', 'tarefa') and topico.notas:
            topico.notas.conteudo = dados.get('conteudo', topico.notas.conteudo)
        elif topico.tipo == 'caderno' and topico.cadernos:
            topico.cadernos.conteudo = dados.get('conteudo', topico.cadernos.conteudo)
        elif topico.tipo == 'diagrama' and topico.diagramas:
            topico.diagramas.dados_json = dados.get('conteudo', topico.diagramas.dados_json)
        elif topico.tipo == 'planilha' and topico.planilhas:
            topico.planilhas.dados_json = dados.get('dados_json', topico.planilhas.dados_json)
        elif topico.tipo in ('python', 'sql') and topico.codigos:
            topico.codigos.conteudo = dados.get('conteudo', topico.codigos.conteudo)
        elif topico.tipo == 'pdf' and topico.pdfs:
            if 'percentual' in dados:
                topico.pdfs.percentual_lido = max(0, min(100, int(dados['percentual'])))
            if 'anotacoes' in dados:
                topico.pdfs.anotacoes = dados['anotacoes']
        elif topico.tipo == 'jupyter':
            for cel_data in dados.get('celulas', []):
                cel = CelulaJupyter.query.filter_by(
                    id=cel_data.get('id'), id_topico=topico.id
                ).first()
                if cel:
                    cel.conteudo = cel_data.get('conteudo', cel.conteudo)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@bp_main.route('/topicos/buscar')
@login_required
def buscar_topicos():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    topicos = (
        Topico.query
        .filter(
            Topico.id_usuario == current_user.id,
            Topico.tipo != 'pasta',
            Topico.nome.ilike(f'%{q}%')
        )
        .order_by(Topico.nome)
        .limit(8)
        .all()
    )
    return jsonify([{'id': t.id, 'nome': t.nome, 'tipo': t.tipo} for t in topicos])


@bp_main.route('/resumo')
@login_required
def resumo():
    """Painel de resumo — dados para a aba de dashboard."""
    hoje = date.today()

    # ── Filtro de período ─────────────────────────────────────────────────
    de_str  = request.args.get('de',  '').strip()
    ate_str = request.args.get('ate', '').strip()
    try:
        de = date.fromisoformat(de_str) if de_str else hoje
    except ValueError:
        de = hoje
    try:
        ate = date.fromisoformat(ate_str) if ate_str else hoje
    except ValueError:
        ate = hoje
    if de > ate:
        de, ate = ate, de

    de_dt  = datetime(de.year,  de.month,  de.day,  0,  0,  0)
    ate_dt = datetime(ate.year, ate.month, ate.day, 23, 59, 59)

    # ── Kanban ────────────────────────────────────────────────────────────
    colunas = (
        ColunaKanban.query
        .filter_by(id_usuario=current_user.id)
        .order_by(ColunaKanban.ordem)
        .all()
    )
    kanban_cols_raw = [
        {'nome': c.nome, 'cor': c.cor, 'total': len(c.cartoes)}
        for c in colunas
    ]
    max_cartoes = max((c['total'] for c in kanban_cols_raw), default=1) or 1
    n = len(kanban_cols_raw)
    kanban_cols = [
        {**c, 'pct': round(c['total'] / max_cartoes * 100), 'is_last': i == n - 1}
        for i, c in enumerate(kanban_cols_raw)
    ]
    total_cartoes = sum(c['total'] for c in kanban_cols)

    def _conta_prio(p):
        return (
            CartaoKanban.query
            .join(ColunaKanban)
            .filter(ColunaKanban.id_usuario == current_user.id,
                    CartaoKanban.prioridade == p)
            .count()
        )

    prio = {
        'alta':  _conta_prio('alta'),
        'media': _conta_prio('media'),
        'baixa': _conta_prio('baixa'),
    }
    prio_total = sum(prio.values()) or 1

    # ── Tarefas no período ────────────────────────────────────────────────
    tarefas_periodo = (
        TarefaFacil.query
        .filter(
            TarefaFacil.id_usuario == current_user.id,
            TarefaFacil.data_tarefa >= de,
            TarefaFacil.data_tarefa <= ate,
        )
        .order_by(TarefaFacil.concluida, TarefaFacil.criado_em)
        .all()
    )
    concluidas_periodo = sum(1 for t in tarefas_periodo if t.concluida)
    atrasadas = (
        TarefaFacil.query
        .filter(
            TarefaFacil.id_usuario == current_user.id,
            TarefaFacil.data_tarefa < hoje,
            TarefaFacil.concluida.is_(False),
        )
        .count()
    )

    # ── Atividade no período ──────────────────────────────────────────────
    hist_rows = (
        db.session.query(
            HistoricoEtapas.nome_coluna,
            HistoricoEtapas.data_entrada,
            CartaoKanban.titulo.label('cartao_titulo'),
        )
        .join(CartaoKanban, HistoricoEtapas.id_cartao == CartaoKanban.id)
        .join(ColunaKanban, CartaoKanban.id_coluna == ColunaKanban.id)
        .filter(
            ColunaKanban.id_usuario == current_user.id,
            HistoricoEtapas.data_entrada >= de_dt,
            HistoricoEtapas.data_entrada <= ate_dt,
        )
        .order_by(desc(HistoricoEtapas.data_entrada))
        .limit(10)
        .all()
    )
    historico = [
        {'titulo': r.cartao_titulo, 'coluna': r.nome_coluna, 'data': r.data_entrada}
        for r in hist_rows
    ]

    # ── Documentos por tipo ───────────────────────────────────────────────
    _TIPO_INFO = {
        'nota':     ('📒', 'Notas',      '#2563eb'),
        'caderno':  ('📔', 'Cadernos',   '#7c3aed'),
        'planilha': ('📊', 'Planilhas',  '#16a34a'),
        'diagrama': ('🔷', 'Diagramas',  '#0891b2'),
        'jupyter':  ('⚗️',  'Notebooks',  '#d97706'),
        'tarefa':   ('🎯', 'Tarefas',    '#16a34a'),
        'imagem':   ('🖼',  'Imagens',    '#7c3aed'),
        'pdf':      ('📄', 'PDFs',       '#ef4444'),
        'python':   ('PY', 'Python',     '#3776ab'),
        'sql':      ('SQL','SQL',        '#e38c00'),
    }
    contagem: dict[str, int] = {}
    for t in Topico.query.filter_by(id_usuario=current_user.id).all():
        if t.tipo != 'pasta':
            contagem[t.tipo] = contagem.get(t.tipo, 0) + 1

    docs_info = [
        {
            'tipo':   tipo,
            'count':  count,
            'icone':  _TIPO_INFO.get(tipo, ('📄', tipo, '#64748b'))[0],
            'label':  _TIPO_INFO.get(tipo, ('📄', tipo, '#64748b'))[1],
            'cor':    _TIPO_INFO.get(tipo, ('📄', tipo, '#64748b'))[2],
        }
        for tipo, count in sorted(contagem.items(), key=lambda x: x[1], reverse=True)
    ]
    total_docs = sum(contagem.values())

    return render_template(
        'content/_resumo.html',
        kanban_cols=kanban_cols,
        total_cartoes=total_cartoes,
        prio=prio,
        prio_total=prio_total,
        tarefas_periodo=tarefas_periodo,
        concluidas_periodo=concluidas_periodo,
        atrasadas=atrasadas,
        historico=historico,
        docs_info=docs_info,
        total_docs=total_docs,
        hoje=hoje,
        de=de,
        ate=ate,
    )
