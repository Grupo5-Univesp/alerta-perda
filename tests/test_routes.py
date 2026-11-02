import unittest
import uuid
from datetime import date, timedelta

from app import app
from models import db, Lote, MovimentacaoEstoque, Produto, Usuario


class ProductRouteTest(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        self.client = app.test_client()
        self.admin = Usuario.query.filter_by(matricula='ADMIN-001').first()
        with self.client.session_transaction() as session:
            session['usuario_id'] = self.admin.id

    def tearDown(self):
        self.context.pop()

    def test_new_product_form_contains_first_lot_fields(self):
        response = self.client.get('/produto/novo')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="codigo_lote"', response.data)
        self.assertIn(b'name="data_entrada"', response.data)
        self.assertIn(b'name="origem_produto"', response.data)
        self.assertIn(b'name="tipo_lote"', response.data)

    def test_dashboard_uses_lot_priority(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lotes ativos ordenados pela validade', response.data)

    def test_anonymous_user_is_redirected_to_login(self):
        anonymous = app.test_client()
        response = anonymous.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_product_entry_creates_first_lot(self):
        code = f'TEST-{uuid.uuid4().hex[:8]}'
        response = self.client.post('/produto/novo', data={
            'modo_entrada': 'novo_produto', 'nome': 'Produto de teste',
            'categoria': 'Hortifrúti (FLV)', 'codigo_barras': code,
            'unidade_medida': 'un', 'codigo_lote': 'TESTE-01',
            'data_entrada': date.today().isoformat(),
            'data_validade': (date.today() + timedelta(days=8)).isoformat(),
            'local_armazenamento': 'Teste', 'quantidade_entrada': '7',
        })
        self.assertEqual(response.status_code, 302)
        product = Produto.query.filter_by(codigo_barras=code).first()
        self.assertIsNotNone(product)
        self.assertEqual(product.lotes[0].quantidade_atual, 7)
        MovimentacaoEstoque.query.filter_by(produto_id=product.id).delete()
        db.session.delete(product)
        db.session.commit()

    def test_sale_movement_reduces_lot_and_product_balance(self):
        code = f'MOV-{uuid.uuid4().hex[:8]}'
        product = Produto(nome='Movimentação teste', categoria='Carnes e Aves', codigo_barras=code,
                          data_validade=date.today() + timedelta(days=7), quantidade_estoque=10, unidade_medida='kg')
        db.session.add(product)
        db.session.flush()
        lot = Lote(produto_id=product.id, codigo_lote='MOV-01', data_entrada=date.today(),
                   data_validade=date.today() + timedelta(days=7), quantidade_inicial=10,
                   quantidade_atual=10, local_armazenamento='Câmara 1')
        db.session.add(lot)
        db.session.commit()
        response = self.client.post(f'/produto/{product.id}/movimentacao', data={
            'tipo': 'saida_venda', 'lote_id': lot.id, 'quantidade': '3', 'observacao': 'Teste',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Lote, lot.id).quantidade_atual, 7)
        self.assertEqual(db.session.get(Produto, product.id).quantidade_estoque, 7)
        MovimentacaoEstoque.query.filter_by(produto_id=product.id).delete()
        db.session.delete(product)
        db.session.commit()
