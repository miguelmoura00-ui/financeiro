"""Gráficos e relatórios financeiros (Plotly)."""
from datetime import date

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import calculos as calc
import config
import database as db
import ui

HOVER = "R$ %{y:,.2f}<extra></extra>"


def render():
    st.title("📈 Gráficos e relatórios")
    hoje = date.today()

    c1, c2 = st.columns([3, 2])
    with c1:
        inicio, fim, nome = ui.seletor_periodo("graf")
    with c2:
        incluir_pend = st.checkbox("Incluir despesas pendentes", value=False,
                                   help="Por padrão os gráficos usam apenas despesas pagas.")
    freq = calc.escolher_freq(inicio, fim)
    st.caption(f"Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · agrupado por {'dia' if freq == 'D' else 'mês'}.")

    entradas = db.carregar_df("entradas")
    despesas = db.carregar_df("despesas")
    mov = db.carregar_df("poupanca_mov")
    metas = db.carregar_df("metas")
    desp = despesas if incluir_pend or despesas.empty else despesas[despesas["status"] == config.STATUS_PAGO]

    idx = calc.serie_agrupada(entradas, "data", "valor", inicio, fim, freq).index
    rotulos = calc.rotulos_periodo(idx, freq)

    col1, col2 = st.columns(2)

    # 1) Pizza: despesas por categoria
    with col1:
        d = calc.filtrar_periodo(desp, "data", inicio, fim)
        if d.empty:
            st.info("Sem despesas no período para o gráfico de categorias.")
        else:
            por_cat = d.groupby("categoria")["valor"].sum().sort_values(ascending=False)
            fig = px.pie(names=por_cat.index, values=por_cat.values, hole=0.35,
                         title="Despesas por categoria")
            fig.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>")
            ui.mostrar_grafico(fig)

    # 2) Barras: entradas × saídas
    with col2:
        ent = calc.serie_agrupada(entradas, "data", "valor", inicio, fim, freq)
        sai = calc.serie_agrupada(desp, "data", "valor", inicio, fim, freq)
        fig = go.Figure()
        fig.add_bar(name="Entradas", x=rotulos, y=ent.values, marker_color=config.CORES["verde"], hovertemplate=HOVER)
        fig.add_bar(name="Saídas", x=rotulos, y=sai.values, marker_color=config.CORES["vermelho"], hovertemplate=HOVER)
        fig.update_layout(barmode="group", title="Entradas × saídas")
        ui.mostrar_grafico(fig)

    col3, col4 = st.columns(2)

    # 3) Linha: evolução do saldo
    with col3:
        saldo = calc.serie_saldo(entradas, despesas, mov, inicio, fim, freq, incluir_pendentes=incluir_pend)
        fig = go.Figure(go.Scatter(x=rotulos, y=saldo.values, mode="lines+markers",
                                   line=dict(color=config.CORES["azul"], width=3), hovertemplate=HOVER))
        fig.update_layout(title="Evolução do saldo disponível")
        ui.mostrar_grafico(fig)

    # 4) Barras: fixas × variáveis
    with col4:
        fixas = calc.serie_agrupada(desp[desp["tipo"] == config.TIPO_FIXA] if not desp.empty else desp,
                                    "data", "valor", inicio, fim, freq)
        variaveis = calc.serie_agrupada(desp[desp["tipo"] == config.TIPO_VARIAVEL] if not desp.empty else desp,
                                        "data", "valor", inicio, fim, freq)
        fig = go.Figure()
        fig.add_bar(name="Fixas", x=rotulos, y=fixas.values, marker_color=config.CORES["azul"], hovertemplate=HOVER)
        fig.add_bar(name="Variáveis", x=rotulos, y=variaveis.values, marker_color=config.CORES["laranja"], hovertemplate=HOVER)
        fig.update_layout(barmode="group", title="Despesas fixas × variáveis")
        ui.mostrar_grafico(fig)

    col5, col6 = st.columns(2)

    # 5) Progresso das metas (independe do período)
    with col5:
        prog = calc.progresso_metas(metas, mov)
        if prog.empty:
            st.info("Crie metas na página Poupança para acompanhar o progresso aqui.")
        else:
            prog = prog.sort_values("pct")
            cores = [config.CORES["verde"] if p >= 100 else config.CORES["azul"] for p in prog["pct"]]
            fig = go.Figure(go.Bar(
                x=prog["pct"].clip(upper=100), y=prog["nome"], orientation="h", marker_color=cores,
                text=[f"{p:.0f}%" for p in prog["pct"]], textposition="inside",
                customdata=prog[["atual", "valor_alvo"]].values,
                hovertemplate="%{y}<br>R$ %{customdata[0]:,.2f} de R$ %{customdata[1]:,.2f}<extra></extra>"))
            fig.update_xaxes(range=[0, 100], title="% da meta")
            fig.update_layout(title="Progresso das metas financeiras")
            ui.mostrar_grafico(fig)

    # 6) Área: economias acumuladas
    with col6:
        eco = calc.serie_economias(mov, inicio, fim, freq)
        fig = go.Figure(go.Scatter(x=rotulos, y=eco.values, fill="tozeroy", mode="lines",
                                   line=dict(color=config.CORES["verde"]), hovertemplate=HOVER))
        fig.update_layout(title="Economias acumuladas")
        ui.mostrar_grafico(fig)
