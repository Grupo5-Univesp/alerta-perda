import os
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func, inspect, text

from models import db, InspecaoSetor, Lote, MovimentacaoEstoque, Produto, RegistroPerda, Usuario
from weather import get_weather, get_weather_config


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('APP_SECRET_KEY', 'desenvolvimento-local-altere-em-producao')

# O Render fornece URLs PostgreSQL. O dialeto explicita o driver psycopg 3
# usado na publicação, enquanto o ambiente local continua usando SQLite.
database_url = os.getenv('DATABASE_URL', 'sqlite:///alerta_perda.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
db.init_app(app)


def migrate_local_database():
    """Mantém o banco SQLite existente compatível com as novas funcionalidades."""
    schema = inspect(db.engine)
    columns = {column['name'] for column in schema.get_columns('registros_perda')}
    if 'lote_id' not in columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE registros_perda ADD COLUMN lote_id INTEGER'))

    user_columns = {column['name'] for column in schema.get_columns('usuarios')}
    additions = {
        'perfil': "ALTER TABLE usuarios ADD COLUMN perfil VARCHAR(20) DEFAULT 'operador'",
        'senha_hash': 'ALTER TABLE usuarios ADD COLUMN senha_hash VARCHAR(255)',
        'ativo': 'ALTER TABLE usuarios ADD COLUMN ativo BOOLEAN DEFAULT 1',
    }
    with db.engine.begin() as connection:
        for name, statement in additions.items():
            if name not in user_columns:
                connection.execute(text(statement))


def ensure_admin():
    admin = Usuario.query.filter_by(matricula='ADMIN-001').first()
    if not admin:
        admin = Usuario(
            nome='Administrador do Sistema', matricula='ADMIN-001',
            cargo='Administrador', perfil='administrador', ativo=True,
        )
        admin.definir_senha(os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123'))
        db.session.add(admin)
        db.session.commit()
    demo_profiles = {'DEMO-001': 'operador', 'DEMO-002': 'gerente'}
    updated = False
    for matricula, perfil in demo_profiles.items():
        demo_user = Usuario.query.filter_by(matricula=matricula).first()
        if demo_user:
            if not demo_user.senha_hash:
                demo_user.definir_senha('demo123')
                updated = True
            if demo_user.perfil != perfil:
                demo_user.perfil = perfil
                updated = True
    if updated:
        db.session.commit()


with app.app_context():
    db.create_all()
    migrate_local_database()
    ensure_admin()
    if os.getenv('SEED_INITIAL_CATALOG', '').lower() in {'1', 'true', 'yes'} and not Produto.query.first():
        from seed_demo import seed_video_catalog
        seed_video_catalog()


def current_user():
    user_id = session.get('usuario_id')
    return db.session.get(Usuario, user_id) if user_id else None


@app.context_processor
def inject_current_user():
    return {'usuario_logado': current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash('Faça login para acessar o sistema.', 'warning')
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for('login', next=request.path))
            if user.perfil not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def parse_positive_quantity(value):
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        return None
    return quantity if quantity > 0 else None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(matricula=request.form.get('matricula', '').strip()).first()
        if user and user.ativo and user.validar_senha(request.form.get('senha', '')):
            session.clear()
            session['usuario_id'] = user.id
            flash(f'Bem-vindo(a), {user.nome}.', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Matrícula ou senha inválida.', 'danger')
    return render_template('login.html')


@app.route('/sair', methods=['POST'])
def logout():
    session.clear()
    flash('Sessão encerrada.', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    lotes_ativos = Lote.query.filter(Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
    produtos_sem_lote = Produto.query.filter(~Produto.lotes.any()).order_by(Produto.data_validade.asc()).all()
    lotes_urgentes = [lote for lote in lotes_ativos if lote.dias_para_vencer <= 2]
    categorias_ativas = sorted({lote.produto.categoria for lote in lotes_ativos})
    return render_template(
        'index.html', lotes_ativos=lotes_ativos, produtos_sem_lote=produtos_sem_lote,
        lotes_urgentes=lotes_urgentes, clima=get_weather(categorias_ativas), clima_config=get_weather_config()
    )


@app.route('/produto/novo', methods=['GET', 'POST'])
@roles_required('administrador', 'gerente')
def novo_produto():
    produtos = Produto.query.order_by(Produto.nome.asc()).all()
    lotes = Lote.query.order_by(Lote.data_validade.asc()).all()
    if request.method == 'POST':
        modo_entrada = request.form.get('modo_entrada', 'novo_produto')
        quantidade = parse_positive_quantity(request.form.get('quantidade_entrada'))
        if not quantidade:
            return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Informe uma quantidade maior que zero.')
        if modo_entrada == 'lote_existente':
            lote = db.session.get(Lote, request.form.get('lote_id'))
            if not lote:
                return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Selecione um lote válido.')
            lote.quantidade_inicial += quantidade
            lote.quantidade_atual += quantidade
            lote.produto.quantidade_estoque += quantidade
            db.session.commit()
            flash('Reposição registrada no lote.', 'success')
            return redirect(url_for('lotes_produto', produto_id=lote.produto_id))
        try:
            validade = datetime.strptime(request.form.get('data_validade'), '%Y-%m-%d').date()
            entrada = datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Informe datas válidas.')
        if modo_entrada == 'produto_existente_novo_lote':
            produto = db.session.get(Produto, request.form.get('produto_id'))
            if not produto:
                return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Selecione um produto válido.')
        else:
            produto = Produto(nome=request.form.get('nome', '').strip(), categoria=request.form.get('categoria'),
                              codigo_barras=request.form.get('codigo_barras', '').strip(), data_validade=validade,
                              quantidade_estoque=quantidade, unidade_medida=request.form.get('unidade_medida', 'kg'))
            if not produto.nome or not produto.codigo_barras:
                return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Preencha nome e código do produto.')
            db.session.add(produto)
            db.session.flush()
        codigo_lote = request.form.get('codigo_lote', '').strip()
        if not codigo_lote or Lote.query.filter_by(produto_id=produto.id, codigo_lote=codigo_lote).first():
            db.session.rollback()
            return render_template('novo_produto.html', produtos=produtos, lotes=lotes, erro='Informe um código de lote único para este produto.')
        lote = Lote(produto_id=produto.id, codigo_lote=codigo_lote, data_entrada=entrada, data_validade=validade,
                    quantidade_inicial=quantidade, quantidade_atual=quantidade,
                    local_armazenamento=request.form.get('local_armazenamento', '').strip() or None)
        if modo_entrada == 'produto_existente_novo_lote':
            produto.quantidade_estoque += quantidade
        db.session.add(lote)
        db.session.commit()
        flash('Entrada registrada com sucesso.', 'success')
        return redirect(url_for('lotes_produto', produto_id=produto.id))
    return render_template('novo_produto.html', produtos=produtos, lotes=lotes)


@app.route('/produto/<int:produto_id>/lotes')
@login_required
def lotes_produto(produto_id):
    produto = db.session.get(Produto, produto_id) or abort(404)
    lotes = Lote.query.filter_by(produto_id=produto.id).order_by(Lote.data_validade.asc()).all()
    return render_template('lotes_produto.html', produto=produto, lotes=lotes)


@app.route('/produto/<int:produto_id>/lotes/novo', methods=['GET', 'POST'])
@roles_required('administrador', 'gerente')
def novo_lote(produto_id):
    produto = db.session.get(Produto, produto_id) or abort(404)
    if request.method == 'POST':
        codigo_lote = request.form.get('codigo_lote', '').strip()
        quantidade = parse_positive_quantity(request.form.get('quantidade'))
        if not codigo_lote or not quantidade or Lote.query.filter_by(produto_id=produto.id, codigo_lote=codigo_lote).first():
            return render_template('novo_lote.html', produto=produto, erro='Informe um código de lote único e quantidade maior que zero.')
        try:
            entrada = datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date()
            validade = datetime.strptime(request.form.get('data_validade'), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return render_template('novo_lote.html', produto=produto, erro='Informe datas válidas.')
        lote = Lote(produto_id=produto.id, codigo_lote=codigo_lote, data_entrada=entrada, data_validade=validade,
                    quantidade_inicial=quantidade, quantidade_atual=quantidade,
                    local_armazenamento=request.form.get('local_armazenamento', '').strip() or None)
        produto.quantidade_estoque += quantidade
        db.session.add(lote)
        db.session.commit()
        flash('Novo lote cadastrado.', 'success')
        return redirect(url_for('lotes_produto', produto_id=produto.id))
    return render_template('novo_lote.html', produto=produto)


@app.route('/produto/<int:produto_id>/baixa', methods=['GET', 'POST'])
@login_required
def registrar_baixa(produto_id):
    produto = db.session.get(Produto, produto_id) or abort(404)
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome.asc()).all()
    lotes = Lote.query.filter(Lote.produto_id == produto.id, Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
    if request.method == 'POST':
        quantidade = parse_positive_quantity(request.form.get('quantidade_perdida'))
        lote = db.session.get(Lote, request.form.get('lote_id'))
        if not quantidade or not lote or lote.produto_id != produto.id or quantidade > lote.quantidade_atual:
            return render_template('registrar_baixa.html', produto=produto, usuarios=usuarios, lotes=lotes,
                                   erro='Selecione um lote válido e informe uma quantidade dentro do saldo disponível.')
        registro = RegistroPerda(produto_id=produto.id, lote_id=lote.id, usuario_id=current_user().id,
                                 quantidade_perdida=quantidade, motivo=request.form.get('motivo'),
                                 observacao=request.form.get('observacao', '').strip())
        lote.quantidade_atual -= quantidade
        produto.quantidade_estoque = max(0, produto.quantidade_estoque - quantidade)
        db.session.add(registro)
        db.session.commit()
        flash('Baixa registrada e saldo atualizado.', 'success')
        return redirect(url_for('historico_perdas'))
    return render_template('registrar_baixa.html', produto=produto, usuarios=usuarios, lotes=lotes)


@app.route('/produto/<int:produto_id>/movimentacao', methods=['GET', 'POST'])
@login_required
def movimentacao(produto_id):
    produto = db.session.get(Produto, produto_id) or abort(404)
    lotes = Lote.query.filter(Lote.produto_id == produto.id, Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
    if request.method == 'POST':
        lote = db.session.get(Lote, request.form.get('lote_id'))
        quantidade = parse_positive_quantity(request.form.get('quantidade'))
        tipo = request.form.get('tipo')
        if not lote or lote.produto_id != produto.id or not quantidade or quantidade > lote.quantidade_atual:
            return render_template('movimentacao.html', produto=produto, lotes=lotes, erro='Selecione um lote e uma quantidade dentro do saldo disponível.')
        origem = lote.local_armazenamento
        destino = request.form.get('local_destino', '').strip() or None
        if tipo == 'saida_venda':
            lote.quantidade_atual -= quantidade
            produto.quantidade_estoque = max(0, produto.quantidade_estoque - quantidade)
        elif tipo == 'remanejamento':
            if not destino:
                return render_template('movimentacao.html', produto=produto, lotes=lotes, erro='Informe o local de destino do remanejamento.')
            if quantidade == lote.quantidade_atual:
                lote.local_armazenamento = destino
            else:
                lote.quantidade_atual -= quantidade
                novo_codigo = f'{lote.codigo_lote}-R{MovimentacaoEstoque.query.count() + 1}'
                novo_lote = Lote(produto_id=produto.id, codigo_lote=novo_codigo, data_entrada=lote.data_entrada,
                                 data_validade=lote.data_validade, quantidade_inicial=quantidade,
                                 quantidade_atual=quantidade, local_armazenamento=destino)
                db.session.add(novo_lote)
        else:
            return render_template('movimentacao.html', produto=produto, lotes=lotes, erro='Selecione um tipo de movimentação.')
        db.session.add(MovimentacaoEstoque(produto_id=produto.id, lote_id=lote.id, usuario_id=current_user().id,
                                            tipo=tipo, quantidade=quantidade, local_origem=origem,
                                            local_destino=destino, observacao=request.form.get('observacao', '').strip()))
        db.session.commit()
        flash('Movimentação registrada.', 'success')
        return redirect(url_for('lotes_produto', produto_id=produto.id))
    return render_template('movimentacao.html', produto=produto, lotes=lotes)


@app.route('/historico-perdas')
@login_required
def historico_perdas():
    perdas = RegistroPerda.query.order_by(RegistroPerda.data_registro.desc()).all()
    return render_template('historico_perdas.html', perdas=perdas, total_descartes=sum(p.quantidade_perdida for p in perdas))


@app.route('/indicadores')
@roles_required('administrador', 'gerente')
def indicadores():
    total_perdas = db.session.query(func.coalesce(func.sum(RegistroPerda.quantidade_perdida), 0)).scalar()
    por_categoria = (db.session.query(Produto.categoria, func.sum(RegistroPerda.quantidade_perdida))
                     .join(RegistroPerda).group_by(Produto.categoria).order_by(func.sum(RegistroPerda.quantidade_perdida).desc()).all())
    por_motivo = (db.session.query(RegistroPerda.motivo, func.sum(RegistroPerda.quantidade_perdida))
                  .group_by(RegistroPerda.motivo).order_by(func.sum(RegistroPerda.quantidade_perdida).desc()).all())
    total_movimentacoes = MovimentacaoEstoque.query.count()
    return render_template('indicadores.html', total_perdas=total_perdas, por_categoria=por_categoria,
                           por_motivo=por_motivo, total_movimentacoes=total_movimentacoes)


@app.route('/usuarios', methods=['GET', 'POST'])
@roles_required('administrador')
def usuarios():
    if request.method == 'POST':
        user = Usuario(nome=request.form.get('nome', '').strip(), matricula=request.form.get('matricula', '').strip(),
                       cargo=request.form.get('cargo'), perfil=request.form.get('perfil', 'operador'), ativo=True)
        senha = request.form.get('senha', '')
        if not user.nome or not user.matricula or len(senha) < 6 or Usuario.query.filter_by(matricula=user.matricula).first():
            flash('Preencha os dados, use senha de ao menos 6 caracteres e uma matrícula única.', 'danger')
        else:
            user.definir_senha(senha)
            db.session.add(user)
            db.session.commit()
            flash('Usuário cadastrado.', 'success')
    return render_template('usuarios.html', usuarios=Usuario.query.order_by(Usuario.nome.asc()).all())


@app.route('/inspecoes')
@login_required
def inspecoes():
    return render_template('inspecoes.html', inspecoes=InspecaoSetor.query.order_by(InspecaoSetor.data_inspecao.desc()).all())


@app.route('/inspecoes/nova', methods=['GET', 'POST'])
@login_required
def nova_inspecao():
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome.asc()).all()
    if request.method == 'POST':
        try:
            temperatura = float(request.form.get('temperatura_aferida')) if request.form.get('temperatura_aferida') else None
        except ValueError:
            flash('Informe uma temperatura válida.', 'danger')
            return render_template('nova_inspecao.html', usuarios=usuarios)
        inspecao = InspecaoSetor(fiscal_id=current_user().id, setor=request.form.get('setor'), temperatura_aferida=temperatura,
                                 status_conformidade=request.form.get('status_conformidade'), observacao=request.form.get('observacao', '').strip())
        db.session.add(inspecao)
        db.session.commit()
        flash('Inspeção registrada.', 'success')
        return redirect(url_for('inspecoes'))
    return render_template('nova_inspecao.html', usuarios=usuarios)


@app.route('/api/produtos/alertas')
@login_required
def api_alertas():
    lotes = Lote.query.filter(Lote.quantidade_atual > 0).all()
    dados = [{'id': l.id, 'produto': l.produto.nome, 'categoria': l.produto.categoria, 'lote': l.codigo_lote,
              'validade': l.data_validade.isoformat(), 'dias_restantes': l.dias_para_vencer, 'alerta': l.status_alerta}
             for l in lotes if l.dias_para_vencer <= 2]
    return jsonify({'total_criticos': len(dados), 'lotes': dados})


@app.route('/api/clima')
@login_required
def api_clima():
    clima = get_weather()
    if clima is None:
        return jsonify({'erro': 'Não foi possível consultar a previsão do tempo agora.'}), 503
    return jsonify(clima)


@app.errorhandler(403)
def forbidden(_error):
    return render_template('erro.html', titulo='Acesso não autorizado', mensagem='Seu perfil não possui permissão para esta ação.'), 403


if __name__ == '__main__':
    app.run(debug=True)
