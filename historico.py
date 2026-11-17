"""Histórico financeiro: todas as movimentações em uma tabela."""
from datetime import date

import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_data, formatar_moeda

ORDENACOES = {
    "Data (mais recente primeiro)": ("data", False),
    "Data (mais antiga primeiro)": ("data", True),
    "Valor (maior primeiro)": ("valor", False),
    "Valor (menor primeiro)": ("valor", True),
    "Descrição (A–Z)": ("descricao", True),
}


def render():
    st.title("🗂️ Histórico financeiro")
    hoje = date.today()
    hist = calc.construir_historico(db.carregar_df("entradas"), db.carregar_df("despesas"),
                                    db.carregar_df("poupanca_mov"))
    if hist.empty:
        st.info("Ainda não há movimentações. Cadastre entradas, despesas ou depósitos para vê-las aqui.")
        return

    f1, f2, f3 = st.columns([2, 2, 2])
    busca = f1.text_input("🔎 Pesquisar", placeholder="descrição, categoria, forma de pagamento…")
    tipos = f2.multiselect("Tipo de movimentação", sorted(hist["tipo"].unique()))
    categorias = f3.multiselect("Categoria", sorted(hist["categoria"].unique()))
    f4, f5, f6 = st.columns([2, 2, 2])
    situacoes = f4.multiselect("Situação", sorted(hist["situacao"].unique()))
    ordem = f5.selectbox("Ordenar por", list(ORDENACOES))
    periodo = f6.date_input("Período", value=(), format="DD/MM/YYYY", key="hist_periodo")

    vis = hist
    if busca:
        alvo = vis[["descricao", "categoria", "forma_pagamento", "tipo", "situacao"]].astype(str).agg(" ".join, axis=1)
        vis = vis[alvo.str.contains(busca, case=False, regex=False)]
    if tipos:
        vis = vis[vis["tipo"].isin(tipos)]
    if categorias:
        vis = vis[vis["categoria"].isin(categorias)]
    if situacoes:
        vis = vis[vis["situacao"].isin(situacoes)]
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        vis = calc.filtrar_periodo(vis, "data", periodo[0], periodo[1])
    coluna, crescente = ORDENACOES[ordem]
    vis = vis.sort_values(coluna, ascending=crescente, kind="stable")

    entradas = vis.loc[vis["tipo"] == config.MOV_ENTRADA, "valor"].sum()
    saidas = vis.loc[vis["tipo"] == config.MOV_SAIDA, "valor"].sum()
    saidas_pagas = vis.loc[(vis["tipo"] == config.MOV_SAIDA) & (vis["situacao"] == config.STATUS_PAGO), "valor"].sum()
    c = st.columns(4)
    with c[0]:
        ui.cartao("Entradas (filtro)", formatar_moeda(entradas), "verde")
    with c[1]:
        ui.cartao("Saídas (filtro)", formatar_moeda(saidas), "vermelho", f"{formatar_moeda(saidas_pagas)} já pagas")
    with c[2]:
        ui.cartao("Entradas − saídas pagas", formatar_moeda(entradas - saidas_pagas),
                  "verde" if entradas - saidas_pagas >= 0 else "vermelho")
    with c[3]:
        ui.cartao("Movimentações", str(len(vis)), "azul", f"de {len(hist)} no total")

    if vis.empty:
        st.warning("Nenhuma movimentação encontrada com esses filtros.")
        return

    t = vis.rename(columns={"data": "Data", "descricao": "Descrição", "categoria": "Categoria",
                            "tipo": "Tipo", "valor": "Valor", "forma_pagamento": "Forma de pagamento",
                            "situacao": "Situação"})
    estilo = ui.estilo_linhas(t, "Tipo", {"Valor": formatar_moeda, "Data": formatar_data})
    ui.mostrar_tabela(estilo, height=520)

    csv = t.assign(Data=t["Data"].dt.strftime("%d/%m/%Y")).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("⬇️ Exportar para CSV", csv, file_name=f"historico_{hoje:%Y%m%d}.csv", mime="text/csv")
    st.caption("🟩 Entradas · 🟥 Saídas · 🟦 Poupança. Clique no cabeçalho de uma coluna para ordenar.")
