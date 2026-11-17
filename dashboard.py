"""Painel principal."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_data, formatar_moeda, formatar_pct


def render():
    st.title("📊 Painel financeiro")
    ui.mostrar_flash()
    hoje = date.today()

    entradas = db.carregar_df("entradas")
    despesas = db.carregar_df("despesas")
    contas = db.carregar_df("contas")
    rendas = db.carregar_df("rendas")
    mov = db.carregar_df("poupanca_mov")

    if db.esta_vazio():
        st.info("Ainda não há dados. Cadastre suas entradas e despesas pelo menu lateral "
                "ou use **Carregar dados de exemplo** na barra lateral para conhecer o sistema.")

    renda_cadastrada = float(rendas.loc[rendas["ativa"] == 1, "valor"].sum()) if not rendas.empty else 0.0
    atual = calc.resumo_mes(entradas, despesas, hoje, renda_cadastrada)
    anterior = calc.resumo_mes(entradas, despesas, calc.mes_anterior(hoje), renda_cadastrada)
    saldo = calc.saldo_total(entradas, despesas, mov)
    poupado = calc.saldo_poupanca(mov)
    pendentes = calc.pagamentos_pendentes(contas, despesas, hoje)
    total_pendente = float(pendentes["valor"].sum()) if not pendentes.empty else 0.0

    st.caption(f"Resumo de {hoje.strftime('%m/%Y')} · valores de gasto consideram despesas com status *Pago*.")

    # ---- Cartões (linha 1)
    c = st.columns(5)
    with c[0]:
        ui.cartao("Saldo total disponível", formatar_moeda(saldo), "azul", "entradas − gastos − poupança")
    with c[1]:
        ui.cartao("Recebido no mês", formatar_moeda(atual["recebido"]), "verde", "total de entradas")
    with c[2]:
        ui.cartao("Gasto no mês", formatar_moeda(atual["gasto"]), "vermelho",
                  f"+ {formatar_moeda(atual['pendentes'])} pendentes" if atual["pendentes"] else "despesas pagas")
    with c[3]:
        ui.cartao("Renda mensal", formatar_moeda(renda_cadastrada), "azul", "fontes de renda ativas")
    with c[4]:
        ui.cartao("Economizado no mês", formatar_moeda(atual["economizado"]),
                  "verde" if atual["economizado"] >= 0 else "vermelho", "recebido − gasto")

    # ---- Cartões (linha 2)
    c = st.columns(5)
    with c[0]:
        ui.cartao("Despesas fixas", formatar_moeda(atual["fixas"]), "vermelho", "pagas no mês")
    with c[1]:
        ui.cartao("Despesas variáveis", formatar_moeda(atual["variaveis"]), "vermelho", "pagas no mês")
    with c[2]:
        ui.cartao("% da renda economizada", formatar_pct(atual["pct_economizado"]),
                  "verde" if atual["pct_economizado"] >= 0 else "vermelho", "sobre o que foi recebido")
    with c[3]:
        ui.cartao("Contas pendentes", formatar_moeda(total_pendente), "laranja",
                  f"{len(pendentes)} pagamento(s) em aberto")
    with c[4]:
        ui.cartao("Guardado na poupança", formatar_moeda(poupado), "azul", "saldo acumulado")

    # ---- Alertas
    alertas_mostrados = False
    if not pendentes.empty:
        atrasadas = pendentes[pendentes["situacao"] == config.SIT_ATRASADA]
        proximas = pendentes[pendentes["situacao"] == config.SIT_PROXIMA]
        if not atrasadas.empty:
            st.error(f"⚠️ {len(atrasadas)} pagamento(s) atrasado(s), somando {formatar_moeda(atrasadas['valor'].sum())}: "
                     + ", ".join(atrasadas["nome"].head(4)) + ("…" if len(atrasadas) > 4 else ""))
            alertas_mostrados = True
        if not proximas.empty:
            st.warning(f"⏰ {len(proximas)} pagamento(s) vencem nos próximos {config.DIAS_ALERTA_VENCIMENTO} dias, "
                       f"somando {formatar_moeda(proximas['valor'].sum())}: "
                       + ", ".join(proximas["nome"].head(4)) + ("…" if len(proximas) > 4 else ""))
            alertas_mostrados = True
    limites = db.obter_limites(hoje.strftime("%Y-%m"))
    if limites:
        orc = calc.status_orcamento(limites, despesas, hoje)
        for r in orc[orc["nivel"] == "estourado"].itertuples():
            st.error(f"🚨 Limite de **{r.categoria}** ultrapassado: {formatar_moeda(r.gasto)} de {formatar_moeda(r.limite)}.")
            alertas_mostrados = True
        for r in orc[orc["nivel"] == "atencao"].itertuples():
            st.warning(f"🔔 **{r.categoria}** já usou {formatar_pct(r.pct, 0)} do limite "
                       f"({formatar_moeda(r.gasto)} de {formatar_moeda(r.limite)}).")
            alertas_mostrados = True
    if not alertas_mostrados and not db.esta_vazio():
        st.success("✅ Nenhum alerta no momento.")

    st.divider()

    # ---- Comparação com o mês anterior
    col_a, col_b = st.columns([1, 1])
    ref_ant = calc.mes_anterior(hoje)
    with col_a:
        st.subheader("Mês atual × mês anterior")
        comp = calc.comparacao_meses(atual, anterior)
        exibicao = pd.DataFrame({
            "Indicador": comp["indicador"],
            f"Atual ({hoje:%m/%Y})": comp["atual"].map(formatar_moeda),
            f"Anterior ({ref_ant:%m/%Y})": comp["anterior"].map(formatar_moeda),
            "Variação": comp["variacao"].map(formatar_moeda),
            "%": [("▲ " if v > 0 else "▼ " if v < 0 else "") + formatar_pct(abs(v), 1) if v is not None and v == v else "—"
                  for v in comp["variacao_pct"]],
        })
        ui.mostrar_tabela(exibicao)
    with col_b:
        base = comp[comp["indicador"].isin(["Recebido", "Gasto", "Economizado"])]
        fig = go.Figure()
        fig.add_bar(name=f"Anterior ({ref_ant:%m/%Y})", x=base["indicador"], y=base["anterior"],
                    marker_color=config.CORES["cinza"], hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.add_bar(name=f"Atual ({hoje:%m/%Y})", x=base["indicador"], y=base["atual"],
                    marker_color=config.CORES["azul"], hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.update_layout(barmode="group", title="Comparação mensal")
        ui.mostrar_grafico(fig)

    # ---- Próximos pagamentos
    st.subheader("Próximos pagamentos")
    if pendentes.empty:
        st.success("Nenhum pagamento pendente. 🎉")
    else:
        prox = pendentes.head(8).rename(columns={
            "nome": "Descrição", "valor": "Valor", "vencimento": "Vencimento",
            "categoria": "Categoria", "origem": "Origem", "situacao": "Situação"})
        estilo = ui.estilo_linhas(prox, "Situação", {"Valor": formatar_moeda, "Vencimento": formatar_data})
        ui.mostrar_tabela(estilo)
