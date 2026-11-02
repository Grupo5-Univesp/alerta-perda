from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    cargo = db.Column(db.String(50), nullable=False, default='Fiscal de Loja')
    perfil = db.Column(db.String(20), nullable=False, default='operador')
    senha_hash = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    perdas_registradas = db.relationship('RegistroPerda', backref='responsavel', lazy=True)
    inspecoes = db.relationship('InspecaoSetor', backref='fiscal', lazy=True)
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='responsavel', lazy=True)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def validar_senha(self, senha):
        return bool(self.senha_hash) and check_password_hash(self.senha_hash, senha)

    @property
    def nome_perfil(self):
        return {'administrador': 'Administrador', 'gerente': 'Gerente', 'operador': 'Operador'}.get(self.perfil, self.perfil)


def status_por_validade(dias):
    if dias < 0:
        return {'tipo': 'danger', 'texto': 'Vencido (Descarte Imediato)'}
    if dias <= 2:
        return {'tipo': 'warning', 'texto': 'Ação Comercial / Promoção Urgente'}
    if dias <= 5:
        return {'tipo': 'info', 'texto': 'Atenção / Giro Rápido'}
    return {'tipo': 'success', 'texto': 'Regular'}


class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    codigo_barras = db.Column(db.String(50), unique=True, nullable=False)
    data_validade = db.Column(db.Date, nullable=False)
    quantidade_estoque = db.Column(db.Float, nullable=False, default=0.0)
    unidade_medida = db.Column(db.String(10), nullable=False, default='kg')
    perdas = db.relationship('RegistroPerda', backref='produto', lazy=True)
    lotes = db.relationship('Lote', backref='produto', lazy=True, cascade='all, delete-orphan')

    @property
    def dias_para_vencer(self):
        return (self.data_validade - date.today()).days if self.data_validade else 999

    @property
    def status_alerta(self):
        return status_por_validade(self.dias_para_vencer)


class Lote(db.Model):
    __tablename__ = 'lotes'
    __table_args__ = (db.UniqueConstraint('produto_id', 'codigo_lote', name='uq_lote_por_produto'),)
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    codigo_lote = db.Column(db.String(50), nullable=False)
    data_entrada = db.Column(db.Date, nullable=False, default=date.today)
    data_validade = db.Column(db.Date, nullable=False)
    quantidade_inicial = db.Column(db.Float, nullable=False)
    quantidade_atual = db.Column(db.Float, nullable=False)
    local_armazenamento = db.Column(db.String(100), nullable=True)
    perdas = db.relationship('RegistroPerda', backref='lote', lazy=True)
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='lote', lazy=True)

    @property
    def dias_para_vencer(self):
        return (self.data_validade - date.today()).days

    @property
    def status_alerta(self):
        if self.quantidade_atual <= 0:
            return {'tipo': 'secondary', 'texto': 'Sem saldo'}
        return status_por_validade(self.dias_para_vencer)


class InspecaoSetor(db.Model):
    __tablename__ = 'inspecoes_setor'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    setor = db.Column(db.String(50), nullable=False)
    temperatura_aferida = db.Column(db.Float, nullable=True)
    status_conformidade = db.Column(db.String(30), nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    data_inspecao = db.Column(db.DateTime, default=datetime.now)


class RegistroPerda(db.Model):
    __tablename__ = 'registros_perda'
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    lote_id = db.Column(db.Integer, db.ForeignKey('lotes.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    quantidade_perdida = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(100), nullable=False)
    data_registro = db.Column(db.DateTime, default=datetime.now)
    observacao = db.Column(db.Text, nullable=True)


class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    lote_id = db.Column(db.Integer, db.ForeignKey('lotes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    tipo = db.Column(db.String(30), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    local_origem = db.Column(db.String(100), nullable=True)
    local_destino = db.Column(db.String(100), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    data_movimentacao = db.Column(db.DateTime, default=datetime.now)
    produto = db.relationship('Produto', backref=db.backref('movimentacoes', lazy=True))
