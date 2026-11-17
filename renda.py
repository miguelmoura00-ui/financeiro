"""Gerenciamento de salário e renda."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_data, formatar_moeda, formatar_pct


def _validar(nome: str, valor: float) -> str | None:
    if not nome.strip():
        return "Informe o nome da fonte de renda."
    if valor <= 0:
        return "O valor deve ser maior que zero."
    return None


def render():
    st.title("💼 Salário e renda")
    ui.mostrar_flash()
    hoje = date.today()
    rendas = db.carregar_df("rendas", "tipo ASC, valor DESC")
    entradas = db.carregar_df("entradas", "data DESC")
    despesas = db.carregar_df("despesas")
    ativas = rendas[rendas["ativa"] == 1] if not rendas.empty else rendas

    total = float(ativas["valor"].sum()) if not ativas.empty else 0.0
    principal = float(ativas.loc[ativas["tipo"] == config.RENDA_PRINCIPAL, "valor"].sum()) if not ativas.empty else 0.0
    secundaria = total - principal
    resumo = calc.resumo_mes(entradas, despesas, hoje, total)
    comprometido = (resumo["gasto"] + resumo["pendentes"])

    c = st.columns(4)
    with c[0]:
        ui.cartao("Renda total mensal", formatar_moeda(total), "verde", "todas as fontes ativas")
    with c[1]:
        ui.cartao("Renda principal", formatar_moeda(principal), "azul")
    with c[2]:
        ui.cartao("Renda secundária", formatar_moeda(secundaria), "azul")
    with c[3]:
        sobra = total - comprometido
        ui.cartao("Renda − despesas do mês", formatar_moeda(sobra), "verde" if sobra >= 0 else "vermelho",
                  "considera despesas pagas e pendentes")

    tab_fontes, tab_receber, tab_comp, tab_hist = st.tabs(
        ["🧾 Fontes de renda", "📥 Registrar recebimento", "⚖️ Renda × despesas", "📈 Histórico"])

    # ------------------------------------------------------------------ fontes
    with tab_fontes:
        st.markdown("**Cadastrar nova fonte de renda**")
        with st.form("form_nova_renda", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome (ex.: Salário, Freelance)", key="nr_nome")
            valor = c2.number_input("Quanto recebe por mês (R$)", min_value=0.0, step=100.0, format="%.2f", key="nr_valor")
            c3, c4 = st.columns(2)
            tipo = c3.selectbox("Tipo", config.TIPOS_RENDA, key="nr_tipo")
            dia = c4.number_input("Dia em que costuma receber", min_value=1, max_value=31, value=5, step=1, key="nr_dia")
            if st.form_submit_button("💾 Cadastrar fonte", type="primary"):
                erro = _validar(nome, valor)
                if erro:
                    st.error(erro)
                else:
                    db.criar_renda({"nome": nome.strip(), "valor": valor, "tipo": tipo,
                                    "dia_recebimento": int(dia), "ativa": 1}, hoje)
                    ui.flash("Fonte de renda cadastrada!")
                    st.rerun()

        st.divider()
        if rendas.empty:
            st.info("Nenhuma fonte de renda cadastrada.")
        else:
            tabela = rendas.copy()
            tabela["Próximo recebimento"] = [calc.proximo_recebimento(int(d), hoje) if a == 1 else None
                                             for d, a in zip(tabela["dia_recebimento"], tabela["ativa"])]
            tabela["ativa"] = tabela["ativa"].map({1: "Sim", 0: "Não"})
            tabela["Próximo recebimento"] = pd.to_datetime(tabela["Próximo recebimento"])
            tabela = tabela.rename(columns={"nome": "Fonte", "valor": "Valor mensal", "tipo": "Tipo",
                                            "dia_recebimento": "Dia do recebimento", "ativa": "Ativa"})
            ui.mostrar_tabela(tabela[["Fonte", "Tipo", "Valor mensal", "Dia do recebimento", "Próximo recebimento", "Ativa"]],
                              column_config={"Valor mensal": st.column_config.NumberColumn(format="R$ %.2f"),
                                             "Próximo recebimento": st.column_config.DateColumn(format="DD/MM/YYYY")})

            st.markdown("**Editar ou excluir**")
            reg = ui.selecionar_registro(rendas, lambda r: f"{r['nome']} · {r['tipo']} · {formatar_moeda(r['valor'])}",
                                         "sel_renda", "Fonte de renda")
            if reg is not None:
                rid = int(reg["id"])
                with st.form(f"form_edit_renda_{rid}"):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Nome", value=reg["nome"], key=f"er{rid}_nome")
                    valor = c2.number_input("Valor mensal (R$)", min_value=0.0, step=100.0, format="%.2f",
                                            value=float(reg["valor"]), key=f"er{rid}_valor")
                    c3, c4, c5 = st.columns(3)
                    tipo = c3.selectbox("Tipo", config.TIPOS_RENDA, index=ui.indice(config.TIPOS_RENDA, reg["tipo"]),
                                        key=f"er{rid}_tipo")
                    dia = c4.number_input("Dia do recebimento", min_value=1, max_value=31,
                                          value=int(reg["dia_recebimento"]), step=1, key=f"er{rid}_dia")
                    ativa = c5.checkbox("Fonte ativa", value=bool(reg["ativa"]), key=f"er{rid}_ativa")
                    st.caption("Se o valor mudar, a alteração fica registrada no histórico de renda.")
                    confirma = st.checkbox("Confirmo a exclusão desta fonte (o histórico dela também será apagado)",
                                           key=f"er{rid}_conf")
                    b1, b2 = st.columns(2)
                    salvar = b1.form_submit_button("💾 Salvar alterações", type="primary")
                    excluir = b2.form_submit_button("🗑️ Excluir fonte")
                if salvar:
                    erro = _validar(nome, valor)
                    if erro:
                        st.error(erro)
                    else:
                        db.atualizar_renda(rid, {"nome": nome.strip(), "valor": valor, "tipo": tipo,
                                                 "dia_recebimento": int(dia), "ativa": int(ativa)}, hoje)
                        ui.flash("Fonte de renda atualizada.")
                        st.rerun()
                if excluir:
                    if confirma:
                        db.excluir("rendas", rid)
                        ui.flash("Fonte de renda excluída.")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")

    # --------------------------------------------------------------- recebimento
    with tab_receber:
        st.markdown(f"Registre o recebimento de **{hoje:%m/%Y}** com um clique. "
                    "O valor entra na lista de entradas, na data habitual de cada fonte.")
        if ativas.empty:
            st.info("Cadastre uma fonte de renda para usar este atalho.")
        for r in ativas.itertuples():
            data = calc.data_no_mes(hoje.year, hoje.month, int(r.dia_recebimento))
            descricao = f"{r.nome} - {hoje:%m/%Y}"
            ja = (not entradas.empty) and bool((entradas["descricao"] == descricao).any())
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{r.nome}** ({r.tipo}) · {formatar_moeda(r.valor)} · dia {formatar_data(data)}"
                        + ("  ✅ já registrado" if ja else ""))
            if c2.button("Registrar", key=f"receber_{r.id}", disabled=ja):
                categoria = "Salário" if r.tipo == config.RENDA_PRINCIPAL else "Renda extra"
                db.inserir("entradas", {"descricao": descricao, "valor": r.valor, "categoria": categoria,
                                        "data": data, "origem": r.nome, "observacoes": "Lançado pelo atalho de renda"})
                ui.flash(f"Recebimento de {r.nome} registrado.")
                st.rerun()

    # ---------------------------------------------------------------- comparação
    with tab_comp:
        base = total if total > 0 else resumo["recebido"]
        st.markdown(f"**{hoje:%m/%Y}: quanto da renda já está comprometido**")
        if base > 0:
            pct = comprometido / base * 100
            ui.barra_progresso(pct, "vermelho" if pct > 100 else "laranja" if pct >= 80 else "verde",
                               f"Despesas: {formatar_moeda(comprometido)}",
                               f"{formatar_pct(pct)} de {formatar_moeda(base)}")
        else:
            st.info("Cadastre uma fonte de renda ou uma entrada para ver a comparação.")

        fim_mes = hoje
        inicio, _ = calc.intervalo_periodo(config.PERIODO_6M, hoje)
        inicio = inicio.replace(day=1)
        rec = calc.serie_agrupada(entradas, "data", "valor", inicio, fim_mes, "M")
        pag = despesas[despesas["status"] == config.STATUS_PAGO] if not despesas.empty else despesas
        gas = calc.serie_agrupada(pag, "data", "valor", inicio, fim_mes, "M")
        rot = calc.rotulos_periodo(rec.index, "M")
        fig = go.Figure()
        fig.add_bar(name="Renda recebida", x=rot, y=rec.values, marker_color=config.CORES["verde"],
                    hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.add_bar(name="Despesas pagas", x=rot, y=gas.values, marker_color=config.CORES["vermelho"],
                    hovertemplate="R$ %{y:,.2f}<extra></extra>")
        fig.update_layout(barmode="group", title="Renda × despesas (últimos 6 meses)")
        ui.mostrar_grafico(fig)

    # ----------------------------------------------------------------- histórico
    with tab_hist:
        st.markdown("**Salários recebidos**")
        salarios = entradas[entradas["categoria"] == "Salário"] if not entradas.empty else entradas
        if salarios.empty:
            st.info("Nenhum salário registrado ainda (categoria *Salário* em Entradas).")
        else:
            t = salarios[["data", "descricao", "valor", "origem"]].rename(
                columns={"data": "Data", "descricao": "Descrição", "valor": "Valor", "origem": "Origem"})
            ui.mostrar_tabela(t, column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                                "Valor": st.column_config.NumberColumn(format="R$ %.2f")})
            st.caption(f"{len(salarios)} recebimento(s) · média {formatar_moeda(salarios['valor'].mean())}")

        st.markdown("**Alterações na renda ao longo do tempo**")
        hist = db.carregar_df("renda_historico", "data ASC, id ASC")
        if hist.empty or rendas.empty:
            st.info("O histórico aparece quando você cadastra ou altera uma fonte de renda.")
        else:
            nomes = dict(zip(rendas["id"], rendas["nome"]))
            fig = go.Figure()
            for rid, grupo in hist.groupby("renda_id"):
                fig.add_trace(go.Scatter(x=grupo["data"], y=grupo["valor"], mode="lines+markers",
                                         line_shape="hv", name=nomes.get(rid, f"Fonte {rid}"),
                                         hovertemplate="R$ %{y:,.2f}<extra></extra>"))
            fig.update_layout(title="Evolução do valor de cada fonte de renda")
            ui.mostrar_grafico(fig)
