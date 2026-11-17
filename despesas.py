"""Controle de saídas e despesas."""
from datetime import date

import pandas as pd
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_moeda


def _validar(nome: str, valor: float) -> str | None:
    if not nome.strip():
        return "Informe o nome da despesa."
    if valor <= 0:
        return "O valor deve ser maior que zero."
    return None


def _campos(prefixo: str, reg=None, hoje: date | None = None) -> dict:
    """Desenha os campos do formulário (novo ou edição) e devolve os valores."""
    hoje = hoje or date.today()
    g = (lambda k, padrao="": reg[k] if reg is not None and reg[k] is not None else padrao)
    c1, c2 = st.columns(2)
    nome = c1.text_input("Nome da despesa", value=g("nome"), key=f"{prefixo}_nome")
    valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f",
                            value=float(g("valor", 0.0)), key=f"{prefixo}_valor")
    c3, c4 = st.columns(2)
    cats = config.CATEGORIAS_DESPESA if g("categoria") in ("", *config.CATEGORIAS_DESPESA) \
        else config.CATEGORIAS_DESPESA + [g("categoria")]
    categoria = c3.selectbox("Categoria", cats, index=ui.indice(cats, g("categoria")), key=f"{prefixo}_cat")
    data = c4.date_input("Data", value=reg["data"].date() if reg is not None else hoje,
                         format="DD/MM/YYYY", key=f"{prefixo}_data")
    c5, c6, c7 = st.columns(3)
    formas = config.FORMAS_PAGAMENTO if g("forma_pagamento") in ("", *config.FORMAS_PAGAMENTO) \
        else config.FORMAS_PAGAMENTO + [g("forma_pagamento")]
    forma = c5.selectbox("Forma de pagamento", formas, index=ui.indice(formas, g("forma_pagamento")),
                         key=f"{prefixo}_forma")
    status = c6.selectbox("Status", config.STATUS_DESPESA, index=ui.indice(config.STATUS_DESPESA, g("status", config.STATUS_PAGO)),
                         key=f"{prefixo}_status")
    tipo = c7.selectbox("Tipo", config.TIPOS_DESPESA, index=ui.indice(config.TIPOS_DESPESA, g("tipo", config.TIPO_VARIAVEL), 1),
                       key=f"{prefixo}_tipo")
    descricao = st.text_area("Descrição adicional", value=g("descricao"), key=f"{prefixo}_desc")
    return {"nome": nome.strip(), "valor": valor, "categoria": categoria, "data": data,
            "forma_pagamento": forma, "status": status, "tipo": tipo, "descricao": descricao.strip()}


def render():
    st.title("💸 Despesas")
    ui.mostrar_flash()
    hoje = date.today()
    df = db.carregar_df("despesas", "data DESC, id DESC")

    resumo = calc.resumo_mes(db.carregar_df("entradas"), df, hoje)
    c = st.columns(4)
    with c[0]:
        ui.cartao(f"Gasto em {hoje:%m/%Y}", formatar_moeda(resumo["gasto"]), "vermelho", "despesas pagas")
    with c[1]:
        ui.cartao("Pendentes no mês", formatar_moeda(resumo["pendentes"]), "laranja", "ainda não pagas")
    with c[2]:
        ui.cartao("Fixas", formatar_moeda(resumo["fixas"]), "vermelho", "pagas no mês")
    with c[3]:
        ui.cartao("Variáveis", formatar_moeda(resumo["variaveis"]), "vermelho", "pagas no mês")

    tab_nova, tab_editar, tab_lista = st.tabs(["➕ Nova despesa", "✏️ Editar / excluir", "🔎 Consultar com filtros"])

    with tab_nova:
        with st.form("form_nova_despesa", clear_on_submit=True):
            dados = _campos("nova", None, hoje)
            if st.form_submit_button("💾 Salvar despesa", type="primary"):
                erro = _validar(dados["nome"], dados["valor"])
                if erro:
                    st.error(erro)
                else:
                    db.inserir("despesas", dados)
                    ui.flash("Despesa cadastrada com sucesso!")
                    st.rerun()

    with tab_editar:
        reg = ui.selecionar_registro(
            df, lambda r: f"{r['data']:%d/%m/%Y} · {r['nome']} · {formatar_moeda(r['valor'])} · {r['status']}",
            "sel_despesa")
        if reg is not None:
            rid = int(reg["id"])
            if pd.notna(reg["conta_id"]):  # despesa vinculada a uma conta
                st.caption("ℹ️ Esta despesa foi gerada pelo pagamento de uma conta. "
                           "Para desfazer o pagamento, use a página *Contas a pagar*.")
            with st.form(f"form_edit_despesa_{rid}"):
                dados = _campos(f"ed{rid}", reg, hoje)
                confirma = st.checkbox("Confirmo a exclusão deste registro", key=f"ed{rid}_conf")
                b1, b2 = st.columns(2)
                salvar = b1.form_submit_button("💾 Salvar alterações", type="primary")
                excluir = b2.form_submit_button("🗑️ Excluir registro")
            if salvar:
                erro = _validar(dados["nome"], dados["valor"])
                if erro:
                    st.error(erro)
                else:
                    db.atualizar("despesas", rid, dados)
                    ui.flash("Despesa atualizada.")
                    st.rerun()
            if excluir:
                if confirma:
                    db.excluir("despesas", rid)
                    ui.flash("Despesa excluída.")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

    with tab_lista:
        if df.empty:
            st.info("Nenhuma despesa cadastrada.")
        else:
            f1, f2, f3 = st.columns(3)
            cats = f1.multiselect("Categoria", config.CATEGORIAS_DESPESA)
            status = f2.multiselect("Situação do pagamento", config.STATUS_DESPESA)
            tipos = f3.multiselect("Tipo", config.TIPOS_DESPESA)
            f4, f5, f6 = st.columns(3)
            periodo = f4.date_input("Período", value=(), format="DD/MM/YYYY", key="desp_periodo")
            vmin = f5.number_input("Valor mínimo (R$)", min_value=0.0, step=10.0, format="%.2f", key="desp_vmin")
            vmax = f6.number_input("Valor máximo (R$, 0 = sem limite)", min_value=0.0, step=10.0,
                                   format="%.2f", key="desp_vmax")
            vis = df
            if cats:
                vis = vis[vis["categoria"].isin(cats)]
            if status:
                vis = vis[vis["status"].isin(status)]
            if tipos:
                vis = vis[vis["tipo"].isin(tipos)]
            if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
                vis = calc.filtrar_periodo(vis, "data", periodo[0], periodo[1])
            vis = vis[vis["valor"] >= vmin]
            if vmax > 0:
                vis = vis[vis["valor"] <= vmax]

            tabela = vis.rename(columns={
                "nome": "Despesa", "valor": "Valor", "categoria": "Categoria", "data": "Data",
                "forma_pagamento": "Forma de pagamento", "status": "Status", "tipo": "Tipo",
                "descricao": "Descrição"})
            ui.mostrar_tabela(
                tabela[["Data", "Despesa", "Valor", "Categoria", "Forma de pagamento", "Status", "Tipo", "Descrição"]],
                column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                               "Valor": st.column_config.NumberColumn(format="R$ %.2f")})
            pagas = vis[vis["status"] == config.STATUS_PAGO]["valor"].sum()
            pend = vis[vis["status"] == config.STATUS_PENDENTE]["valor"].sum()
            st.caption(f"{len(vis)} registro(s) · pagas {formatar_moeda(pagas)} · pendentes {formatar_moeda(pend)}")
