"""Versão pública de demonstração do Alerta Perda para o Streamlit Community Cloud.

O Streamlit Community Cloud usa armazenamento local temporário. Por isso esta
versão é somente de consulta e recria dados fictícios quando necessário. A
versão Flask permanece como a aplicação operacional completa.
"""

import streamlit as st

from app import app as flask_app
from models import InspecaoSetor, Lote, MovimentacaoEstoque, Produto, RegistroPerda
from seed_demo import seed
from weather import get_weather


st.set_page_config(page_title="Alerta Perda", page_icon="🥦", layout="wide")


def ensure_demo_data():
    with flask_app.app_context():
        if not Produto.query.first():
            seed()


def load_dashboard():
    with flask_app.app_context():
        lots = Lote.query.filter(Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
        rows = [{
            "Produto": lot.produto.nome,
            "Categoria": lot.produto.categoria,
            "Lote": lot.codigo_lote,
            "Local": lot.local_armazenamento or "-",
            "Saldo": f"{lot.quantidade_atual:g} {lot.produto.unidade_medida}",
            "Validade": lot.data_validade.strftime("%d/%m/%Y"),
            "Dias restantes": lot.dias_para_vencer,
            "Status": lot.status_alerta["texto"],
        } for lot in lots]
        categories = sorted({lot.produto.categoria for lot in lots})
        critical = sum(lot.dias_para_vencer <= 2 for lot in lots)
    return rows, categories, critical


def show_dashboard():
    rows, categories, critical = load_dashboard()
    st.title("🥦 Alerta Perda")
    st.caption("Demonstração pública com dados fictícios - gestão preventiva de validade e perdas.")
    first, second, third = st.columns(3)
    first.metric("Lotes ativos", len(rows))
    second.metric("Lotes críticos", critical)
    third.metric("Categorias monitoradas", len(categories))
    st.subheader("Condições meteorológicas")
    climate = get_weather(categories)
    if climate:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temperatura", f"{climate['temperatura']} °C")
        c2.metric("Umidade", f"{climate['umidade']}%")
        c3.metric("Chuva", f"{climate['probabilidade_chuva']}%")
        c4.metric("Condição", climate['condicao'])
        rec = climate['recomendacao']
        (st.warning if rec['nivel'] == 'warning' else st.success)(f"{rec['titulo']}: {rec['mensagem']}")
        for action in rec['acoes']:
            st.write(f"- {action}")
    else:
        st.info("A previsão não está disponível agora. O painel de lotes continua acessível.")
    st.subheader("Lotes ativos por validade")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_losses():
    with flask_app.app_context():
        losses = RegistroPerda.query.order_by(RegistroPerda.data_registro.desc()).all()
        rows = [{
            "Data": loss.data_registro.strftime("%d/%m/%Y %H:%M"),
            "Produto": loss.produto.nome,
            "Lote": loss.lote.codigo_lote if loss.lote else "-",
            "Quantidade": f"{loss.quantidade_perdida:g} {loss.produto.unidade_medida}",
            "Motivo": loss.motivo,
            "Observação": loss.observacao or "-",
        } for loss in losses]
    st.title("Histórico de perdas")
    st.caption("Os registros de descarte são vinculados ao produto e, quando aplicável, ao lote de origem.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_inspections():
    with flask_app.app_context():
        inspections = InspecaoSetor.query.order_by(InspecaoSetor.data_inspecao.desc()).all()
        rows = [{
            "Data": item.data_inspecao.strftime("%d/%m/%Y %H:%M"),
            "Setor": item.setor,
            "Responsável": item.fiscal.nome,
            "Temperatura": f"{item.temperatura_aferida} °C" if item.temperatura_aferida is not None else "-",
            "Status": item.status_conformidade,
            "Observação": item.observacao or "-",
        } for item in inspections]
    st.title("Inspeções")
    st.caption("Monitoramento preventivo de temperatura e conformidade dos setores.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_indicators():
    with flask_app.app_context():
        losses = RegistroPerda.query.all()
        movements = MovimentacaoEstoque.query.count()
        categories = {}
        reasons = {}
        for loss in losses:
            categories[loss.produto.categoria] = categories.get(loss.produto.categoria, 0) + loss.quantidade_perdida
            reasons[loss.motivo] = reasons.get(loss.motivo, 0) + loss.quantidade_perdida
    st.title("Indicadores")
    total = sum(loss.quantidade_perdida for loss in losses)
    one, two = st.columns(2)
    one.metric("Quantidade descartada registrada", f"{total:g}")
    two.metric("Movimentações registradas", movements)
    left, right = st.columns(2)
    with left:
        st.subheader("Perdas por categoria")
        st.bar_chart(categories)
    with right:
        st.subheader("Perdas por motivo")
        st.bar_chart(reasons)


ensure_demo_data()
page = st.sidebar.radio("Navegação", ["Painel", "Perdas", "Inspeções", "Indicadores"])
st.sidebar.divider()
st.sidebar.caption("Versão em nuvem para demonstração acadêmica. Os dados são fictícios e podem ser reiniciados pelo ambiente gratuito.")

if page == "Painel":
    show_dashboard()
elif page == "Perdas":
    show_losses()
elif page == "Inspeções":
    show_inspections()
else:
    show_indicators()
