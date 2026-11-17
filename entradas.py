"""Controle de entradas de dinheiro."""
from datetime import date

import streamlit as st

import calculos as calc
import config
import database as db
import ui
from formatacao import formatar_moeda


def _validar(descricao: str, valor: float) -> str | None:
    if not descricao.strip():
        return "Informe o nome ou a descrição da entrada."
    if valor <= 0:
        return "O valor deve ser maior que zero."
    return None


def render():
    st.title("💰 Entradas de dinheiro")
    ui.mostrar_flash()
    hoje = date.today()
    df = db.carregar_df("entradas", "data DESC, id DESC")

    mes = calc.filtrar_mes(df, "data", hoje)
    ano = df[df["data"].dt.year == hoje.year] if not df.empty else df
    c = st.columns(3)
    with c[0]:
        ui.cartao(f"Entradas em {hoje:%m/%Y}", formatar_moeda(mes["valor"].sum() if not mes.empty else 0), "verde")
    with c[1]:
        ui.cartao(f"Entradas em {hoje.year}", formatar_moeda(ano["valor"].sum() if not ano.empty else 0), "verde")
    with c[2]:
        ui.cartao("Total registrado", formatar_moeda(df["valor"].sum() if not df.empty else 0), "azul",
                  f"{len(df)} registro(s)")

    tab_nova, tab_editar, tab_lista, tab_totais = st.tabs(
        ["➕ Nova entrada", "✏️ Editar / excluir", "📋 Consultar", "📅 Totais por mês e ano"])

    with tab_nova:
        with st.form("form_nova_entrada", clear_on_submit=True):
            c1, c2 = st.columns(2)
            descricao = c1.text_input("Nome ou descrição", key="ne_desc")
            valor = c2.number_input("Valor recebido (R$)", min_value=0.0, step=50.0, format="%.2f", key="ne_valor")
            c3, c4 = st.columns(2)
            categoria = c3.selectbox("Categoria", config.CATEGORIAS_ENTRADA, key="ne_cat")
            data = c4.date_input("Data do recebimento", value=hoje, format="DD/MM/YYYY", key="ne_data")
            origem = st.text_input("Origem do dinheiro", placeholder="Ex.: Empresa X, cliente Y", key="ne_origem")
            obs = st.text_area("Observações (opcional)", key="ne_obs")
            if st.form_submit_button("💾 Salvar entrada", type="primary"):
                erro = _validar(descricao, valor)
                if erro:
                    st.error(erro)
                else:
                    db.inserir("entradas", {"descricao": descricao.strip(), "valor": valor, "categoria": categoria,
                                            "data": data, "origem": origem.strip(), "observacoes": obs.strip()})
                    ui.flash("Entrada cadastrada com sucesso!")
                    st.rerun()

    with tab_editar:
        reg = ui.selecionar_registro(
            df, lambda r: f"{r['data']:%d/%m/%Y} · {r['descricao']} · {formatar_moeda(r['valor'])}", "sel_entrada")
        if reg is not None:
            rid = int(reg["id"])
            with st.form(f"form_edit_entrada_{rid}"):
                c1, c2 = st.columns(2)
                descricao = c1.text_input("Nome ou descrição", value=reg["descricao"], key=f"ee{rid}_desc")
                valor = c2.number_input("Valor recebido (R$)", min_value=0.0, step=50.0, format="%.2f",
                                        value=float(reg["valor"]), key=f"ee{rid}_valor")
                c3, c4 = st.columns(2)
                cats = config.CATEGORIAS_ENTRADA if reg["categoria"] in config.CATEGORIAS_ENTRADA \
                    else config.CATEGORIAS_ENTRADA + [reg["categoria"]]
                categoria = c3.selectbox("Categoria", cats, index=ui.indice(cats, reg["categoria"]), key=f"ee{rid}_cat")
                data = c4.date_input("Data do recebimento", value=reg["data"].date(), format="DD/MM/YYYY", key=f"ee{rid}_data")
                origem = st.text_input("Origem do dinheiro", value=reg["origem"] or "", key=f"ee{rid}_origem")
                obs = st.text_area("Observações (opcional)", value=reg["observacoes"] or "", key=f"ee{rid}_obs")
                confirma = st.checkbox("Confirmo a exclusão deste registro", key=f"ee{rid}_conf")
                b1, b2 = st.columns(2)
                salvar = b1.form_submit_button("💾 Salvar alterações", type="primary")
                excluir = b2.form_submit_button("🗑️ Excluir registro")
            if salvar:
                erro = _validar(descricao, valor)
                if erro:
                    st.error(erro)
                else:
                    db.atualizar("entradas", rid, {"descricao": descricao.strip(), "valor": valor,
                                                   "categoria": categoria, "data": data,
                                                   "origem": origem.strip(), "observacoes": obs.strip()})
                    ui.flash("Entrada atualizada.")
                    st.rerun()
            if excluir:
                if confirma:
                    db.excluir("entradas", rid)
                    ui.flash("Entrada excluída.")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

    with tab_lista:
        if df.empty:
            st.info("Nenhuma entrada cadastrada.")
        else:
            f1, f2 = st.columns(2)
            cats = f1.multiselect("Categoria", config.CATEGORIAS_ENTRADA)
            busca = f2.text_input("Buscar na descrição ou origem")
            vis = df
            if cats:
                vis = vis[vis["categoria"].isin(cats)]
            if busca:
                alvo = (vis["descricao"].fillna("") + " " + vis["origem"].fillna("")).str.contains(busca, case=False, regex=False)
                vis = vis[alvo]
            tabela = vis.drop(columns=["id"]).rename(columns={
                "descricao": "Descrição", "valor": "Valor", "categoria": "Categoria", "data": "Data",
                "origem": "Origem", "observacoes": "Observações"})
            ui.mostrar_tabela(tabela[["Data", "Descrição", "Valor", "Categoria", "Origem", "Observações"]],
                              column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                             "Valor": st.column_config.NumberColumn(format="R$ %.2f")})
            st.caption(f"{len(vis)} registro(s) · total {formatar_moeda(vis['valor'].sum())}")

    with tab_totais:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Por mês**")
            tm = calc.totais_por_mes(df)
            ui.mostrar_tabela(tm.rename(columns={"mes": "Mês", "total": "Total"}),
                              column_config={"Total": st.column_config.NumberColumn(format="R$ %.2f")})
        with c2:
            st.markdown("**Por ano**")
            ta = calc.totais_por_ano(df)
            ui.mostrar_tabela(ta.rename(columns={"ano": "Ano", "total": "Total"}),
                              column_config={"Total": st.column_config.NumberColumn(format="R$ %.2f")})
