"""Cria dados fictícios para demonstrar as funcionalidades do Alerta Perda."""

from datetime import date, timedelta

from app import app
from models import InspecaoSetor, Lote, Produto, RegistroPerda, Usuario, db


DEMO_PREFIX = "DEMO-"


def create_product(nome, categoria, sku, unidade, lotes):
    produto = Produto(
        nome=nome,
        categoria=categoria,
        codigo_barras=sku,
        data_validade=min(lote[1] for lote in lotes),
        quantidade_estoque=sum(lote[3] for lote in lotes),
        unidade_medida=unidade,
    )
    db.session.add(produto)
    db.session.flush()

    created_lots = []
    for codigo, validade, quantidade_inicial, quantidade_atual, local in lotes:
        lote = Lote(
            produto_id=produto.id,
            codigo_lote=codigo,
            data_entrada=date.today() - timedelta(days=2),
            data_validade=validade,
            quantidade_inicial=quantidade_inicial,
            quantidade_atual=quantidade_atual,
            local_armazenamento=local,
        )
        db.session.add(lote)
        created_lots.append(lote)
    return produto, created_lots


def seed():
    if Produto.query.filter(Produto.codigo_barras.like(f"{DEMO_PREFIX}%")).first():
        print("Dados demonstrativos já cadastrados.")
        return

    hoje = date.today()
    fiscal = Usuario(nome="Marina Alves", matricula="DEMO-001", cargo="Fiscal de Prevenção", perfil="operador")
    encarregado = Usuario(nome="Carlos Mendes", matricula="DEMO-002", cargo="Encarregado de Perecíveis", perfil="gerente")
    fiscal.definir_senha("demo123")
    encarregado.definir_senha("demo123")
    db.session.add_all([fiscal, encarregado])
    db.session.flush()

    morango, lotes_morango = create_product(
        "Morango bandeja 250g", "Hortifrúti (FLV)", "DEMO-001", "bdj",
        [
            ("MOR-1001", hoje + timedelta(days=1), 12, 12, "Área de vendas"),
            ("MOR-1002", hoje + timedelta(days=5), 18, 18, "Câmara fria 1"),
        ],
    )
    carne, lotes_carne = create_product(
        "Acém bovino", "Carnes e Aves", "DEMO-002", "kg",
        [("CAR-2001", hoje + timedelta(days=2), 18, 18, "Balcão de carnes")],
    )
    banana, lotes_banana = create_product(
        "Banana nanica", "Hortifrúti (FLV)", "DEMO-003", "kg",
        [("BAN-3001", hoje - timedelta(days=1), 15, 11, "Área de vendas")],
    )
    frango, _ = create_product(
        "Peito de frango resfriado", "Carnes e Aves", "DEMO-004", "kg",
        [("FRA-4001", hoje + timedelta(days=7), 20, 20, "Câmara fria 2")],
    )

    db.session.add(RegistroPerda(
        produto_id=banana.id,
        lote=lotes_banana[0],
        usuario_id=fiscal.id,
        quantidade_perdida=4,
        motivo="Produto vencido",
        observacao="Registro fictício para demonstração.",
    ))
    db.session.add_all([
        InspecaoSetor(
            fiscal_id=fiscal.id, setor="Balcão de carnes", temperatura_aferida=3.2,
            status_conformidade="Conforme", observacao="Aferição demonstrativa.",
        ),
        InspecaoSetor(
            fiscal_id=encarregado.id, setor="Área de hortifrúti", temperatura_aferida=27.5,
            status_conformidade="Alerta", observacao="Reforçar giro dos produtos expostos.",
        ),
    ])
    db.session.commit()
    print("Dados demonstrativos criados: 4 produtos, 5 lotes, 2 usuários, 1 perda e 2 inspeções.")


def seed_video_catalog():
    """Inclui produtos atuais para apresentar os fluxos do sistema em vídeo."""
    if Produto.query.filter(Produto.codigo_barras.like("VIDEO-%")).first():
        print("Catálogo para vídeo já cadastrado.")
        return

    hoje = date.today()
    catalogo = [
        ("Tomate italiano 1 kg", "Hortifrúti (FLV)", "VIDEO-001", "kg", [
            ("TOM-1101", hoje + timedelta(days=1), 14, 14, "Área de vendas"),
            ("TOM-1102", hoje + timedelta(days=4), 20, 20, "Câmara fria 1"),
        ]),
        ("Iogurte natural 170 g", "Laticínios e Frios", "VIDEO-002", "un", [
            ("IOG-2201", hoje + timedelta(days=2), 36, 36, "Refrigerador de laticínios"),
        ]),
        ("Leite integral UHT 1 L", "Laticínios e Frios", "VIDEO-003", "un", [
            ("LEI-3301", hoje + timedelta(days=12), 48, 48, "Gôndola central"),
        ]),
        ("Queijo muçarela fatiado", "Laticínios e Frios", "VIDEO-004", "kg", [
            ("QUE-4401", hoje + timedelta(days=5), 9, 9, "Balcão de frios"),
        ]),
        ("Ovos brancos com 12 unidades", "Mercearia", "VIDEO-005", "un", [
            ("OVO-5501", hoje + timedelta(days=9), 30, 30, "Gôndola de mercearia"),
        ]),
    ]
    for nome, categoria, sku, unidade, lotes in catalogo:
        create_product(nome, categoria, sku, unidade, lotes)
    db.session.commit()
    print("Catálogo para vídeo criado: 5 produtos e 6 lotes.")


if __name__ == "__main__":
    with app.app_context():
        seed()
