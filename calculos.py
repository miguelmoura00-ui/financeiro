"""Regras de negócio e cálculos financeiros.

Este módulo não depende do Streamlit, o que permite testá-lo isoladamente.

Convenções:
- "Gasto" = despesas com status Pago (dinheiro que de fato saiu).
- "Saldo disponível" = entradas - despesas pagas - saldo guardado na poupança.
- "Economizado no mês" = recebido no mês - gasto no mês (a sobra).
- O orçamento (limites por categoria) considera despesas pagas e pendentes,
  pois representa o valor já comprometido.
"""
from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

import pandas as pd

import config

# ==========================================================================
# Datas e períodos
# ==========================================================================


def primeiro_dia_mes(d: date) -> date:
    return d.replace(day=1)


def mes_anterior(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def ultimo_dia_mes(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def data_no_mes(ano: int, mes: int, dia: int) -> date:
    """Data no mês informado, ajustando o dia para meses mais curtos."""
    return date(ano, mes, min(dia, ultimo_dia_mes(ano, mes)))


def proximo_recebimento(dia: int, hoje: date) -> date:
    candidata = data_no_mes(hoje.year, hoje.month, dia)
    if candidata >= hoje:
        return candidata
    prox = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
    return data_no_mes(prox.year, prox.month, dia)


def intervalo_periodo(nome: str, hoje: date, inicio: date | None = None,
                      fim: date | None = None) -> tuple[date, date]:
    """Converte o nome de um período em (data_inicial, data_final), ambas inclusivas."""
    if nome == config.PERIODO_7D:
        return hoje - timedelta(days=6), hoje
    if nome == config.PERIODO_30D:
        return hoje - timedelta(days=29), hoje
    if nome == config.PERIODO_6M:
        return (pd.Timestamp(hoje) - pd.DateOffset(months=6) + pd.Timedelta(days=1)).date(), hoje
    if nome == config.PERIODO_1A:
        return (pd.Timestamp(hoje) - pd.DateOffset(months=12) + pd.Timedelta(days=1)).date(), hoje
    if nome == config.PERIODO_PERSONALIZADO:
        if inicio is None or fim is None:
            raise ValueError("Informe a data inicial e a final.")
        if inicio > fim:
            inicio, fim = fim, inicio
        return inicio, fim
    raise ValueError(f"Período desconhecido: {nome}")


def escolher_freq(inicio: date, fim: date) -> str:
    """'D' (diário) para períodos curtos; 'M' (mensal) para os demais."""
    return "D" if (fim - inicio).days <= 62 else "M"


def rotulos_periodo(indice: pd.PeriodIndex, freq: str) -> list[str]:
    return list(indice.strftime("%d/%m" if freq == "D" else "%m/%Y"))


# ==========================================================================
# Filtros
# ==========================================================================


def filtrar_periodo(df: pd.DataFrame, coluna: str, inicio: date, fim: date) -> pd.DataFrame:
    if df.empty:
        return df
    ini = pd.Timestamp(inicio)
    limite = pd.Timestamp(fim) + pd.Timedelta(days=1)
    return df[(df[coluna] >= ini) & (df[coluna] < limite)]


def filtrar_mes(df: pd.DataFrame, coluna: str, ref: date) -> pd.DataFrame:
    primeiro = ref.replace(day=1)
    ultimo = ref.replace(day=ultimo_dia_mes(ref.year, ref.month))
    return filtrar_periodo(df, coluna, primeiro, ultimo)


# ==========================================================================
# Totais
# ==========================================================================


def totais_por_mes(df: pd.DataFrame, col_data: str = "data", col_valor: str = "valor") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["mes", "total"])
    s = df.groupby(df[col_data].dt.to_period("M"))[col_valor].sum().sort_index(ascending=False)
    return pd.DataFrame({"mes": list(s.index.strftime("%m/%Y")), "total": s.values})


def totais_por_ano(df: pd.DataFrame, col_data: str = "data", col_valor: str = "valor") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["ano", "total"])
    s = df.groupby(df[col_data].dt.year)[col_valor].sum().sort_index(ascending=False)
    return pd.DataFrame({"ano": [int(a) for a in s.index], "total": s.values})


def _pagas(despesas: pd.DataFrame) -> pd.DataFrame:
    if despesas.empty:
        return despesas
    return despesas[despesas["status"] == config.STATUS_PAGO]


def _sinal_poupanca(mov: pd.DataFrame) -> pd.Series:
    return mov["valor"].where(mov["tipo"] == config.MOV_DEPOSITO, -mov["valor"])


def saldo_poupanca(mov: pd.DataFrame, meta_id="todas") -> float:
    """Saldo guardado. meta_id: 'todas', None (sem meta) ou o id de uma meta."""
    if mov.empty:
        return 0.0
    m = mov
    if meta_id != "todas":
        m = mov[mov["meta_id"].isna()] if meta_id is None else mov[mov["meta_id"] == meta_id]
    if m.empty:
        return 0.0
    return float(_sinal_poupanca(m).sum())


def saldo_total(entradas: pd.DataFrame, despesas: pd.DataFrame, mov_poupanca: pd.DataFrame) -> float:
    """Dinheiro disponível: entradas - despesas pagas - o que está guardado na poupança."""
    recebido = float(entradas["valor"].sum()) if not entradas.empty else 0.0
    gasto = float(_pagas(despesas)["valor"].sum()) if not despesas.empty else 0.0
    return recebido - gasto - saldo_poupanca(mov_poupanca)


def resumo_mes(entradas: pd.DataFrame, despesas: pd.DataFrame, ref: date,
               renda_cadastrada: float = 0.0) -> dict:
    e = filtrar_mes(entradas, "data", ref)
    d = filtrar_mes(despesas, "data", ref)
    pagas = _pagas(d)
    recebido = float(e["valor"].sum()) if not e.empty else 0.0
    gasto = float(pagas["valor"].sum()) if not pagas.empty else 0.0
    fixas = float(pagas.loc[pagas["tipo"] == config.TIPO_FIXA, "valor"].sum()) if not pagas.empty else 0.0
    variaveis = float(pagas.loc[pagas["tipo"] == config.TIPO_VARIAVEL, "valor"].sum()) if not pagas.empty else 0.0
    pendentes = float(d.loc[d["status"] == config.STATUS_PENDENTE, "valor"].sum()) if not d.empty else 0.0
    economizado = recebido - gasto
    base = recebido if recebido > 0 else renda_cadastrada
    pct = (economizado / base * 100) if base > 0 else 0.0
    return {
        "recebido": recebido,
        "gasto": gasto,
        "fixas": fixas,
        "variaveis": variaveis,
        "pendentes": pendentes,
        "economizado": economizado,
        "pct_economizado": pct,
    }


def comparacao_meses(atual: dict, anterior: dict) -> pd.DataFrame:
    indicadores = [
        ("Recebido", "recebido"),
        ("Gasto", "gasto"),
        ("Economizado", "economizado"),
        ("Despesas fixas", "fixas"),
        ("Despesas variáveis", "variaveis"),
    ]
    linhas = []
    for rotulo, chave in indicadores:
        a, b = atual[chave], anterior[chave]
        var = a - b
        pct = (var / abs(b) * 100) if b != 0 else None
        linhas.append({"indicador": rotulo, "atual": a, "anterior": b,
                       "variacao": var, "variacao_pct": pct})
    return pd.DataFrame(linhas)


# ==========================================================================
# Contas a pagar
# ==========================================================================


def classificar_conta(status: str, vencimento, hoje: date,
                      dias_alerta: int = config.DIAS_ALERTA_VENCIMENTO) -> str:
    if status == config.STATUS_PAGO:
        return config.SIT_PAGA
    venc = pd.Timestamp(vencimento).date()
    if venc < hoje:
        return config.SIT_ATRASADA
    if (venc - hoje).days <= dias_alerta:
        return config.SIT_PROXIMA
    return config.SIT_PENDENTE


def adicionar_situacao(contas: pd.DataFrame, hoje: date) -> pd.DataFrame:
    out = contas.copy()
    out["situacao"] = [classificar_conta(s, v, hoje) for s, v in zip(out["status"], out["vencimento"])]
    return out


def pagamentos_pendentes(contas: pd.DataFrame, despesas: pd.DataFrame, hoje: date) -> pd.DataFrame:
    """Contas não pagas + despesas pendentes que não vieram de uma conta, por vencimento."""
    colunas = ["nome", "valor", "vencimento", "categoria", "origem", "situacao"]
    partes = []
    if not contas.empty:
        c = contas[contas["status"] == config.STATUS_PENDENTE]
        if not c.empty:
            partes.append(pd.DataFrame({
                "nome": c["nome"], "valor": c["valor"], "vencimento": c["vencimento"],
                "categoria": c["categoria"], "origem": "Conta"}))
    if not despesas.empty:
        d = despesas[(despesas["status"] == config.STATUS_PENDENTE) & despesas["conta_id"].isna()]
        if not d.empty:
            partes.append(pd.DataFrame({
                "nome": d["nome"], "valor": d["valor"], "vencimento": d["data"],
                "categoria": d["categoria"], "origem": "Despesa"}))
    if not partes:
        return pd.DataFrame(columns=colunas)
    out = pd.concat(partes, ignore_index=True).sort_values("vencimento").reset_index(drop=True)
    out["situacao"] = [classificar_conta(config.STATUS_PENDENTE, v, hoje) for v in out["vencimento"]]
    return out[colunas]


# ==========================================================================
# Orçamento
# ==========================================================================


def status_orcamento(limites: dict[str, float], despesas: pd.DataFrame, ref: date,
                     incluir_pendentes: bool = True,
                     limite_alerta: float = config.LIMITE_ALERTA_ORCAMENTO) -> pd.DataFrame:
    colunas = ["categoria", "limite", "gasto", "restante", "pct", "nivel"]
    d = filtrar_mes(despesas, "data", ref)
    if not incluir_pendentes:
        d = _pagas(d)
    gasto_cat = d.groupby("categoria")["valor"].sum() if not d.empty else pd.Series(dtype=float)
    linhas = []
    for categoria, limite in limites.items():
        if limite <= 0:
            continue
        gasto = float(gasto_cat.get(categoria, 0.0))
        pct = gasto / limite * 100
        if pct > 100:
            nivel = "estourado"
        elif pct >= limite_alerta * 100:
            nivel = "atencao"
        else:
            nivel = "ok"
        linhas.append({"categoria": categoria, "limite": limite, "gasto": gasto,
                       "restante": limite - gasto, "pct": pct, "nivel": nivel})
    return pd.DataFrame(linhas, columns=colunas)


# ==========================================================================
# Metas de poupança
# ==========================================================================


def meses_para_meta(falta: float, mensal: float) -> int | None:
    if falta <= 0:
        return 0
    if mensal <= 0:
        return None
    return math.ceil(falta / mensal)


def progresso_metas(metas: pd.DataFrame, mov: pd.DataFrame) -> pd.DataFrame:
    colunas = ["id", "nome", "valor_alvo", "atual", "pct", "falta", "prazo", "valor_mensal"]
    linhas = []
    for r in metas.itertuples():
        atual = saldo_poupanca(mov, int(r.id))
        alvo = float(r.valor_alvo)
        linhas.append({
            "id": int(r.id), "nome": r.nome, "valor_alvo": alvo, "atual": atual,
            "pct": (atual / alvo * 100) if alvo > 0 else 0.0,
            "falta": max(alvo - atual, 0.0), "prazo": r.prazo,
            "valor_mensal": float(r.valor_mensal),
        })
    return pd.DataFrame(linhas, columns=colunas)


# ==========================================================================
# Séries para os gráficos
# ==========================================================================


def serie_agrupada(df: pd.DataFrame, col_data: str, col_valor: str,
                   inicio: date, fim: date, freq: str) -> pd.Series:
    """Soma por dia ('D') ou mês ('M') no período, preenchendo zeros nos vazios."""
    idx = pd.period_range(start=inicio, end=fim, freq=freq)
    d = filtrar_periodo(df, col_data, inicio, fim)
    if d.empty:
        return pd.Series(0.0, index=idx)
    s = d.groupby(d[col_data].dt.to_period(freq))[col_valor].sum()
    return s.reindex(idx, fill_value=0.0)


def _acumulado(mov: pd.DataFrame, inicio: date, fim: date, freq: str) -> pd.Series:
    """Soma acumulada (desde o primeiro registro) de uma tabela data/delta, amostrada no período."""
    idx = pd.period_range(start=inicio, end=fim, freq=freq)
    if mov.empty:
        return pd.Series(0.0, index=idx)
    mov = mov.copy()
    mov["data"] = mov["data"].dt.normalize()
    diario = mov.groupby("data")["delta"].sum()
    ini, fi = pd.Timestamp(inicio), pd.Timestamp(fim)
    dias = pd.date_range(min(diario.index.min(), ini), max(diario.index.max(), fi))
    acum = diario.reindex(dias, fill_value=0.0).cumsum().loc[ini:fi]
    amostrado = acum.groupby(acum.index.to_period(freq)).last()
    return amostrado.reindex(idx).ffill().fillna(0.0)


def serie_saldo(entradas: pd.DataFrame, despesas: pd.DataFrame, mov_poupanca: pd.DataFrame,
                inicio: date, fim: date, freq: str, incluir_pendentes: bool = False) -> pd.Series:
    """Evolução do saldo disponível (mesma regra do painel)."""
    partes = []
    if not entradas.empty:
        partes.append(pd.DataFrame({"data": entradas["data"], "delta": entradas["valor"]}))
    if not despesas.empty:
        d = despesas if incluir_pendentes else _pagas(despesas)
        if not d.empty:
            partes.append(pd.DataFrame({"data": d["data"], "delta": -d["valor"]}))
    if not mov_poupanca.empty:
        partes.append(pd.DataFrame({"data": mov_poupanca["data"], "delta": -_sinal_poupanca(mov_poupanca)}))
    if not partes:
        return pd.Series(0.0, index=pd.period_range(start=inicio, end=fim, freq=freq))
    return _acumulado(pd.concat(partes, ignore_index=True), inicio, fim, freq)


def serie_economias(mov_poupanca: pd.DataFrame, inicio: date, fim: date, freq: str) -> pd.Series:
    if mov_poupanca.empty:
        return pd.Series(0.0, index=pd.period_range(start=inicio, end=fim, freq=freq))
    mov = pd.DataFrame({"data": mov_poupanca["data"], "delta": _sinal_poupanca(mov_poupanca)})
    return _acumulado(mov, inicio, fim, freq)


# ==========================================================================
# Histórico unificado
# ==========================================================================


def construir_historico(entradas: pd.DataFrame, despesas: pd.DataFrame,
                        mov_poupanca: pd.DataFrame) -> pd.DataFrame:
    colunas = ["data", "descricao", "categoria", "tipo", "valor", "forma_pagamento", "situacao"]
    partes = []
    if not entradas.empty:
        partes.append(pd.DataFrame({
            "data": entradas["data"], "descricao": entradas["descricao"],
            "categoria": entradas["categoria"], "tipo": config.MOV_ENTRADA,
            "valor": entradas["valor"], "forma_pagamento": "—", "situacao": "Recebido"}))
    if not despesas.empty:
        partes.append(pd.DataFrame({
            "data": despesas["data"], "descricao": despesas["nome"],
            "categoria": despesas["categoria"], "tipo": config.MOV_SAIDA,
            "valor": despesas["valor"], "forma_pagamento": despesas["forma_pagamento"].replace("", "—"),
            "situacao": despesas["status"]}))
    if not mov_poupanca.empty:
        tipo = mov_poupanca["tipo"].map({config.MOV_DEPOSITO: config.MOV_POUP_DEP,
                                         config.MOV_RETIRADA: config.MOV_POUP_RET})
        desc = mov_poupanca["descricao"].where(mov_poupanca["descricao"] != "", "Movimentação da poupança")
        partes.append(pd.DataFrame({
            "data": mov_poupanca["data"], "descricao": desc, "categoria": "Poupança",
            "tipo": tipo, "valor": mov_poupanca["valor"], "forma_pagamento": "—",
            "situacao": "Concluído"}))
    if not partes:
        return pd.DataFrame(columns=colunas)
    return (pd.concat(partes, ignore_index=True)
            .sort_values("data", ascending=False, kind="stable")
            .reset_index(drop=True)[colunas])


# ==========================================================================
# Calculadoras financeiras
# ==========================================================================


def juros_compostos(capital: float, aporte_mensal: float, taxa_mensal_pct: float,
                    meses: int) -> pd.DataFrame:
    """Evolução mês a mês. Os aportes são feitos no fim de cada mês."""
    i = taxa_mensal_pct / 100
    saldo, investido = capital, capital
    linhas = [{"mes": 0, "investido": investido, "montante": saldo}]
    for m in range(1, int(meses) + 1):
        saldo = saldo * (1 + i) + aporte_mensal
        investido += aporte_mensal
        linhas.append({"mes": m, "investido": investido, "montante": saldo})
    return pd.DataFrame(linhas)


def aporte_necessario(meta: float, capital: float, taxa_mensal_pct: float, meses: int) -> float:
    """Aporte mensal (no fim do mês) para atingir a meta no prazo."""
    if meses <= 0:
        return 0.0
    i = taxa_mensal_pct / 100
    if i == 0:
        return max((meta - capital) / meses, 0.0)
    fator = (1 + i) ** meses
    return max((meta - capital * fator) * i / (fator - 1), 0.0)


def parcela_price(valor: float, taxa_mensal_pct: float, parcelas: int) -> float:
    """Parcela fixa pela Tabela Price."""
    if parcelas <= 0:
        return 0.0
    i = taxa_mensal_pct / 100
    if i == 0:
        return valor / parcelas
    return valor * i / (1 - (1 + i) ** -parcelas)


def tabela_price(valor: float, taxa_mensal_pct: float, parcelas: int) -> pd.DataFrame:
    i = taxa_mensal_pct / 100
    pmt = parcela_price(valor, taxa_mensal_pct, parcelas)
    saldo = valor
    linhas = []
    for n in range(1, int(parcelas) + 1):
        juros = saldo * i
        amort = pmt - juros
        saldo = max(saldo - amort, 0.0)
        linhas.append({"parcela": n, "valor_parcela": pmt, "juros": juros,
                       "amortizacao": amort, "saldo_devedor": saldo})
    return pd.DataFrame(linhas)


def regra_50_30_20(renda: float) -> dict[str, float]:
    return {"Necessidades (50%)": renda * 0.5,
            "Desejos (30%)": renda * 0.3,
            "Poupança e investimentos (20%)": renda * 0.2}


def reserva_emergencia(despesa_mensal: float, meses: int) -> float:
    return despesa_mensal * meses
