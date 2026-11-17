"""Poupança e economias."""
from datetime import date

import plotly.graph_objects as go
import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_data, formatar_moeda, formatar_pct

SEM_META = "Reserva geral (sem meta)"


def _validar_meta(nome: str, alvo: float) -> str | None:
    if not nome.strip():
        return "Dê um nome à meta."
    if alvo <= 0:
        return "O valor da meta deve ser maior que zero."
    return None


def render():
    st.title("🐷 Poupança e economias")
    ui.mostrar_flash()
    hoje = date.today()
    metas = db.carregar_df("metas", "nome ASC")
    mov = db.carregar_df("poupanca_mov", "data DESC, id DESC")
    progresso = calc.progresso_metas(metas, mov)

    saldo = calc.saldo_poupanca(mov)
    dep_mes = ret_mes = 0.0
    if not mov.empty:
        mm = calc.filtrar_mes(mov, "data", hoje)
        if not mm.empty:
            dep_mes = float(mm.loc[mm["tipo"] == config.MOV_DEPOSITO, "valor"].sum())
            ret_mes = float(mm.loc[mm["tipo"] == config.MOV_RETIRADA, "valor"].sum())
    meta_mensal = float(metas["valor_mensal"].sum()) if not metas.empty else 0.0

    c = st.columns(4)
    with c[0]:
        ui.cartao("Saldo acumulado", formatar_moeda(saldo), "azul", "total guardado")
    with c[1]:
        ui.cartao(f"Depositado em {hoje:%m/%Y}", formatar_moeda(dep_mes), "verde")
    with c[2]:
        ui.cartao(f"Retirado em {hoje:%m/%Y}", formatar_moeda(ret_mes), "vermelho")
    with c[3]:
        ui.cartao("Meta mensal de economia", formatar_moeda(meta_mensal), "laranja",
                  f"{formatar_pct(dep_mes / meta_mensal * 100, 0)} atingido no mês" if meta_mensal > 0 else "defina nas metas")

    tab_mov, tab_metas, tab_hist = st.tabs(["💵 Depositar / retirar", "🎯 Metas e objetivos", "📜 Histórico"])

    # --------------------------------------------------------------- movimentação
    with tab_mov:
        destinos = {None: SEM_META}
        destinos.update({int(r.id): r.nome for r in metas.itertuples()})
        with st.form("form_mov", clear_on_submit=True):
            c1, c2 = st.columns(2)
            tipo = c1.radio("Operação", config.TIPOS_POUPANCA, horizontal=True, key="mv_tipo")
            valor = c2.number_input("Valor (R$)", min_value=0.0, step=50.0, format="%.2f", key="mv_valor")
            c3, c4 = st.columns(2)
            destino = c3.selectbox("Meta", list(destinos), format_func=destinos.get, key="mv_meta")
            data = c4.date_input("Data", value=hoje, format="DD/MM/YYYY", key="mv_data")
            descricao = st.text_input("Descrição (opcional)", key="mv_desc")
            if st.form_submit_button("💾 Registrar", type="primary"):
                disponivel = calc.saldo_poupanca(mov, destino)
                if valor <= 0:
                    st.error("O valor deve ser maior que zero.")
                elif tipo == config.MOV_RETIRADA and valor > disponivel + 1e-9:
                    st.error(f"Saldo insuficiente em «{destinos[destino]}»: disponível {formatar_moeda(disponivel)}.")
                else:
                    db.inserir("poupanca_mov", {"data": data, "tipo": tipo, "valor": valor,
                                                "meta_id": destino, "descricao": descricao.strip()})
                    ui.flash(f"{tipo} de {formatar_moeda(valor)} registrado(a).")
                    st.rerun()

    # ---------------------------------------------------------------------- metas
    with tab_metas:
        if progresso.empty:
            st.info("Crie sua primeira meta abaixo: um computador, uma viagem, uma reserva de emergência…")
        for r in progresso.itertuples():
            cor = "verde" if r.pct >= 100 else "azul"
            direita = f"{formatar_pct(r.pct, 0)} · faltam {formatar_moeda(r.falta)}" if r.falta > 0 else "✅ meta atingida!"
            ui.barra_progresso(r.pct, cor, f"{r.nome}: {formatar_moeda(r.atual)} de {formatar_moeda(r.valor_alvo)}", direita)
            detalhes = []
            if r.prazo is not None and r.prazo == r.prazo:  # prazo não vazio
                dias = (r.prazo.date() - hoje).days
                detalhes.append(f"prazo {formatar_data(r.prazo)}" + (f" ({dias} dias)" if dias >= 0 else " (vencido)"))
            if r.falta > 0:
                meses = calc.meses_para_meta(r.falta, r.valor_mensal)
                if meses is not None:
                    detalhes.append(f"guardando {formatar_moeda(r.valor_mensal)}/mês: cerca de {meses} mês(es)")
            if detalhes:
                st.caption(" · ".join(detalhes))

        st.divider()
        st.markdown("**Nova meta**")
        with st.form("form_nova_meta", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Objetivo", placeholder="Ex.: Comprar um computador", key="nm_nome")
            alvo = c2.number_input("Valor da meta (R$)", min_value=0.0, step=100.0, format="%.2f", key="nm_alvo")
            c3, c4 = st.columns(2)
            mensal = c3.number_input("Quanto guardar por mês (R$)", min_value=0.0, step=50.0, format="%.2f", key="nm_mensal")
            usar_prazo = c4.checkbox("Definir prazo", key="nm_usar_prazo")
            prazo = c4.date_input("Prazo", value=date(hoje.year + 1, hoje.month, 1), format="DD/MM/YYYY", key="nm_prazo")
            if st.form_submit_button("💾 Criar meta", type="primary"):
                erro = _validar_meta(nome, alvo)
                if erro:
                    st.error(erro)
                else:
                    db.inserir("metas", {"nome": nome.strip(), "valor_alvo": alvo, "valor_mensal": mensal,
                                         "prazo": prazo if usar_prazo else None})
                    ui.flash("Meta criada!")
                    st.rerun()

        if not metas.empty:
            st.markdown("**Editar ou excluir meta**")
            reg = ui.selecionar_registro(metas, lambda r: f"{r['nome']} · {formatar_moeda(r['valor_alvo'])}",
                                         "sel_meta", "Meta")
            if reg is not None:
                rid = int(reg["id"])
                tem_prazo = reg["prazo"] == reg["prazo"]  # False se NaT
                with st.form(f"form_edit_meta_{rid}"):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Objetivo", value=reg["nome"], key=f"em{rid}_nome")
                    alvo = c2.number_input("Valor da meta (R$)", min_value=0.0, step=100.0, format="%.2f",
                                           value=float(reg["valor_alvo"]), key=f"em{rid}_alvo")
                    c3, c4 = st.columns(2)
                    mensal = c3.number_input("Guardar por mês (R$)", min_value=0.0, step=50.0, format="%.2f",
                                             value=float(reg["valor_mensal"]), key=f"em{rid}_mensal")
                    usar_prazo = c4.checkbox("Definir prazo", value=bool(tem_prazo), key=f"em{rid}_usar")
                    prazo = c4.date_input("Prazo", value=reg["prazo"].date() if tem_prazo else hoje,
                                          format="DD/MM/YYYY", key=f"em{rid}_prazo")
                    st.caption("Ao excluir a meta, o dinheiro depositado continua no saldo como reserva geral.")
                    confirma = st.checkbox("Confirmo a exclusão desta meta", key=f"em{rid}_conf")
                    b1, b2 = st.columns(2)
                    salvar = b1.form_submit_button("💾 Salvar alterações", type="primary")
                    excluir = b2.form_submit_button("🗑️ Excluir meta")
                if salvar:
                    erro = _validar_meta(nome, alvo)
                    if erro:
                        st.error(erro)
                    else:
                        db.atualizar("metas", rid, {"nome": nome.strip(), "valor_alvo": alvo, "valor_mensal": mensal,
                                                    "prazo": prazo if usar_prazo else None})
                        ui.flash("Meta atualizada.")
                        st.rerun()
                if excluir:
                    if confirma:
                        db.excluir("metas", rid)
                        ui.flash("Meta excluída.")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")

    # ------------------------------------------------------------------ histórico
    with tab_hist:
        if mov.empty:
            st.info("Nenhuma movimentação registrada.")
        else:
            nomes = {int(r.id): r.nome for r in metas.itertuples()}
            t = mov.copy()
            t["Meta"] = [nomes.get(int(m), SEM_META) if m == m else SEM_META for m in t["meta_id"]]
            t = t.rename(columns={"data": "Data", "tipo": "Operação", "valor": "Valor", "descricao": "Descrição"})
            ui.mostrar_tabela(t[["Data", "Operação", "Valor", "Meta", "Descrição"]],
                              column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                             "Valor": st.column_config.NumberColumn(format="R$ %.2f")})
            serie = calc.serie_economias(mov, mov["data"].min().date(), max(hoje, mov["data"].max().date()), "M")
            fig = go.Figure(go.Scatter(x=calc.rotulos_periodo(serie.index, "M"), y=serie.values, fill="tozeroy",
                                       mode="lines", line_color=config.CORES["azul"],
                                       hovertemplate="R$ %{y:,.2f}<extra></extra>"))
            fig.update_layout(title="Evolução do dinheiro guardado")
            ui.mostrar_grafico(fig)
