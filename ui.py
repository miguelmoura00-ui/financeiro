"""Componentes visuais reutilizáveis (Streamlit)."""
from __future__ import annotations

import html
import inspect
from datetime import date

import streamlit as st

import calculos as calc
import config
from formatacao import formatar_moeda

CSS = """
<style>
.block-container { padding-top: 2rem; padding-bottom: 3rem; }
.fin-card {
    background: rgba(128, 128, 128, 0.08);
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-left: 6px solid #2563eb;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
    min-height: 112px;
}
.fin-card-titulo { font-size: 0.78rem; letter-spacing: .04em; text-transform: uppercase; opacity: .75; }
.fin-card-valor  { font-size: 1.7rem; font-weight: 700; line-height: 1.25; margin: 2px 0; word-break: break-word; }
.fin-card-legenda { font-size: 0.8rem; opacity: .7; }
.fin-barra-rotulo { display: flex; justify-content: space-between; font-size: .88rem; margin: 10px 0 3px; }
.fin-barra { background: rgba(128, 128, 128, 0.22); border-radius: 8px; height: 12px; overflow: hidden; }
.fin-barra-fill { height: 100%; border-radius: 8px; }
</style>
"""

CORES_LINHA = {
    config.MOV_ENTRADA: "rgba(22, 163, 74, 0.16)",
    config.MOV_SAIDA: "rgba(220, 38, 38, 0.16)",
    config.MOV_POUP_DEP: "rgba(37, 99, 235, 0.16)",
    config.MOV_POUP_RET: "rgba(37, 99, 235, 0.16)",
    config.SIT_ATRASADA: "rgba(220, 38, 38, 0.18)",
    config.SIT_PROXIMA: "rgba(245, 158, 11, 0.22)",
    config.SIT_PAGA: "rgba(22, 163, 74, 0.14)",
}


def aplicar_estilo() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def cartao(titulo: str, valor: str, cor: str = "azul", legenda: str = "") -> None:
    c = config.CORES.get(cor, cor)
    st.markdown(
        f'<div class="fin-card" style="border-left-color:{c}">'
        f'<div class="fin-card-titulo">{html.escape(titulo)}</div>'
        f'<div class="fin-card-valor" style="color:{c}">{html.escape(valor)}</div>'
        f'<div class="fin-card-legenda">{html.escape(legenda)}&nbsp;</div></div>',
        unsafe_allow_html=True,
    )


def barra_progresso(pct: float, cor: str, esquerda: str = "", direita: str = "") -> None:
    largura = max(0.0, min(float(pct), 100.0))
    c = config.CORES.get(cor, cor)
    st.markdown(
        f'<div class="fin-barra-rotulo"><span>{html.escape(esquerda)}</span><span>{html.escape(direita)}</span></div>'
        f'<div class="fin-barra"><div class="fin-barra-fill" style="width:{largura:.1f}%;background:{c}"></div></div>',
        unsafe_allow_html=True,
    )


def cor_nivel(nivel: str) -> str:
    return {"ok": "verde", "atencao": "laranja", "estourado": "vermelho"}.get(nivel, "azul")


# --------------------------------------------------------------------------
# Mensagens que sobrevivem ao st.rerun()
# --------------------------------------------------------------------------
def flash(mensagem: str, tipo: str = "success") -> None:
    st.session_state["_flash"] = (tipo if tipo in ("success", "error", "warning", "info") else "info", mensagem)


def mostrar_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        getattr(st, item[0])(item[1])


# --------------------------------------------------------------------------
# Compatibilidade entre versões do Streamlit (largura total)
# --------------------------------------------------------------------------
def _largura_total(funcao) -> dict:
    params = inspect.signature(funcao).parameters
    largura = params.get("width")
    if largura is not None and isinstance(largura.default, str):
        return {"width": "stretch"}              # API nova
    if "use_container_width" in params:
        return {"use_container_width": True}     # API antiga
    return {}


def mostrar_grafico(fig, **kwargs) -> None:
    fig.update_layout(
        separators=",.",  # decimal com vírgula e milhar com ponto
        margin=dict(l=10, r=10, t=55, b=10),
        height=370,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig, **_largura_total(st.plotly_chart), **kwargs)


def mostrar_tabela(df, **kwargs) -> None:
    kwargs.setdefault("hide_index", True)
    st.dataframe(df, **_largura_total(st.dataframe), **kwargs)


# --------------------------------------------------------------------------
# Entradas de formulário auxiliares
# --------------------------------------------------------------------------
def indice(lista: list, valor, padrao: int = 0) -> int:
    try:
        return lista.index(valor)
    except ValueError:
        return padrao


def selecionar_registro(df, rotulo_fn, chave: str, titulo: str = "Selecione o registro"):
    """Selectbox de registros; devolve a linha escolhida (Series) ou None."""
    if df.empty:
        st.info("Nenhum registro cadastrado ainda.")
        return None
    opcoes = {int(r["id"]): rotulo_fn(r) for _, r in df.iterrows()}
    escolhido = st.selectbox(titulo, list(opcoes), format_func=opcoes.get, key=chave)
    return df[df["id"] == escolhido].iloc[0]


def seletor_periodo(chave: str, padrao: str = config.PERIODO_30D):
    """Seletor de período; devolve (inicio, fim, nome) ou interrompe a página se incompleto."""
    hoje = date.today()
    nome = st.selectbox("Período", config.PERIODOS, index=config.PERIODOS.index(padrao), key=f"{chave}_periodo")
    inicio = fim = None
    if nome == config.PERIODO_PERSONALIZADO:
        intervalo = st.date_input("Datas (início e fim)", value=(hoje.replace(day=1), hoje),
                                  format="DD/MM/YYYY", key=f"{chave}_datas")
        if not isinstance(intervalo, (tuple, list)) or len(intervalo) != 2:
            st.info("Selecione a data inicial e a final.")
            st.stop()
        inicio, fim = intervalo
    ini, fi = calc.intervalo_periodo(nome, hoje, inicio, fim)
    return ini, fi, nome


def estilo_linhas(df, coluna: str, formatos: dict | None = None):
    """Styler que pinta cada linha conforme o valor da coluna (ver CORES_LINHA)."""
    def pintar(linha):
        cor = CORES_LINHA.get(linha[coluna], "")
        return [f"background-color: {cor}" if cor else ""] * len(linha)
    styler = df.style.apply(pintar, axis=1)
    if formatos:
        styler = styler.format(formatos, na_rep="—")
    return styler


def moeda(v) -> str:
    return formatar_moeda(v)
