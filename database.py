"""Camada de dados (SQLite). Todo acesso ao banco passa por este módulo."""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import config

DB_PATH = Path(os.environ.get("FINANCAS_DB", Path(__file__).parent / "data" / "financas.db"))

TABELAS = {
    "entradas": ["id", "descricao", "valor", "categoria", "data", "origem", "observacoes"],
    "despesas": ["id", "nome", "valor", "categoria", "data", "forma_pagamento",
                 "status", "tipo", "descricao", "conta_id"],
    "rendas": ["id", "nome", "valor", "tipo", "dia_recebimento", "ativa"],
    "renda_historico": ["id", "renda_id", "data", "valor"],
    "planejamento": ["mes", "renda_prevista", "limite_gastos", "poupanca",
                     "investimentos", "emergencia"],
    "planejamento_categorias": ["mes", "categoria", "limite"],
    "metas": ["id", "nome", "valor_alvo", "prazo", "valor_mensal"],
    "poupanca_mov": ["id", "data", "tipo", "valor", "meta_id", "descricao"],
    "contas": ["id", "nome", "valor", "vencimento", "categoria", "status", "data_pagamento"],
}

COLUNAS_DATA = {
    "entradas": ["data"],
    "despesas": ["data"],
    "renda_historico": ["data"],
    "metas": ["prazo"],
    "poupanca_mov": ["data"],
    "contas": ["vencimento", "data_pagamento"],
}

COLUNAS_NUMERICAS = {
    "entradas": ["valor"],
    "despesas": ["valor"],
    "rendas": ["valor", "dia_recebimento", "ativa"],
    "renda_historico": ["valor"],
    "planejamento": ["renda_prevista", "limite_gastos", "poupanca", "investimentos", "emergencia"],
    "planejamento_categorias": ["limite"],
    "metas": ["valor_alvo", "valor_mensal"],
    "poupanca_mov": ["valor"],
    "contas": ["valor"],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS contas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor REAL NOT NULL CHECK (valor >= 0),
    vencimento TEXT NOT NULL,
    categoria TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pendente' CHECK (status IN ('Pago', 'Pendente')),
    data_pagamento TEXT
);

CREATE TABLE IF NOT EXISTS entradas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL CHECK (valor >= 0),
    categoria TEXT NOT NULL,
    data TEXT NOT NULL,
    origem TEXT DEFAULT '',
    observacoes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS despesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor REAL NOT NULL CHECK (valor >= 0),
    categoria TEXT NOT NULL,
    data TEXT NOT NULL,
    forma_pagamento TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Pendente' CHECK (status IN ('Pago', 'Pendente')),
    tipo TEXT NOT NULL DEFAULT 'Variável' CHECK (tipo IN ('Fixa', 'Variável')),
    descricao TEXT DEFAULT '',
    conta_id INTEGER REFERENCES contas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS rendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor REAL NOT NULL CHECK (valor >= 0),
    tipo TEXT NOT NULL DEFAULT 'Principal' CHECK (tipo IN ('Principal', 'Secundária')),
    dia_recebimento INTEGER NOT NULL DEFAULT 5 CHECK (dia_recebimento BETWEEN 1 AND 31),
    ativa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS renda_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    renda_id INTEGER NOT NULL REFERENCES rendas(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    valor REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS planejamento (
    mes TEXT PRIMARY KEY,
    renda_prevista REAL NOT NULL DEFAULT 0,
    limite_gastos REAL NOT NULL DEFAULT 0,
    poupanca REAL NOT NULL DEFAULT 0,
    investimentos REAL NOT NULL DEFAULT 0,
    emergencia REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS planejamento_categorias (
    mes TEXT NOT NULL,
    categoria TEXT NOT NULL,
    limite REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (mes, categoria)
);

CREATE TABLE IF NOT EXISTS metas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor_alvo REAL NOT NULL CHECK (valor_alvo > 0),
    prazo TEXT,
    valor_mensal REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS poupanca_mov (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('Depósito', 'Retirada')),
    valor REAL NOT NULL CHECK (valor > 0),
    meta_id INTEGER REFERENCES metas(id) ON DELETE SET NULL,
    descricao TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_entradas_data ON entradas(data);
CREATE INDEX IF NOT EXISTS idx_despesas_data ON despesas(data);
CREATE INDEX IF NOT EXISTS idx_contas_venc ON contas(vencimento);
CREATE INDEX IF NOT EXISTS idx_poup_data ON poupanca_mov(data);
"""

_ORDER_RE = re.compile(r"^[a-z_]+( (ASC|DESC))?(, [a-z_]+( (ASC|DESC))?)*$", re.IGNORECASE)


# --------------------------------------------------------------------------
# Conexão
# --------------------------------------------------------------------------
@contextmanager
def conectar(db_path=None):
    """Abre uma conexão com commit/rollback automático."""
    caminho = Path(db_path or DB_PATH)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar():
    """Cria as tabelas, se ainda não existirem."""
    with conectar() as con:
        con.executescript(SCHEMA)


def _normalizar(valor):
    """Converte tipos Python/pandas para algo que o SQLite aceita."""
    if valor is None:
        return None
    if isinstance(valor, pd.Timestamp):
        return None if pd.isna(valor) else valor.date().isoformat()
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, float):
        return None if valor != valor else round(valor, 2)
    if hasattr(valor, "item"):  # tipos numpy
        return _normalizar(valor.item())
    return valor


def _validar(tabela: str, dados: dict) -> list[str]:
    if tabela not in TABELAS:
        raise ValueError(f"Tabela desconhecida: {tabela}")
    colunas = [c for c in dados if c != "id"]
    invalidas = [c for c in colunas if c not in TABELAS[tabela]]
    if invalidas:
        raise ValueError(f"Colunas inválidas para {tabela}: {invalidas}")
    return colunas


# --------------------------------------------------------------------------
# CRUD genérico
# --------------------------------------------------------------------------
def inserir(tabela: str, dados: dict) -> int:
    colunas = _validar(tabela, dados)
    sql = (f"INSERT INTO {tabela} ({', '.join(colunas)}) "
           f"VALUES ({', '.join('?' for _ in colunas)})")
    with conectar() as con:
        cur = con.execute(sql, [_normalizar(dados[c]) for c in colunas])
        return cur.lastrowid


def atualizar(tabela: str, registro_id: int, dados: dict) -> None:
    colunas = _validar(tabela, dados)
    if not colunas:
        return
    sql = f"UPDATE {tabela} SET {', '.join(f'{c} = ?' for c in colunas)} WHERE id = ?"
    with conectar() as con:
        con.execute(sql, [_normalizar(dados[c]) for c in colunas] + [int(registro_id)])


def excluir(tabela: str, registro_id: int) -> None:
    if tabela not in TABELAS or "id" not in TABELAS[tabela]:
        raise ValueError(f"Não é possível excluir por id em: {tabela}")
    with conectar() as con:
        con.execute(f"DELETE FROM {tabela} WHERE id = ?", (int(registro_id),))


def carregar_df(tabela: str, ordenar: str | None = None) -> pd.DataFrame:
    """Lê uma tabela como DataFrame, com datas e números já convertidos."""
    if tabela not in TABELAS:
        raise ValueError(f"Tabela desconhecida: {tabela}")
    sql = f"SELECT * FROM {tabela}"
    if ordenar:
        if not _ORDER_RE.match(ordenar):
            raise ValueError("Ordenação inválida")
        sql += f" ORDER BY {ordenar}"
    with conectar() as con:
        linhas = [tuple(r) for r in con.execute(sql).fetchall()]
    df = pd.DataFrame(linhas, columns=TABELAS[tabela])
    for col in COLUNAS_DATA.get(tabela, []):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in COLUNAS_NUMERICAS.get(tabela, []):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def esta_vazio() -> bool:
    with conectar() as con:
        total = 0
        for t in ("entradas", "despesas", "rendas", "contas", "metas", "poupanca_mov"):
            total += con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return total == 0


# --------------------------------------------------------------------------
# Rendas (com histórico de alterações)
# --------------------------------------------------------------------------
def criar_renda(dados: dict, data_inicio: date | None = None) -> int:
    renda_id = inserir("rendas", dados)
    inserir("renda_historico", {"renda_id": renda_id,
                                "data": data_inicio or date.today(),
                                "valor": dados["valor"]})
    return renda_id


def atualizar_renda(renda_id: int, dados: dict, data_alteracao: date | None = None) -> None:
    """Atualiza a renda e, se o valor mudou, registra no histórico."""
    with conectar() as con:
        antigo = con.execute("SELECT valor FROM rendas WHERE id = ?", (int(renda_id),)).fetchone()
    atualizar("rendas", renda_id, dados)
    if antigo is not None and "valor" in dados and round(float(dados["valor"]), 2) != round(float(antigo["valor"]), 2):
        inserir("renda_historico", {"renda_id": renda_id,
                                    "data": data_alteracao or date.today(),
                                    "valor": dados["valor"]})


# --------------------------------------------------------------------------
# Contas a pagar
# --------------------------------------------------------------------------
def pagar_conta(conta_id: int, data_pagamento: date, forma_pagamento: str,
                tipo: str = config.TIPO_FIXA) -> bool:
    """Marca a conta como paga e lança a despesa correspondente (uma única vez)."""
    with conectar() as con:
        conta = con.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),)).fetchone()
        if conta is None or conta["status"] == config.STATUS_PAGO:
            return False
        data_iso = _normalizar(data_pagamento)
        con.execute("UPDATE contas SET status = 'Pago', data_pagamento = ? WHERE id = ?",
                    (data_iso, int(conta_id)))
        con.execute(
            "INSERT INTO despesas (nome, valor, categoria, data, forma_pagamento, status, tipo, descricao, conta_id) "
            "VALUES (?, ?, ?, ?, ?, 'Pago', ?, ?, ?)",
            (conta["nome"], conta["valor"], conta["categoria"], data_iso,
             forma_pagamento, tipo, "Pagamento de conta", int(conta_id)),
        )
    return True


def desfazer_pagamento(conta_id: int) -> None:
    with conectar() as con:
        con.execute("DELETE FROM despesas WHERE conta_id = ?", (int(conta_id),))
        con.execute("UPDATE contas SET status = 'Pendente', data_pagamento = NULL WHERE id = ?",
                    (int(conta_id),))


def atualizar_conta(conta_id: int, dados: dict) -> None:
    """Atualiza a conta; se já estiver paga, mantém a despesa vinculada em sincronia."""
    atualizar("contas", conta_id, dados)
    sincronizaveis = {k: dados[k] for k in ("nome", "valor", "categoria") if k in dados}
    if sincronizaveis:
        sets = ", ".join(f"{k} = ?" for k in sincronizaveis)
        with conectar() as con:
            con.execute(f"UPDATE despesas SET {sets} WHERE conta_id = ?",
                        [_normalizar(v) for v in sincronizaveis.values()] + [int(conta_id)])


# --------------------------------------------------------------------------
# Planejamento mensal
# --------------------------------------------------------------------------
def obter_planejamento(mes: str) -> dict | None:
    with conectar() as con:
        linha = con.execute("SELECT * FROM planejamento WHERE mes = ?", (mes,)).fetchone()
    return dict(linha) if linha else None


def obter_limites(mes: str) -> dict[str, float]:
    with conectar() as con:
        linhas = con.execute("SELECT categoria, limite FROM planejamento_categorias WHERE mes = ?",
                             (mes,)).fetchall()
    return {r["categoria"]: float(r["limite"]) for r in linhas}


def salvar_planejamento(mes: str, dados: dict, limites: dict[str, float]) -> None:
    campos = ["renda_prevista", "limite_gastos", "poupanca", "investimentos", "emergencia"]
    with conectar() as con:
        con.execute(
            "INSERT OR REPLACE INTO planejamento (mes, renda_prevista, limite_gastos, poupanca, investimentos, emergencia) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [mes] + [_normalizar(float(dados.get(c, 0.0))) for c in campos],
        )
        con.execute("DELETE FROM planejamento_categorias WHERE mes = ?", (mes,))
        for categoria, limite in limites.items():
            if float(limite) > 0:
                con.execute("INSERT INTO planejamento_categorias (mes, categoria, limite) VALUES (?, ?, ?)",
                            (mes, categoria, _normalizar(float(limite))))
