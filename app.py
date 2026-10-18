import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify
from sqlalchemy import inspect, text
from models import db, Produto, RegistroPerda, Usuario, InspecaoSetor, Lote
from weather import get_weather, get_weather_config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-desenvolvimento-pi'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alerta_perda.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    schema = inspect(db.engine)
    existing_columns = {column['name'] for column in schema.get_columns('registros_perda')}
    if 'lote_id' not in existing_columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE registros_perda ADD COLUMN lote_id INTEGER'))

# --- Rotas Principais de Produtos ---

@app.route('/')
def index():
    lotes_ativos = Lote.query.filter(
        Lote.quantidade_atual > 0
    ).order_by(Lote.data_validade.asc()).all()
    produtos_sem_lote = Produto.query.filter(
        ~Produto.lotes.any()
    ).order_by(Produto.data_validade.asc()).all()
    lotes_urgentes = [lote for lote in lotes_ativos if lote.dias_para_vencer <= 2]
    return render_template(
        'index.html', lotes_ativos=lotes_ativos, produtos_sem_lote=produtos_sem_lote,
        lotes_urgentes=lotes_urgentes, clima=get_weather(), clima_config=get_weather_config()
    )

@app.route('/produto/novo', methods=['GET', 'POST'])
def novo_produto():
    if request.method == 'POST':
        modo_entrada = request.form.get('modo_entrada', 'novo_produto')
        quantidade = float(request.form.get('quantidade_entrada', 0))

        if modo_entrada == 'lote_existente':
            lote = Lote.query.get_or_404(request.form.get('lote_id'))
            lote.quantidade_inicial += quantidade
            lote.quantidade_atual += quantidade
            lote.produto.quantidade_estoque += quantidade
            db.session.commit()
            return redirect(url_for('lotes_produto', produto_id=lote.produto_id))

        if modo_entrada == 'produto_existente_novo_lote':
            produto = Produto.query.get_or_404(request.form.get('produto_id'))
        else:
            data_validade = datetime.strptime(request.form.get('data_validade'), '%Y-%m-%d').date()
            produto = Produto(
                nome=request.form.get('nome'),
                categoria=request.form.get('categoria'),
                codigo_barras=request.form.get('codigo_barras'),
                data_validade=data_validade,
                quantidade_estoque=quantidade,
                unidade_medida=request.form.get('unidade_medida', 'kg')
            )
            db.session.add(produto)
            db.session.flush()

        codigo_lote = request.form.get('codigo_lote', '').strip()
        existing_lote = Lote.query.filter_by(produto_id=produto.id, codigo_lote=codigo_lote).first()
        if existing_lote:
            produtos = Produto.query.order_by(Produto.nome.asc()).all()
            lotes = Lote.query.order_by(Lote.data_validade.asc()).all()
            return render_template(
                'novo_produto.html', produtos=produtos, lotes=lotes,
                erro='Já existe um lote com este código para o produto selecionado.'
            )

        lote = Lote(
            produto_id=produto.id,
            codigo_lote=codigo_lote,
            data_entrada=datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date(),
            data_validade=datetime.strptime(request.form.get('data_validade'), '%Y-%m-%d').date(),
            quantidade_inicial=quantidade,
            quantidade_atual=quantidade,
            local_armazenamento=request.form.get('local_armazenamento', '').strip() or None,
        )
        if modo_entrada == 'produto_existente_novo_lote':
            produto.quantidade_estoque += quantidade
        db.session.add(lote)
        db.session.commit()
        return redirect(url_for('lotes_produto', produto_id=produto.id))

    produtos = Produto.query.order_by(Produto.nome.asc()).all()
    lotes = Lote.query.order_by(Lote.data_validade.asc()).all()
    return render_template('novo_produto.html', produtos=produtos, lotes=lotes)


@app.route('/produto/<int:produto_id>/lotes')
def lotes_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    lotes = Lote.query.filter_by(produto_id=produto.id).order_by(Lote.data_validade.asc()).all()
    return render_template('lotes_produto.html', produto=produto, lotes=lotes)


@app.route('/produto/<int:produto_id>/lotes/novo', methods=['GET', 'POST'])
def novo_lote(produto_id):
    produto = Produto.query.get_or_404(produto_id)

    if request.method == 'POST':
        codigo_lote = request.form.get('codigo_lote', '').strip()
        existing_lote = Lote.query.filter_by(produto_id=produto.id, codigo_lote=codigo_lote).first()
        if existing_lote:
            return render_template(
                'novo_lote.html', produto=produto,
                erro='Já existe um lote com este código para este produto.'
            )

        quantidade = float(request.form.get('quantidade', 0))
        lote = Lote(
            produto_id=produto.id,
            codigo_lote=codigo_lote,
            data_entrada=datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date(),
            data_validade=datetime.strptime(request.form.get('data_validade'), '%Y-%m-%d').date(),
            quantidade_inicial=quantidade,
            quantidade_atual=quantidade,
            local_armazenamento=request.form.get('local_armazenamento', '').strip() or None,
        )
        produto.quantidade_estoque += quantidade
        db.session.add(lote)
        db.session.commit()
        return redirect(url_for('lotes_produto', produto_id=produto.id))

    return render_template('novo_lote.html', produto=produto)

@app.route('/produto/<int:produto_id>/baixa', methods=['GET', 'POST'])
def registrar_baixa(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    lotes = Lote.query.filter(
        Lote.produto_id == produto.id,
        Lote.quantidade_atual > 0
    ).order_by(Lote.data_validade.asc()).all()
    
    if request.method == 'POST':
        quantidade = float(request.form.get('quantidade_perdida', 0))
        motivo = request.form.get('motivo')
        usuario_id = request.form.get('usuario_id') or None
        observacao = request.form.get('observacao', '')
        lote_id = request.form.get('lote_id') or None

        lote = None
        if lote_id:
            lote = Lote.query.filter_by(id=lote_id, produto_id=produto.id).first_or_404()
            if quantidade > lote.quantidade_atual:
                return render_template(
                    'registrar_baixa.html', produto=produto, usuarios=usuarios, lotes=lotes,
                    erro='A quantidade informada é maior do que o saldo disponível no lote.'
                )
        elif lotes:
            return render_template(
                'registrar_baixa.html', produto=produto, usuarios=usuarios, lotes=lotes,
                erro='Selecione o lote de origem para registrar a baixa.'
            )

        registro = RegistroPerda(
            produto_id=produto.id,
            lote_id=lote.id if lote else None,
            usuario_id=usuario_id,
            quantidade_perdida=quantidade,
            motivo=motivo,
            observacao=observacao
        )
        
        produto.quantidade_estoque = max(0.0, produto.quantidade_estoque - quantidade)
        if lote:
            lote.quantidade_atual -= quantidade
        
        db.session.add(registro)
        db.session.commit()
        return redirect(url_for('historico_perdas'))

    return render_template('registrar_baixa.html', produto=produto, usuarios=usuarios, lotes=lotes)

@app.route('/historico-perdas')
def historico_perdas():
    perdas = RegistroPerda.query.order_by(RegistroPerda.data_registro.desc()).all()
    total_descartes = sum(p.quantidade_perdida for p in perdas)
    return render_template('historico_perdas.html', perdas=perdas, total_descartes=total_descartes)

# --- Rotas de Usuários / Fiscais ---

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if request.method == 'POST':
        nome = request.form.get('nome')
        matricula = request.form.get('matricula')
        cargo = request.form.get('cargo')

        novo_usuario = Usuario(nome=nome, matricula=matricula, cargo=cargo)
        db.session.add(novo_usuario)
        db.session.commit()
        return redirect(url_for('usuarios'))

    lista_usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    return render_template('usuarios.html', usuarios=lista_usuarios)

# --- Rotas de Inspeção e Controle de Temperatura ---

@app.route('/inspecoes')
def inspecoes():
    lista_inspecoes = InspecaoSetor.query.order_by(InspecaoSetor.data_inspecao.desc()).all()
    return render_template('inspecoes.html', inspecoes=lista_inspecoes)

@app.route('/inspecoes/nova', methods=['GET', 'POST'])
def nova_inspecao():
    usuarios = Usuario.query.order_by(Usuario.nome.asc()).all()
    
    if request.method == 'POST':
        fiscal_id = request.form.get('fiscal_id')
        setor = request.form.get('setor')
        temperatura = request.form.get('temperatura_aferida')
        status = request.form.get('status_conformidade')
        observacao = request.form.get('observacao', '')

        temp_valor = float(temperatura) if temperatura else None

        inspecao = InspecaoSetor(
            fiscal_id=fiscal_id,
            setor=setor,
            temperatura_aferida=temp_valor,
            status_conformidade=status,
            observacao=observacao
        )
        db.session.add(inspecao)
        db.session.commit()
        return redirect(url_for('inspecoes'))

    return render_template('nova_inspecao.html', usuarios=usuarios)

# --- Endpoint de API (Requisito Univesp) ---

@app.route('/api/produtos/alertas')
def api_alertas():
    produtos = Produto.query.all()
    dados = [
        {
            "id": p.id,
            "nome": p.nome,
            "categoria": p.categoria,
            "validade": p.data_validade.strftime('%Y-%m-%d'),
            "dias_restantes": p.dias_para_vencer,
            "alerta": p.status_alerta
        }
        for p in produtos if p.dias_para_vencer <= 2
    ]
    return {"total_criticos": len(dados), "produtos": dados}


@app.route('/api/clima')
def api_clima():
    clima = get_weather()
    if clima is None:
        return jsonify({"erro": "Não foi possível consultar a previsão do tempo agora."}), 503
    return jsonify(clima)

if __name__ == '__main__':
    app.run(debug=True)
