"""Funções de formatação no padrão brasileiro."""


def formatar_moeda(valor) -> str:
    """1234.5 -> 'R$ 1.234,50' (negativos: '-R$ 1.234,50')."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"
    if v != v:  # NaN
        return "R$ 0,00"
    v = round(v, 2)
    if v == 0:
        v = 0.0
    sinal = "-" if v < 0 else ""
    texto = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def formatar_pct(valor, casas: int = 1) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"
    if v != v:
        return "—"
    return f"{v:.{casas}f}%".replace(".", ",")


def formatar_data(data) -> str:
    """Aceita date, datetime ou Timestamp. Valores vazios viram '—'."""
    try:
        return data.strftime("%d/%m/%Y")
    except (AttributeError, ValueError):
        return "—"
