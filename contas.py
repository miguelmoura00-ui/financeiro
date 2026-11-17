"""Controle de contas a pagar."""
from datetime import date

import pandas as pd
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_data, formatar_moeda


def _validar(nome: str, valor: float) -> str | None:
    if not nome.strip():
        return "Informe o nome da conta."
    if valor <= 0:
        return "O valor deve ser maior que zero."
    return None


def render():
    st.title("🧾 Contas a pagar")
    ui.mostrar_flash()
    hoje = date.today()
    contas = db.carregar_df("contas", "vencimento ASC, id ASC")
    contas = calc.adicionar_situacao(contas, hoje) if not contas.empty else contas.assign(situacao=pd.Series(dtype=str))

    def soma(sit):
        return float(contas.loc[contas["situacao"] == sit, "valor"].sum()) if not contas.empty else 0.0

    def qtd(sit):
        return int((contas["situacao"] == sit).sum()) if not contas.empty else 0

    pagas_mes = contas[(contas["situacao"] == config.SIT_PAGA)
                       & (contas["data_pagamento"].dt.to_period("M") == pd.Period(hoje, "M"))] if not contas.empty else contas
    c = st.columns(4)
    with c[0]:
        total_pend = soma(config.SIT_PENDENTE) + soma(config.SIT_PROXIMA) + soma(config.SIT_ATRASADA)
        ui.cartao("Total em aberto", formatar_moeda(total_pend), "laranja",
                  f"{qtd(config.SIT_PENDENTE) + qtd(config.SIT_PROXIMA) + qtd(config.SIT_ATRASADA)} conta(s)")
    with c[1]:
        ui.cartao("Atrasadas", formatar_moeda(soma(config.SIT_ATRASADA)), "vermelho", f"{qtd(config.SIT_ATRASADA)} conta(s)")
    with c[2]:
        ui.cartao(f"Vencem em {config.DIAS_ALERTA_VENCIMENTO} dias", formatar_moeda(soma(config.SIT_PROXIMA)), "laranja",
                  f"{qtd(config.SIT_PROXIMA)} conta(s)")
    with c[3]:
        ui.cartao(f"Pagas em {hoje:%m/%Y}", formatar_moeda(pagas_mes["valor"].sum() if not pagas_mes.empty else 0),
                  "verde", f"{len(pagas_mes)} conta(s)")

    if qtd(config.SIT_ATRASADA):
        nomes = ", ".join(contas.loc[contas["situacao"] == config.SIT_ATRASADA, "nome"])
        st.error(f"⚠️ Contas atrasadas: {nomes}")
    if qtd(config.SIT_PROXIMA):
        nomes = ", ".join(contas.loc[contas["situacao"] == config.SIT_PROXIMA, "nome"])
        st.warning(f"⏰ Vencem em breve: {nomes}")

    tab_lista, tab_nova, tab_gerenciar = st.tabs(["📋 Lista", "➕ Nova conta", "⚙️ Pagar / editar / excluir"])

    with tab_lista:
        if contas.empty:
            st.info("Nenhuma conta cadastrada.")
        else:
            filtro = st.multiselect("Situação", [config.SIT_ATRASADA, config.SIT_PROXIMA, config.SIT_PENDENTE, config.SIT_PAGA],
                                    default=[config.SIT_ATRASADA, config.SIT_PROXIMA, config.SIT_PENDENTE],
                                    key="ct_filtro")
            vis = contas[contas["situacao"].isin(filtro)] if filtro else contas
            t = vis.rename(columns={"nome": "Conta", "valor": "Valor", "vencimento": "Vencimento",
                                    "categoria": "Categoria", "situacao": "Situação", "data_pagamento": "Pago em"})
            t = t[["Conta", "Valor", "Vencimento", "Categoria", "Situação", "Pago em"]]
            ui.mostrar_tabela(ui.estilo_linhas(t, "Situação", {"Valor": formatar_moeda, "Vencimento": formatar_data,
                                                                "Pago em": formatar_data}))
            st.caption(f"{len(vis)} conta(s) · {formatar_moeda(vis['valor'].sum())}")

    with tab_nova:
        with st.form("form_nova_conta", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome da conta", key="nc_nome")
            valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key="nc_valor")
            c3, c4, c5 = st.columns(3)
            venc = c3.date_input("Data de vencimento", value=hoje, format="DD/MM/YYYY", key="nc_venc")
            cat = c4.selectbox("Categoria", config.CATEGORIAS_DESPESA, key="nc_cat")
            repete = c5.number_input("Repetir por quantos meses", min_value=1, max_value=36, value=1, step=1, key="nc_rep",
                                     help="Cria uma conta para cada mês, com o mesmo dia de vencimento.")
            if st.form_submit_button("💾 Salvar conta", type="primary"):
                erro = _validar(nome, valor)
                if erro:
                    st.error(erro)
                else:
                    for i in range(int(repete)):
                        v = (pd.Timestamp(venc) + pd.DateOffset(months=i)).date()
                        rotulo = nome.strip() if repete == 1 else f"{nome.strip()} ({i + 1}/{int(repete)})"
                        db.inserir("contas", {"nome": rotulo, "valor": valor, "vencimento": v,
                                              "categoria": cat, "status": config.STATUS_PENDENTE})
                    ui.flash(f"{int(repete)} conta(s) cadastrada(s)!")
                    st.rerun()

    with tab_gerenciar:
        reg = ui.selecionar_registro(
            contas, lambda r: f"{r['vencimento']:%d/%m/%Y} · {r['nome']} · {formatar_moeda(r['valor'])} · {r['situacao']}",
            "sel_conta", "Conta")
        if reg is not None:
            rid = int(reg["id"])
            paga = reg["status"] == config.STATUS_PAGO
            if paga:
                st.success(f"Conta paga em {formatar_data(reg['data_pagamento'])}.")
                if st.button("↩️ Desfazer pagamento", key=f"desf_{rid}"):
                    db.desfazer_pagamento(rid)
                    ui.flash("Pagamento desfeito: a despesa vinculada foi removida.")
                    st.rerun()
            else:
                with st.form(f"form_pagar_{rid}"):
                    st.markdown("**Marcar como paga**")
                    c1, c2, c3 = st.columns(3)
                    data_pag = c1.date_input("Data do pagamento", value=hoje, format="DD/MM/YYYY", key=f"pg{rid}_data")
                    forma = c2.selectbox("Forma de pagamento", config.FORMAS_PAGAMENTO, key=f"pg{rid}_forma")
                    tipo = c3.selectbox("Tipo da despesa", config.TIPOS_DESPESA, key=f"pg{rid}_tipo")
                    if st.form_submit_button("✅ Marcar como paga", type="primary"):
                        db.pagar_conta(rid, data_pag, forma, tipo)
                        ui.flash("Conta paga! Ela agora aparece nas despesas.")
                        st.rerun()

            st.divider()
            with st.form(f"form_edit_conta_{rid}"):
                st.markdown("**Editar dados da conta**")
                c1, c2 = st.columns(2)
                nome = c1.text_input("Nome da conta", value=reg["nome"], key=f"ec{rid}_nome")
                valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f",
                                        value=float(reg["valor"]), key=f"ec{rid}_valor")
                c3, c4 = st.columns(2)
                venc = c3.date_input("Data de vencimento", value=reg["vencimento"].date(), format="DD/MM/YYYY",
                                     key=f"ec{rid}_venc")
                cats = config.CATEGORIAS_DESPESA if reg["categoria"] in config.CATEGORIAS_DESPESA \
                    else config.CATEGORIAS_DESPESA + [reg["categoria"]]
                cat = c4.selectbox("Categoria", cats, index=ui.indice(cats, reg["categoria"]), key=f"ec{rid}_cat")
                confirma = st.checkbox("Confirmo a exclusão desta conta", key=f"ec{rid}_conf")
                b1, b2 = st.columns(2)
                salvar = b1.form_submit_button("💾 Salvar alterações")
                excluir = b2.form_submit_button("🗑️ Excluir conta")
            if salvar:
                erro = _validar(nome, valor)
                if erro:
                    st.error(erro)
                else:
                    db.atualizar_conta(rid, {"nome": nome.strip(), "valor": valor, "vencimento": venc, "categoria": cat})
                    ui.flash("Conta atualizada.")
                    st.rerun()
            if excluir:
                if confirma:
                    db.excluir("contas", rid)
                    ui.flash("Conta excluída." + (" A despesa do pagamento foi mantida." if paga else ""))
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")
