"""Interface em Streamlit com os fluxos completos do Alerta Perda."""

from datetime import date

import streamlit as st
from sqlalchemy import func

from app import app as flask_app
from models import InspecaoSetor, Lote, MovimentacaoEstoque, Produto, RegistroPerda, Usuario, db
from weather import get_weather


st.set_page_config(page_title="Alerta Perda", page_icon="🥦", layout="wide")


def context(callback):
    with flask_app.app_context():
        return callback()


def initialize():
    """A inicialização do Flask cria o esquema e a conta administrativa."""
    return None


def current_user():
    user_id = st.session_state.get("usuario_id")
    if not user_id:
        return None

    def get_user():
        user = db.session.get(Usuario, user_id)
        if not user or not user.ativo:
            return None
        return {"id": user.id, "nome": user.nome, "perfil": user.perfil, "cargo": user.nome_perfil}
    return context(get_user)


def login():
    _, column, _ = st.columns([1, 1.4, 1])
    with column:
        st.title("🥦 Alerta Perda")
        st.subheader("Acesso ao sistema")
        with st.form("login"):
            matricula = st.text_input("Matrícula")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", width="stretch")
        if submitted:
            def authenticate():
                user = Usuario.query.filter_by(matricula=matricula.strip()).first()
                return user.id if user and user.ativo and user.validar_senha(senha) else None
            user_id = context(authenticate)
            if user_id:
                st.session_state.usuario_id = user_id
                st.rerun()
            st.error("Matrícula ou senha inválida.")


def require(user, roles):
    if user["perfil"] not in roles:
        st.error("Seu perfil não possui permissão para esta funcionalidade.")
        st.stop()


def active_lot_rows():
    def query():
        lots = Lote.query.filter(Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
        return [{
            "Produto": lot.produto.nome,
            "Categoria": lot.produto.categoria,
            "Lote": lot.codigo_lote,
            "Local": lot.local_armazenamento or "-",
            "Saldo": f"{lot.quantidade_atual:g} {lot.produto.unidade_medida}",
            "Validade": lot.data_validade.strftime("%d/%m/%Y"),
            "Dias restantes": lot.dias_para_vencer,
            "Status": lot.status_alerta["texto"],
        } for lot in lots]
    return context(query)


def dashboard():
    def summary():
        lots = Lote.query.filter(Lote.quantidade_atual > 0).order_by(Lote.data_validade.asc()).all()
        return len(lots), sum(lot.dias_para_vencer <= 2 for lot in lots), sorted({lot.produto.categoria for lot in lots})
    total, critical, categories = context(summary)
    st.title("🥦 Alerta Perda")
    st.caption("Gestão preventiva de validade, estoque, perdas e inspeções.")
    a, b, c = st.columns(3)
    a.metric("Lotes ativos", total)
    b.metric("Lotes críticos", critical)
    c.metric("Categorias monitoradas", len(categories))
    st.subheader("Condições meteorológicas — Pitangueiras, SP")
    climate = get_weather(categories)
    if climate:
        a, b, c, d = st.columns(4)
        a.metric("Temperatura", f"{climate['temperatura']} °C")
        b.metric("Umidade", f"{climate['umidade']}%")
        c.metric("Chuva", f"{climate['probabilidade_chuva']}%")
        d.metric("Condição", climate["condicao"])
        recommendation = climate["recomendacao"]
        message = f"{recommendation['titulo']}: {recommendation['mensagem']}"
        (st.warning if recommendation["nivel"] == "warning" else st.success)(message)
        for action in recommendation["acoes"]:
            st.write(f"- {action}")
    else:
        st.info("A previsão está indisponível no momento. O restante do sistema continua acessível.")
    st.subheader("Lotes ativos por validade")
    st.dataframe(active_lot_rows(), width="stretch", hide_index=True)


def product_list():
    def query():
        return [(item.id, item.nome, item.categoria, item.unidade_medida) for item in Produto.query.order_by(Produto.nome).all()]
    return context(query)


def inventory(user):
    require(user, {"administrador", "gerente"})
    st.title("Cadastro e entrada de estoque")
    choice = st.radio("Tipo de entrada", ["Novo produto", "Novo lote", "Reposição"], horizontal=True)

    if choice == "Reposição":
        def query_lots():
            return [(lot.id, lot.produto.nome, lot.codigo_lote, lot.quantidade_atual, lot.produto.unidade_medida)
                    for lot in Lote.query.filter(Lote.quantidade_atual >= 0).order_by(Lote.data_validade).all()]
        lots = context(query_lots)
        lot_map = {item[0]: item for item in lots}
        if not lot_map:
            st.info("Não há lotes para repor.")
            return
        selected = st.selectbox("Lote", list(lot_map), format_func=lambda item: f"{lot_map[item][1]} — {lot_map[item][2]} — saldo: {lot_map[item][3]:g} {lot_map[item][4]}")
        with st.form("repor"):
            quantity = st.number_input("Quantidade de reposição", min_value=0.0, step=1.0)
            submitted = st.form_submit_button("Registrar reposição")
        if submitted:
            if quantity <= 0:
                st.error("Informe uma quantidade maior que zero.")
                return
            def replenish():
                lot = db.session.get(Lote, selected)
                lot.quantidade_inicial += quantity
                lot.quantidade_atual += quantity
                lot.produto.quantidade_estoque += quantity
                db.session.commit()
            context(replenish)
            st.success("Reposição registrada.")
            st.rerun()
        return

    products = product_list()
    product = None
    if choice == "Novo lote":
        if not products:
            st.info("Cadastre um produto primeiro.")
            return
        product_map = {item[0]: item for item in products}
        selected = st.selectbox("Produto existente", list(product_map), format_func=lambda item: product_map[item][1])
        product = product_map[selected]

    with st.form("entrada"):
        if choice == "Novo produto":
            name = st.text_input("Nome do produto")
            category = st.selectbox("Categoria", ["Hortifrúti (FLV)", "Carnes e Aves", "Laticínios e Frios", "Mercearia", "Outros"])
            barcode = st.text_input("Código de barras")
            unit = st.selectbox("Unidade", ["kg", "un", "bdj", "cx", "L"])
        else:
            name, category, barcode, unit = product[1], product[2], None, product[3]
        code = st.text_input("Código do lote")
        entry = st.date_input("Data de entrada", value=date.today())
        expiration = st.date_input("Data de validade", value=date.today())
        quantity = st.number_input("Quantidade", min_value=0.0, step=1.0)
        location = st.text_input("Local de armazenamento")
        submitted = st.form_submit_button("Registrar entrada")
    if not submitted:
        return
    if not code.strip() or quantity <= 0 or expiration < entry or (choice == "Novo produto" and (not name.strip() or not barcode.strip())):
        st.error("Preencha os dados obrigatórios e informe datas e quantidade válidas.")
        return

    def create_entry():
        if choice == "Novo produto":
            if Produto.query.filter_by(codigo_barras=barcode.strip()).first():
                return "Já existe um produto com este código de barras."
            item = Produto(nome=name.strip(), categoria=category, codigo_barras=barcode.strip(), data_validade=expiration, quantidade_estoque=quantity, unidade_medida=unit)
            db.session.add(item)
            db.session.flush()
        else:
            item = db.session.get(Produto, product[0])
            item.quantidade_estoque += quantity
        if Lote.query.filter_by(produto_id=item.id, codigo_lote=code.strip()).first():
            db.session.rollback()
            return "Esse código de lote já existe para o produto selecionado."
        db.session.add(Lote(produto_id=item.id, codigo_lote=code.strip(), data_entrada=entry, data_validade=expiration,
                            quantidade_inicial=quantity, quantidade_atual=quantity, local_armazenamento=location.strip() or None))
        db.session.commit()
        return None
    error = context(create_entry)
    if error:
        st.error(error)
    else:
        st.success("Entrada registrada com sucesso.")
        st.rerun()


def lots_and_operations(user):
    st.title("Lotes e movimentações")
    products = product_list()
    if not products:
        st.info("Não há produtos cadastrados.")
        return
    product_map = {item[0]: item for item in products}
    selected_product = st.selectbox("Produto", list(product_map), format_func=lambda item: product_map[item][1])

    def query_lots():
        return [(lot.id, lot.codigo_lote, lot.quantidade_atual, lot.produto.unidade_medida, lot.local_armazenamento or "-", lot.data_validade)
                for lot in Lote.query.filter_by(produto_id=selected_product).filter(Lote.quantidade_atual > 0).order_by(Lote.data_validade).all()]
    lots = context(query_lots)
    if not lots:
        st.info("Este produto não possui lote com saldo.")
        return
    lot_map = {item[0]: item for item in lots}
    selected = st.selectbox("Lote", list(lot_map), format_func=lambda item: f"{lot_map[item][1]} — {lot_map[item][2]:g} {lot_map[item][3]} — validade: {lot_map[item][5].strftime('%d/%m/%Y')}")
    selected_lot = lot_map[selected]
    st.caption(f"Local atual: {selected_lot[4]}")
    action = st.radio("Operação", ["Baixa por perda", "Saída por venda", "Remanejamento"], horizontal=True)
    with st.form("operacao"):
        quantity = st.number_input("Quantidade", min_value=0.0, max_value=float(selected_lot[2]), step=1.0)
        reason = st.selectbox("Motivo da perda", ["Produto vencido", "Avaria", "Quebra", "Falha de refrigeração", "Outro"]) if action == "Baixa por perda" else ""
        destination = st.text_input("Local de destino") if action == "Remanejamento" else ""
        notes = st.text_area("Observação")
        submitted = st.form_submit_button("Confirmar operação")
    if not submitted:
        return
    if quantity <= 0 or (action == "Remanejamento" and not destination.strip()):
        st.error("Informe uma quantidade válida e, no remanejamento, o local de destino.")
        return

    def execute():
        lot = db.session.get(Lote, selected)
        product = lot.produto
        if quantity > lot.quantidade_atual:
            return "A quantidade é maior que o saldo atual."
        origin = lot.local_armazenamento
        if action == "Baixa por perda":
            lot.quantidade_atual -= quantity
            product.quantidade_estoque = max(0, product.quantidade_estoque - quantity)
            db.session.add(RegistroPerda(produto_id=product.id, lote_id=lot.id, usuario_id=user["id"], quantidade_perdida=quantity, motivo=reason, observacao=notes.strip() or None))
        elif action == "Saída por venda":
            lot.quantidade_atual -= quantity
            product.quantidade_estoque = max(0, product.quantidade_estoque - quantity)
            db.session.add(MovimentacaoEstoque(produto_id=product.id, lote_id=lot.id, usuario_id=user["id"], tipo="saida_venda", quantidade=quantity, local_origem=origin, observacao=notes.strip() or None))
        else:
            if quantity == lot.quantidade_atual:
                lot.local_armazenamento = destination.strip()
            else:
                lot.quantidade_atual -= quantity
                code = f"{lot.codigo_lote}-R{MovimentacaoEstoque.query.count() + 1}"
                db.session.add(Lote(produto_id=product.id, codigo_lote=code, data_entrada=lot.data_entrada, data_validade=lot.data_validade,
                                  quantidade_inicial=quantity, quantidade_atual=quantity, local_armazenamento=destination.strip()))
            db.session.add(MovimentacaoEstoque(produto_id=product.id, lote_id=lot.id, usuario_id=user["id"], tipo="remanejamento", quantidade=quantity, local_origem=origin, local_destino=destination.strip(), observacao=notes.strip() or None))
        db.session.commit()
        return None
    error = context(execute)
    if error:
        st.error(error)
    else:
        st.success("Operação registrada e estoque atualizado.")
        st.rerun()


def losses():
    st.title("Histórico de perdas")
    def query():
        records = RegistroPerda.query.order_by(RegistroPerda.data_registro.desc()).all()
        rows = [{"Data": item.data_registro.strftime("%d/%m/%Y %H:%M"), "Produto": item.produto.nome, "Lote": item.lote.codigo_lote if item.lote else "-",
                 "Quantidade": f"{item.quantidade_perdida:g} {item.produto.unidade_medida}", "Motivo": item.motivo,
                 "Responsável": item.responsavel.nome if item.responsavel else "-", "Observação": item.observacao or "-"} for item in records]
        return rows, sum(item.quantidade_perdida for item in records)
    rows, total = context(query)
    st.metric("Quantidade descartada registrada", f"{total:g}")
    st.dataframe(rows, width="stretch", hide_index=True)


def inspections(user):
    st.title("Inspeções")
    with st.expander("Registrar nova inspeção"):
        with st.form("inspecao"):
            sector = st.selectbox("Setor", ["Área de hortifrúti", "Balcão de carnes", "Câmara fria 1", "Câmara fria 2", "Laticínios e frios", "Outro"])
            temperature = st.number_input("Temperatura aferida (°C)", value=0.0, step=0.1)
            status = st.selectbox("Status", ["Conforme", "Alerta", "Não conforme"])
            notes = st.text_area("Observação")
            submitted = st.form_submit_button("Registrar inspeção")
        if submitted:
            def create():
                db.session.add(InspecaoSetor(fiscal_id=user["id"], setor=sector, temperatura_aferida=temperature, status_conformidade=status, observacao=notes.strip() or None))
                db.session.commit()
            context(create)
            st.success("Inspeção registrada.")
            st.rerun()
    def query():
        return [{"Data": item.data_inspecao.strftime("%d/%m/%Y %H:%M"), "Setor": item.setor, "Responsável": item.fiscal.nome,
                 "Temperatura": f"{item.temperatura_aferida:g} °C" if item.temperatura_aferida is not None else "-", "Status": item.status_conformidade,
                 "Observação": item.observacao or "-"} for item in InspecaoSetor.query.order_by(InspecaoSetor.data_inspecao.desc()).all()]
    st.dataframe(context(query), width="stretch", hide_index=True)


def indicators(user):
    require(user, {"administrador", "gerente"})
    st.title("Indicadores")
    def query():
        total = db.session.query(func.coalesce(func.sum(RegistroPerda.quantidade_perdida), 0)).scalar()
        movements = MovimentacaoEstoque.query.count()
        categories = dict(db.session.query(Produto.categoria, func.sum(RegistroPerda.quantidade_perdida)).join(RegistroPerda).group_by(Produto.categoria).all())
        reasons = dict(db.session.query(RegistroPerda.motivo, func.sum(RegistroPerda.quantidade_perdida)).group_by(RegistroPerda.motivo).all())
        return total, movements, categories, reasons
    total, movements, categories, reasons = context(query)
    a, b = st.columns(2)
    a.metric("Quantidade descartada", f"{total:g}")
    b.metric("Movimentações registradas", movements)
    left, right = st.columns(2)
    with left:
        st.subheader("Perdas por categoria")
        st.bar_chart(categories)
    with right:
        st.subheader("Perdas por motivo")
        st.bar_chart(reasons)


def users(user):
    require(user, {"administrador"})
    st.title("Usuários")
    with st.expander("Cadastrar usuário"):
        with st.form("usuario"):
            name = st.text_input("Nome")
            registration = st.text_input("Matrícula")
            role = st.text_input("Cargo", value="Fiscal de Loja")
            profile = st.selectbox("Perfil", ["operador", "gerente", "administrador"])
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Cadastrar usuário")
        if submitted:
            if not name.strip() or not registration.strip() or len(password) < 6:
                st.error("Preencha os dados e use uma senha de pelo menos 6 caracteres.")
            else:
                def create():
                    if Usuario.query.filter_by(matricula=registration.strip()).first():
                        return False
                    item = Usuario(nome=name.strip(), matricula=registration.strip(), cargo=role.strip() or "Fiscal de Loja", perfil=profile, ativo=True)
                    item.definir_senha(password)
                    db.session.add(item)
                    db.session.commit()
                    return True
                if context(create):
                    st.success("Usuário cadastrado.")
                    st.rerun()
                st.error("Já existe um usuário com essa matrícula.")
    def query():
        return [{"Nome": item.nome, "Matrícula": item.matricula, "Cargo": item.cargo, "Perfil": item.nome_perfil, "Ativo": "Sim" if item.ativo else "Não"}
                for item in Usuario.query.order_by(Usuario.nome).all()]
    st.dataframe(context(query), width="stretch", hide_index=True)


def main():
    initialize()
    user = current_user()
    if not user:
        login()
        return
    with st.sidebar:
        st.title("Alerta Perda")
        st.caption(f"{user['nome']}\n{user['cargo']}")
        pages = ["Painel", "Cadastro", "Lotes e movimentações", "Histórico de perdas", "Inspeções"]
        if user["perfil"] in {"administrador", "gerente"}:
            pages.append("Indicadores")
        if user["perfil"] == "administrador":
            pages.append("Usuários")
        page = st.radio("Navegação", pages)
        if st.button("Sair", width="stretch"):
            st.session_state.clear()
            st.rerun()
    if page == "Painel":
        dashboard()
    elif page == "Cadastro":
        inventory(user)
    elif page == "Lotes e movimentações":
        lots_and_operations(user)
    elif page == "Histórico de perdas":
        losses()
    elif page == "Inspeções":
        inspections(user)
    elif page == "Indicadores":
        indicators(user)
    else:
        users(user)


main()
