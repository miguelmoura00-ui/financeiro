"""Ponto de entrada. Execute com:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")

import database as db  # noqa: E402
import seed  # noqa: E402
import ui  # noqa: E402
from views import (calculadora, contas, dashboard, despesas, entradas, graficos,  # noqa: E402
                   historico, planejamento, poupanca, renda)

db.inicializar()
ui.aplicar_estilo()

paginas = [
    st.Page(dashboard.render, title="Painel", icon="📊", url_path="painel", default=True),
    st.Page(entradas.render, title="Entradas", icon="💰", url_path="entradas"),
    st.Page(despesas.render, title="Despesas", icon="💸", url_path="despesas"),
    st.Page(renda.render, title="Salário e renda", icon="💼", url_path="renda"),
    st.Page(planejamento.render, title="Planejamento", icon="🎯", url_path="planejamento"),
    st.Page(poupanca.render, title="Poupança e metas", icon="🐷", url_path="poupanca"),
    st.Page(contas.render, title="Contas a pagar", icon="🧾", url_path="contas"),
    st.Page(graficos.render, title="Gráficos", icon="📈", url_path="graficos"),
    st.Page(historico.render, title="Histórico", icon="🗂️", url_path="historico"),
    st.Page(calculadora.render, title="Calculadoras", icon="🧮", url_path="calculadoras"),
]
pagina = st.navigation(paginas)

with st.sidebar:
    st.divider()
    if db.esta_vazio():
        if st.button("✨ Carregar dados de exemplo"):
            seed.popular_exemplo()
            st.rerun()
    if db.DB_PATH.exists():
        st.download_button("⬇️ Backup do banco (SQLite)", db.DB_PATH.read_bytes(),
                           file_name="financas_backup.db", mime="application/octet-stream")
    st.caption("Seus dados ficam salvos no arquivo `data/financas.db`, neste computador.")

pagina.run()
