import unittest

from app import app


class ProductRouteTest(unittest.TestCase):
    def test_new_product_form_contains_first_lot_fields(self):
        response = app.test_client().get('/produto/novo')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="codigo_lote"', response.data)
        self.assertIn(b'name="data_entrada"', response.data)
        self.assertIn(b'name="origem_produto"', response.data)
        self.assertIn(b'name="tipo_lote"', response.data)

    def test_dashboard_uses_lot_priority(self):
        response = app.test_client().get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lotes ativos ordenados pela validade', response.data)
        self.assertIn(b'lote(s) cr', response.data)
