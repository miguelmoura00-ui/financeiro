"""Planejamento financeiro mensal."""
from datetime import date

import pandas as pd
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_moeda, formatar_pct

ROTULO_NIVEL = {"ok": "dentro do limite", "atencao": "perto do limite", "estourado": "limite ultrapassado"}


def _opcoes_meses(hoje: date) -> list[str]:
    base = pd.Timestamp(hoje.replace(day=1))
    return [(base + pd.DateOffset(months=d)).strftime("%Y-%m") for d in range(3, -13, -1)]


def render():
    st.title("🎯 Planejamento mensal")
    ui.mostrar_flash()
    hoje = date.today()

    meses = _opcoes_meses(hoje)
    mes = st.selectbox("Mês do planejamento", meses, index=meses.index(hoje.strftime("%Y-%m")),
                       format_func=lambda m: f"{m[5:]}/{m[:4]}")
    ref = date(int(mes[:4]), int(mes[5:]), 1)

    plano = db.obter_planejamento(mes)
    limites_salvos = db.obter_limites(mes)
    rendas = db.carregar_df("rendas")
    renda_cadastrada = float(rendas.loc[rendas["ativa"] == 1, "valor"].sum()) if not rendas.empty else 0.0
    if plano is None:
        plano = {"renda_prevista": renda_cadastrada, "limite_gastos": 0.0, "poupanca": 0.0,
                 "investimentos": 0.0, "emergencia": 0.0}
        st.info("Ainda não há planejamento para este mês. Preencha os valores abaixo e salve.")

    # ------------------------------------------------------------------ formulário
    with st.form(f"form_plano_{mes}"):
        st.markdown("**Visão geral do mês**")
        c1, c2 = st.columns(2)
        renda_prev = c1.number_input("Renda prevista (R$)", min_value=0.0, step=100.0, format="%.2f",
                                     value=float(plano["renda_prevista"]), key=f"pl{mes}_renda")
        limite_total = c2.number_input("Limite de gastos mensais (R$)", min_value=0.0, step=100.0, format="%.2f",
                                       value=float(plano["limite_gastos"]), key=f"pl{mes}_limite")
        c3, c4, c5 = st.columns(3)
        poup = c3.number_input("Destinado à poupança (R$)", min_value=0.0, step=50.0, format="%.2f",
                               value=float(plano["poupanca"]), key=f"pl{mes}_poup")
        invest = c4.number_input("Destinado a investimentos (R$)", min_value=0.0, step=50.0, format="%.2f",
                                 value=float(plano["investimentos"]), key=f"pl{mes}_inv")
        emerg = c5.number_input("Reserva para emergências (R$)", min_value=0.0, step=50.0, format="%.2f",
                                value=float(plano["emergencia"]), key=f"pl{mes}_emerg")
        st.markdown("**Limite de gastos por categoria** (0 = sem limite)")
        limites = {}
        colunas = st.columns(3)
        for i, cat in enumerate(config.CATEGORIAS_DESPESA):
            limites[cat] = colunas[i % 3].number_input(
                cat, min_value=0.0, step=50.0, format="%.2f",
                value=float(limites_salvos.get(cat, 0.0)), key=f"pl{mes}_cat_{cat}")
        if st.form_submit_button("💾 Salvar planejamento", type="primary"):
            db.salvar_planejamento(mes, {"renda_prevista": renda_prev, "limite_gastos": limite_total,
                                         "poupanca": poup, "investimentos": invest, "emergencia": emerg}, limites)
            ui.flash("Planejamento salvo!")
            st.rerun()

    # ---------------------------------------------------- distribuição do dinheiro
    plano = db.obter_planejamento(mes)
    if plano is None:
        return
    limites = db.obter_limites(mes)
    soma_cat = sum(limites.values())
    alocado = soma_cat + plano["poupanca"] + plano["investimentos"] + plano["emergencia"]
    livre = plano["renda_prevista"] - alocado

    st.subheader("Distribuição do dinheiro planejado")
    c = st.columns(4)
    with c[0]:
        ui.cartao("Renda prevista", formatar_moeda(plano["renda_prevista"]), "azul")
    with c[1]:
        ui.cartao("Limites por categoria", formatar_moeda(soma_cat), "vermelho", "soma dos limites")
    with c[2]:
        ui.cartao("Poupança + investimentos + reserva",
                  formatar_moeda(plano["poupanca"] + plano["investimentos"] + plano["emergencia"]), "verde")
    with c[3]:
        ui.cartao("Ainda não destinado", formatar_moeda(livre), "verde" if livre >= 0 else "vermelho",
                  "renda prevista − tudo que foi planejado")
    if livre < 0:
        st.error(f"⚠️ O planejamento soma {formatar_moeda(alocado)}, acima da renda prevista em {formatar_moeda(-livre)}.")
    if plano["limite_gastos"] > 0 and soma_cat > plano["limite_gastos"]:
        st.warning(f"A soma dos limites por categoria ({formatar_moeda(soma_cat)}) passa do limite de gastos mensais "
                   f"({formatar_moeda(plano['limite_gastos'])}).")

    # --------------------------------------------------- planejado × realizado
    entradas = db.carregar_df("entradas")
    despesas = db.carregar_df("despesas")
    mov = db.carregar_df("poupanca_mov")
    resumo = calc.resumo_mes(entradas, despesas, ref)
    comprometido = resumo["gasto"] + resumo["pendentes"]
    depositado = 0.0
    if not mov.empty:
        mm = calc.filtrar_mes(mov, "data", ref)
        if not mm.empty:
            depositado = float(mm.loc[mm["tipo"] == config.MOV_DEPOSITO, "valor"].sum())

    st.subheader("Planejado × realizado")
    if plano["renda_prevista"] > 0:
        pct = resumo["recebido"] / plano["renda_prevista"] * 100
        ui.barra_progresso(pct, "verde", f"Renda recebida: {formatar_moeda(resumo['recebido'])}",
                           f"{formatar_pct(pct, 0)} da renda prevista")
    if plano["limite_gastos"] > 0:
        pct = comprometido / plano["limite_gastos"] * 100
        nivel = "estourado" if pct > 100 else "atencao" if pct >= config.LIMITE_ALERTA_ORCAMENTO * 100 else "ok"
        ui.barra_progresso(pct, ui.cor_nivel(nivel),
                           f"Gasto (pago + pendente): {formatar_moeda(comprometido)}",
                           f"{formatar_pct(pct, 0)} do limite · disponível {formatar_moeda(plano['limite_gastos'] - comprometido)}")
        if nivel == "estourado":
            st.error("🚨 O limite total de gastos do mês foi ultrapassado.")
        elif nivel == "atencao":
            st.warning("🔔 Você já usou mais de 80% do limite total de gastos do mês.")
    if plano["poupanca"] > 0:
        pct = depositado / plano["poupanca"] * 100
        ui.barra_progresso(pct, "azul", f"Depositado na poupança: {formatar_moeda(depositado)}",
                           f"{formatar_pct(pct, 0)} do planejado ({formatar_moeda(plano['poupanca'])})")

    # ------------------------------------------------------------ por categoria
    st.subheader("Orçamento por categoria")
    if not limites:
        st.info("Defina limites por categoria no formulário acima para acompanhar o orçamento.")
        return
    orc = calc.status_orcamento(limites, despesas, ref)
    for r in orc.sort_values("pct", ascending=False).itertuples():
        ui.barra_progresso(r.pct, ui.cor_nivel(r.nivel), f"{r.categoria} — {ROTULO_NIVEL[r.nivel]}",
                           f"{formatar_moeda(r.gasto)} de {formatar_moeda(r.limite)} · "
                           + (f"disponível {formatar_moeda(r.restante)}" if r.restante >= 0
                              else f"excedeu {formatar_moeda(-r.restante)}"))
    estourados = orc[orc["nivel"] == "estourado"]
    atencao = orc[orc["nivel"] == "atencao"]
    if not estourados.empty:
        st.error("🚨 Limite ultrapassado em: " + ", ".join(estourados["categoria"]))
    if not atencao.empty:
        st.warning("🔔 Perto do limite (80% ou mais): " + ", ".join(atencao["categoria"]))
    st.caption("O orçamento considera despesas pagas e pendentes do mês, pois ambas já comprometem o dinheiro.")
