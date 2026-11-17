"""Calculadoras financeiras."""
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import config
import ui
from formatacao import formatar_moeda, formatar_pct


def render():
    st.title("🧮 Calculadoras financeiras")
    st.caption("Simulações independentes: nada aqui é gravado nos seus dados.")

    t1, t2, t3, t4, t5 = st.tabs(["📈 Juros compostos", "🎯 Quanto guardar por mês", "🏦 Parcelamento (Price)",
                                  "⚖️ Regra 50-30-20", "🛟 Reserva de emergência"])

    with t1:
        c1, c2, c3, c4 = st.columns(4)
        capital = c1.number_input("Valor inicial (R$)", min_value=0.0, value=1000.0, step=100.0, format="%.2f", key="jc_cap")
        aporte = c2.number_input("Aporte mensal (R$)", min_value=0.0, value=300.0, step=50.0, format="%.2f", key="jc_ap")
        taxa = c3.number_input("Taxa ao mês (%)", min_value=0.0, value=0.8, step=0.1, format="%.3f", key="jc_tx")
        meses = c4.number_input("Prazo (meses)", min_value=1, max_value=600, value=24, step=1, key="jc_mes")
        df = calc.juros_compostos(capital, aporte, taxa, int(meses))
        final, investido = df["montante"].iloc[-1], df["investido"].iloc[-1]
        k = st.columns(3)
        with k[0]:
            ui.cartao("Montante final", formatar_moeda(final), "verde")
        with k[1]:
            ui.cartao("Total investido", formatar_moeda(investido), "azul")
        with k[2]:
            ui.cartao("Rendimento (juros)", formatar_moeda(final - investido), "verde",
                      f"{formatar_pct((final / investido - 1) * 100) if investido > 0 else '—'} sobre o investido")
        fig = go.Figure()
        fig.add_scatter(x=df["mes"], y=df["investido"], name="Investido", line=dict(color=config.CORES["azul"]),
                        hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.add_scatter(x=df["mes"], y=df["montante"], name="Montante", fill="tonexty",
                        line=dict(color=config.CORES["verde"]), hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.update_layout(title="Evolução do investimento", xaxis_title="Meses")
        ui.mostrar_grafico(fig)
        st.caption("Aportes feitos no fim de cada mês, taxa constante e sem impostos ou inflação.")

    with t2:
        c1, c2, c3, c4 = st.columns(4)
        meta = c1.number_input("Meta (R$)", min_value=0.0, value=10000.0, step=500.0, format="%.2f", key="am_meta")
        cap = c2.number_input("Já tenho (R$)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="am_cap")
        tx = c3.number_input("Rendimento ao mês (%)", min_value=0.0, value=0.0, step=0.1, format="%.3f", key="am_tx")
        n = c4.number_input("Prazo (meses)", min_value=1, max_value=600, value=12, step=1, key="am_n")
        ap = calc.aporte_necessario(meta, cap, tx, int(n))
        if cap >= meta and meta > 0:
            st.success("Você já tem o valor da meta! 🎉")
        else:
            ui.cartao("Guardar por mês", formatar_moeda(ap), "azul", f"durante {int(n)} mês(es)")
            st.caption(f"Total depositado: {formatar_moeda(ap * n)}"
                       + (f" · juros estimados: {formatar_moeda(meta - cap - ap * n)}" if tx > 0 else ""))

    with t3:
        c1, c2, c3 = st.columns(3)
        valor = c1.number_input("Valor financiado (R$)", min_value=0.0, value=10000.0, step=500.0, format="%.2f", key="pr_val")
        taxa_p = c2.number_input("Taxa de juros ao mês (%)", min_value=0.0, value=1.5, step=0.1, format="%.3f", key="pr_tx")
        parcelas = c3.number_input("Número de parcelas", min_value=1, max_value=480, value=12, step=1, key="pr_n")
        pmt = calc.parcela_price(valor, taxa_p, int(parcelas))
        total = pmt * parcelas
        k = st.columns(3)
        with k[0]:
            ui.cartao("Valor da parcela", formatar_moeda(pmt), "azul")
        with k[1]:
            ui.cartao("Total pago", formatar_moeda(total), "vermelho")
        with k[2]:
            ui.cartao("Juros pagos", formatar_moeda(total - valor), "vermelho")
        with st.expander("Ver tabela de amortização"):
            tab = calc.tabela_price(valor, taxa_p, int(parcelas)).rename(columns={
                "parcela": "Parcela", "valor_parcela": "Valor", "juros": "Juros",
                "amortizacao": "Amortização", "saldo_devedor": "Saldo devedor"})
            ui.mostrar_tabela(tab, column_config={c: st.column_config.NumberColumn(format="R$ %.2f")
                                                  for c in ("Valor", "Juros", "Amortização", "Saldo devedor")})

    with t4:
        renda = st.number_input("Renda mensal líquida (R$)", min_value=0.0, value=3000.0, step=100.0, format="%.2f", key="r5_renda")
        divisao = calc.regra_50_30_20(renda)
        cores = ["azul", "laranja", "verde"]
        k = st.columns(3)
        for col, (rotulo, valor), cor in zip(k, divisao.items(), cores):
            with col:
                ui.cartao(rotulo, formatar_moeda(valor), cor)
        st.caption("Sugestão: 50% para necessidades (moradia, alimentação, transporte), "
                   "30% para desejos (lazer, compras) e 20% para poupança e investimentos.")

    with t5:
        c1, c2 = st.columns(2)
        despesa = c1.number_input("Despesas mensais essenciais (R$)", min_value=0.0, value=2000.0, step=100.0,
                                  format="%.2f", key="re_desp")
        meses_r = c2.slider("Meses de cobertura", 3, 12, 6, key="re_meses")
        ui.cartao("Reserva recomendada", formatar_moeda(calc.reserva_emergencia(despesa, meses_r)), "azul",
                  f"{meses_r} meses de despesas")
        st.caption("Referência comum: de 3 a 6 meses para quem tem renda estável e até 12 para renda variável.")
