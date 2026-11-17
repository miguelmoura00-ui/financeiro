"""Dados de exemplo para conhecer o sistema (só carrega se o banco estiver vazio)."""
from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

import database as db


def _dia(ref: date, meses_atras: int, dia: int) -> date:
    base = (pd.Timestamp(ref.replace(day=1)) - pd.DateOffset(months=meses_atras)).date()
    return base + timedelta(days=min(dia, 28) - 1)


def popular_exemplo(hoje: date | None = None) -> bool:
    hoje = hoje or date.today()
    if not db.esta_vazio():
        return False
    rnd = random.Random(42)

    db.criar_renda({"nome": "Salário", "valor": 4500, "tipo": "Principal", "dia_recebimento": 5, "ativa": 1},
                   _dia(hoje, 3, 1))
    db.criar_renda({"nome": "Freelance de design", "valor": 800, "tipo": "Secundária",
                    "dia_recebimento": 15, "ativa": 1}, _dia(hoje, 3, 1))

    fixas = [("Aluguel", 1200, "Moradia", 3), ("Internet", 99.9, "Internet", 8),
             ("Energia elétrica", 180, "Energia elétrica", 10), ("Água", 70, "Água", 12),
             ("Streaming", 55.9, "Assinaturas", 15)]
    variaveis = [("Supermercado", (350, 520), "Alimentação"), ("Restaurantes", (80, 220), "Alimentação"),
                 ("Combustível", (150, 260), "Combustível"), ("Cinema e passeios", (40, 160), "Lazer"),
                 ("Farmácia", (30, 120), "Saúde"), ("Compras diversas", (60, 300), "Compras")]
    formas = ["PIX", "Cartão de débito", "Cartão de crédito", "Dinheiro"]

    for m in (3, 2, 1, 0):
        eventos = [("e", _dia(hoje, m, 5), "Salário", 4500, "Salário", "Empresa"),
                   ("e", _dia(hoje, m, 15), "Freelance de design", 800 + rnd.choice([0, 150, 300]),
                    "Trabalho autônomo", "Clientes")]
        for _, data, desc, valor, cat, origem in eventos:
            if data <= hoje:
                db.inserir("entradas", {"descricao": desc, "valor": valor, "categoria": cat, "data": data,
                                        "origem": origem, "observacoes": ""})
        for nome, valor, cat, dia in fixas:
            data = _dia(hoje, m, dia)
            if data <= hoje + timedelta(days=10):
                db.inserir("despesas", {"nome": nome, "valor": valor, "categoria": cat, "data": data,
                                        "forma_pagamento": "Débito automático" if m else "Boleto",
                                        "status": "Pago" if data <= hoje - timedelta(days=2) else "Pendente",
                                        "tipo": "Fixa", "descricao": ""})
        for nome, (lo, hi), cat in variaveis:
            for _ in range(rnd.choice([1, 2])):
                data = _dia(hoje, m, rnd.randint(1, 28))
                if data <= hoje:
                    db.inserir("despesas", {"nome": nome, "valor": round(rnd.uniform(lo, hi), 2), "categoria": cat,
                                            "data": data, "forma_pagamento": rnd.choice(formas),
                                            "status": "Pago", "tipo": "Variável", "descricao": ""})

    for nome, valor, cat, dias in [("Cartão de crédito", 640.0, "Cartão de crédito", -2),
                                   ("Seguro do carro", 210.0, "Transporte", 3),
                                   ("Mensalidade do curso", 320.0, "Educação", 6),
                                   ("IPTU", 150.0, "Moradia", 20)]:
        db.inserir("contas", {"nome": nome, "valor": valor, "vencimento": hoje + timedelta(days=dias),
                              "categoria": cat, "status": "Pendente"})

    notebook = db.inserir("metas", {"nome": "Comprar um notebook", "valor_alvo": 5000,
                                    "prazo": hoje + timedelta(days=240), "valor_mensal": 500})
    viagem = db.inserir("metas", {"nome": "Viagem de férias", "valor_alvo": 3500, "valor_mensal": 300})
    reserva = db.inserir("metas", {"nome": "Reserva de emergência", "valor_alvo": 12000, "valor_mensal": 600})
    for m in (3, 2, 1, 0):
        for meta, valor in ((notebook, 500), (reserva, 600), (viagem, 300)):
            data = _dia(hoje, m, 7)
            if data <= hoje:
                db.inserir("poupanca_mov", {"data": data, "tipo": "Depósito", "valor": valor,
                                            "meta_id": meta, "descricao": "Depósito mensal"})
    db.inserir("poupanca_mov", {"data": _dia(hoje, 1, 20), "tipo": "Retirada", "valor": 150,
                                "meta_id": viagem, "descricao": "Reserva de hotel"})

    mes = hoje.strftime("%Y-%m")
    db.salvar_planejamento(mes, {"renda_prevista": 5300, "limite_gastos": 3700, "poupanca": 1000,
                                 "investimentos": 300, "emergencia": 300},
                           {"Moradia": 1500, "Alimentação": 800, "Transporte": 300, "Combustível": 250,
                            "Lazer": 250, "Saúde": 200, "Compras": 300, "Assinaturas": 80})
    return True
