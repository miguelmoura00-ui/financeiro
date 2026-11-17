"""Testes da camada de dados e das regras de negócio.

Execute na pasta do projeto:  python -m unittest discover -s tests -v
"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

import calculos as calc  # noqa: E402
import config  # noqa: E402
import database as db  # noqa: E402
from formatacao import formatar_moeda, formatar_pct  # noqa: E402

HOJE = date(2026, 11, 17)


class BaseBanco(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "teste.db"
        db.inicializar()

    def tearDown(self):
        db.DB_PATH = self._original
        self._tmp.cleanup()

    def entrada(self, valor, data, categoria="Salário", desc="Teste"):
        return db.inserir("entradas", {"descricao": desc, "valor": valor, "categoria": categoria,
                                       "data": data, "origem": "", "observacoes": ""})

    def despesa(self, valor, data, categoria="Alimentação", status="Pago", tipo="Variável", nome="Gasto"):
        return db.inserir("despesas", {"nome": nome, "valor": valor, "categoria": categoria,
                                       "data": data, "forma_pagamento": "PIX", "status": status,
                                       "tipo": tipo, "descricao": ""})


class TestBanco(BaseBanco):
    def test_crud_entradas(self):
        i = self.entrada(1000, date(2026, 11, 5))
        df = db.carregar_df("entradas")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, "valor"], 1000)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["data"]))
        db.atualizar("entradas", i, {"valor": 1200.456, "descricao": "Novo"})
        df = db.carregar_df("entradas")
        self.assertEqual(df.loc[0, "valor"], 1200.46)
        db.excluir("entradas", i)
        self.assertTrue(db.carregar_df("entradas").empty)

    def test_tabela_vazia_tem_tipos_corretos(self):
        df = db.carregar_df("despesas")
        self.assertTrue(df.empty)
        self.assertIn("conta_id", df.columns)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["data"]))

    def test_coluna_invalida_e_rejeitada(self):
        with self.assertRaises(ValueError):
            db.inserir("entradas", {"valor; DROP TABLE entradas": 1})
        with self.assertRaises(ValueError):
            db.carregar_df("entradas", "valor; DROP TABLE x")

    def test_valor_negativo_e_rejeitado(self):
        with self.assertRaises(Exception):
            self.entrada(-5, date(2026, 11, 1))

    def test_pagar_conta_gera_despesa_uma_vez(self):
        cid = db.inserir("contas", {"nome": "Luz", "valor": 150, "vencimento": date(2026, 11, 20),
                                    "categoria": "Energia elétrica", "status": "Pendente"})
        self.assertTrue(db.pagar_conta(cid, date(2026, 11, 18), "PIX", "Fixa"))
        self.assertFalse(db.pagar_conta(cid, date(2026, 11, 18), "PIX", "Fixa"))
        desp = db.carregar_df("despesas")
        self.assertEqual(len(desp), 1)
        self.assertEqual(desp.loc[0, "status"], "Pago")
        self.assertEqual(int(desp.loc[0, "conta_id"]), cid)
        conta = db.carregar_df("contas").iloc[0]
        self.assertEqual(conta["status"], "Pago")
        db.desfazer_pagamento(cid)
        self.assertTrue(db.carregar_df("despesas").empty)
        self.assertEqual(db.carregar_df("contas").iloc[0]["status"], "Pendente")

    def test_atualizar_conta_paga_sincroniza_despesa(self):
        cid = db.inserir("contas", {"nome": "Net", "valor": 100, "vencimento": date(2026, 11, 10),
                                    "categoria": "Internet"})
        db.pagar_conta(cid, date(2026, 11, 10), "Boleto")
        db.atualizar_conta(cid, {"valor": 120})
        self.assertEqual(db.carregar_df("despesas").loc[0, "valor"], 120)

    def test_excluir_conta_paga_preserva_despesa(self):
        cid = db.inserir("contas", {"nome": "Net", "valor": 100, "vencimento": date(2026, 11, 10),
                                    "categoria": "Internet"})
        db.pagar_conta(cid, date(2026, 11, 10), "Boleto")
        db.excluir("contas", cid)
        desp = db.carregar_df("despesas")
        self.assertEqual(len(desp), 1)
        self.assertTrue(pd.isna(desp.loc[0, "conta_id"]))

    def test_renda_historico(self):
        rid = db.criar_renda({"nome": "Salário", "valor": 3000, "tipo": "Principal",
                              "dia_recebimento": 5, "ativa": 1}, date(2026, 1, 1))
        db.atualizar_renda(rid, {"valor": 3000})  # sem mudança
        db.atualizar_renda(rid, {"valor": 3500}, date(2026, 6, 1))
        hist = db.carregar_df("renda_historico")
        self.assertEqual(list(hist["valor"]), [3000, 3500])

    def test_planejamento(self):
        db.salvar_planejamento("2026-11", {"renda_prevista": 3000, "limite_gastos": 2000,
                                           "poupanca": 600, "investimentos": 0, "emergencia": 300},
                               {"Moradia": 800, "Lazer": 0, "Alimentação": 500})
        p = db.obter_planejamento("2026-11")
        self.assertEqual(p["renda_prevista"], 3000)
        self.assertEqual(db.obter_limites("2026-11"), {"Moradia": 800.0, "Alimentação": 500.0})
        db.salvar_planejamento("2026-11", {"renda_prevista": 3100}, {"Moradia": 900})
        self.assertEqual(db.obter_limites("2026-11"), {"Moradia": 900.0})
        self.assertIsNone(db.obter_planejamento("2026-12"))

    def test_esta_vazio(self):
        self.assertTrue(db.esta_vazio())
        self.entrada(10, date(2026, 11, 1))
        self.assertFalse(db.esta_vazio())


class TestResumo(BaseBanco):
    def setUp(self):
        super().setUp()
        self.entrada(3000, date(2026, 11, 5))
        self.entrada(500, date(2026, 11, 10), "Renda extra")
        self.entrada(2800, date(2026, 10, 5))
        self.despesa(800, date(2026, 11, 6), "Moradia", "Pago", "Fixa")
        self.despesa(300, date(2026, 11, 8), "Alimentação", "Pago", "Variável")
        self.despesa(200, date(2026, 11, 20), "Lazer", "Pendente", "Variável")
        self.despesa(900, date(2026, 10, 6), "Moradia", "Pago", "Fixa")
        db.inserir("poupanca_mov", {"data": date(2026, 11, 7), "tipo": "Depósito", "valor": 400})
        db.inserir("poupanca_mov", {"data": date(2026, 11, 9), "tipo": "Retirada", "valor": 100})
        self.e = db.carregar_df("entradas")
        self.d = db.carregar_df("despesas")
        self.m = db.carregar_df("poupanca_mov")

    def test_resumo_mes(self):
        r = calc.resumo_mes(self.e, self.d, HOJE)
        self.assertEqual(r["recebido"], 3500)
        self.assertEqual(r["gasto"], 1100)
        self.assertEqual(r["fixas"], 800)
        self.assertEqual(r["variaveis"], 300)
        self.assertEqual(r["pendentes"], 200)
        self.assertEqual(r["economizado"], 2400)
        self.assertAlmostEqual(r["pct_economizado"], 2400 / 3500 * 100)

    def test_mes_sem_dados(self):
        r = calc.resumo_mes(self.e, self.d, date(2026, 5, 1), renda_cadastrada=3000)
        self.assertEqual(r["recebido"], 0)
        self.assertEqual(r["pct_economizado"], 0.0)
        vazio = calc.resumo_mes(db.carregar_df("entradas").iloc[0:0], db.carregar_df("despesas").iloc[0:0], HOJE)
        self.assertEqual(vazio["gasto"], 0)

    def test_saldo_total(self):
        # entradas 6300 - despesas pagas 2000 - poupança líquida 300
        self.assertEqual(calc.saldo_total(self.e, self.d, self.m), 6300 - 2000 - 300)

    def test_comparacao(self):
        atual = calc.resumo_mes(self.e, self.d, HOJE)
        ant = calc.resumo_mes(self.e, self.d, calc.mes_anterior(HOJE))
        comp = calc.comparacao_meses(atual, ant)
        linha = comp[comp["indicador"] == "Recebido"].iloc[0]
        self.assertEqual(linha["variacao"], 700)
        self.assertAlmostEqual(linha["variacao_pct"], 700 / 2800 * 100)

    def test_orcamento(self):
        o = calc.status_orcamento({"Moradia": 1000, "Alimentação": 310, "Lazer": 150, "Saúde": 0},
                                  self.d, HOJE)
        niveis = dict(zip(o["categoria"], o["nivel"]))
        self.assertEqual(niveis["Moradia"], "atencao")     # 80%
        self.assertEqual(niveis["Alimentação"], "atencao")  # 96,8%
        self.assertEqual(niveis["Lazer"], "estourado")     # 133% (pendente conta)
        self.assertNotIn("Saúde", niveis)
        so_pagas = calc.status_orcamento({"Lazer": 150}, self.d, HOJE, incluir_pendentes=False)
        self.assertEqual(so_pagas.iloc[0]["nivel"], "ok")

    def test_totais_por_mes_e_ano(self):
        mes = calc.totais_por_mes(self.e)
        self.assertEqual(list(mes["mes"]), ["11/2026", "10/2026"])
        self.assertEqual(list(mes["total"]), [3500, 2800])
        ano = calc.totais_por_ano(self.e)
        self.assertEqual(list(ano["total"]), [6300])

    def test_series(self):
        ini, fim = date(2026, 10, 1), date(2026, 11, 30)
        saldo = calc.serie_saldo(self.e, self.d, self.m, ini, fim, "M")
        self.assertEqual(list(saldo.values), [2800 - 900, 6300 - 2000 - 300])
        eco = calc.serie_economias(self.m, ini, fim, "M")
        self.assertEqual(list(eco.values), [0, 300])
        ent = calc.serie_agrupada(self.e, "data", "valor", ini, fim, "M")
        self.assertEqual(list(ent.values), [2800, 3500])

    def test_serie_diaria_acumula_antes_do_periodo(self):
        s = calc.serie_saldo(self.e, self.d, self.m, date(2026, 11, 8), date(2026, 11, 10), "D")
        # até 07/11: 2800+3000-900-800-400 = 3700; 08/11: -300; 09/11: +100; 10/11: +500
        self.assertEqual(list(s.values), [3400, 3500, 4000])

    def test_series_sem_dados(self):
        vazio_e = db.carregar_df("entradas").iloc[0:0]
        s = calc.serie_saldo(vazio_e, vazio_e, vazio_e, date(2026, 11, 1), date(2026, 11, 3), "D")
        self.assertEqual(list(s.values), [0, 0, 0])

    def test_historico(self):
        h = calc.construir_historico(self.e, self.d, self.m)
        self.assertEqual(len(h), 3 + 4 + 2)  # 3 entradas + 4 despesas + 2 movimentos de poupança
        self.assertEqual(set(h["tipo"]), {"Entrada", "Saída", "Poupança (depósito)", "Poupança (retirada)"})
        self.assertTrue(h["data"].is_monotonic_decreasing)
        self.assertTrue(calc.construir_historico(*(db.carregar_df(t).iloc[0:0] for t in
                                                   ("entradas", "despesas", "poupanca_mov"))).empty)


class TestContasEMetas(BaseBanco):
    def test_classificar_conta(self):
        c = calc.classificar_conta
        self.assertEqual(c("Pago", date(2026, 1, 1), HOJE), "Paga")
        self.assertEqual(c("Pendente", date(2026, 11, 16), HOJE), "Atrasada")
        self.assertEqual(c("Pendente", HOJE, HOJE), "Próxima do vencimento")
        self.assertEqual(c("Pendente", date(2026, 11, 24), HOJE), "Próxima do vencimento")
        self.assertEqual(c("Pendente", date(2026, 11, 25), HOJE), "Pendente")

    def test_pagamentos_pendentes(self):
        db.inserir("contas", {"nome": "Luz", "valor": 100, "vencimento": date(2026, 11, 20), "categoria": "Energia elétrica"})
        db.inserir("contas", {"nome": "Água", "valor": 50, "vencimento": date(2026, 11, 10), "categoria": "Água"})
        pago = db.inserir("contas", {"nome": "Net", "valor": 90, "vencimento": date(2026, 11, 12), "categoria": "Internet"})
        db.pagar_conta(pago, date(2026, 11, 12), "PIX")
        db.inserir("despesas", {"nome": "Dentista", "valor": 200, "categoria": "Saúde", "data": date(2026, 11, 30),
                                "status": "Pendente", "tipo": "Variável", "forma_pagamento": "PIX", "descricao": ""})
        p = calc.pagamentos_pendentes(db.carregar_df("contas"), db.carregar_df("despesas"), HOJE)
        self.assertEqual(list(p["nome"]), ["Água", "Luz", "Dentista"])
        self.assertEqual(list(p["situacao"]), ["Atrasada", "Próxima do vencimento", "Pendente"])
        self.assertEqual(p["valor"].sum(), 350)
        vazio = calc.pagamentos_pendentes(db.carregar_df("contas").iloc[0:0], db.carregar_df("despesas").iloc[0:0], HOJE)
        self.assertTrue(vazio.empty)

    def test_metas(self):
        m1 = db.inserir("metas", {"nome": "Notebook", "valor_alvo": 4000, "valor_mensal": 500})
        m2 = db.inserir("metas", {"nome": "Viagem", "valor_alvo": 2000})
        db.inserir("poupanca_mov", {"data": date(2026, 11, 1), "tipo": "Depósito", "valor": 1000, "meta_id": m1})
        db.inserir("poupanca_mov", {"data": date(2026, 11, 2), "tipo": "Retirada", "valor": 200, "meta_id": m1})
        db.inserir("poupanca_mov", {"data": date(2026, 11, 3), "tipo": "Depósito", "valor": 300})
        mov = db.carregar_df("poupanca_mov")
        self.assertEqual(calc.saldo_poupanca(mov), 1100)
        self.assertEqual(calc.saldo_poupanca(mov, m1), 800)
        self.assertEqual(calc.saldo_poupanca(mov, m2), 0)
        self.assertEqual(calc.saldo_poupanca(mov, None), 300)
        prog = calc.progresso_metas(db.carregar_df("metas"), mov)
        self.assertEqual(prog.loc[0, "pct"], 20)
        self.assertEqual(prog.loc[0, "falta"], 3200)
        self.assertEqual(calc.meses_para_meta(3200, 500), 7)
        self.assertIsNone(calc.meses_para_meta(100, 0))
        self.assertEqual(calc.meses_para_meta(0, 0), 0)

    def test_excluir_meta_preserva_movimentos(self):
        m = db.inserir("metas", {"nome": "X", "valor_alvo": 100})
        db.inserir("poupanca_mov", {"data": date(2026, 11, 1), "tipo": "Depósito", "valor": 50, "meta_id": m})
        db.excluir("metas", m)
        mov = db.carregar_df("poupanca_mov")
        self.assertEqual(len(mov), 1)
        self.assertEqual(calc.saldo_poupanca(mov, None), 50)


class TestPeriodosECalculadoras(unittest.TestCase):
    def test_intervalos(self):
        self.assertEqual(calc.intervalo_periodo(config.PERIODO_7D, HOJE), (date(2026, 11, 11), HOJE))
        self.assertEqual(calc.intervalo_periodo(config.PERIODO_30D, HOJE), (date(2026, 10, 19), HOJE))
        self.assertEqual(calc.intervalo_periodo(config.PERIODO_6M, HOJE), (date(2026, 5, 18), HOJE))
        self.assertEqual(calc.intervalo_periodo(config.PERIODO_1A, HOJE), (date(2025, 11, 18), HOJE))
        self.assertEqual(calc.intervalo_periodo(config.PERIODO_PERSONALIZADO, HOJE, date(2026, 3, 1), date(2026, 2, 1)),
                         (date(2026, 2, 1), date(2026, 3, 1)))
        with self.assertRaises(ValueError):
            calc.intervalo_periodo(config.PERIODO_PERSONALIZADO, HOJE)

    def test_freq(self):
        self.assertEqual(calc.escolher_freq(date(2026, 10, 19), HOJE), "D")
        self.assertEqual(calc.escolher_freq(date(2026, 5, 18), HOJE), "M")

    def test_proximo_recebimento(self):
        self.assertEqual(calc.proximo_recebimento(20, HOJE), date(2026, 11, 20))
        self.assertEqual(calc.proximo_recebimento(5, HOJE), date(2026, 12, 5))
        self.assertEqual(calc.proximo_recebimento(31, date(2027, 1, 31)), date(2027, 1, 31))
        self.assertEqual(calc.proximo_recebimento(31, date(2027, 2, 1)), date(2027, 2, 28))
        self.assertEqual(calc.proximo_recebimento(30, date(2026, 12, 31)), date(2027, 1, 30))

    def test_juros_compostos_formula_fechada(self):
        capital, aporte, taxa, n = 1000.0, 200.0, 1.0, 24
        df = calc.juros_compostos(capital, aporte, taxa, n)
        i = taxa / 100
        esperado = capital * (1 + i) ** n + aporte * ((1 + i) ** n - 1) / i
        self.assertAlmostEqual(df["montante"].iloc[-1], esperado, places=6)
        self.assertEqual(df["investido"].iloc[-1], capital + aporte * n)
        self.assertEqual(len(df), n + 1)

    def test_aporte_necessario(self):
        meta, capital, taxa, n = 10000.0, 500.0, 0.8, 18
        aporte = calc.aporte_necessario(meta, capital, taxa, n)
        final = calc.juros_compostos(capital, aporte, taxa, n)["montante"].iloc[-1]
        self.assertAlmostEqual(final, meta, places=4)
        self.assertAlmostEqual(calc.aporte_necessario(1200, 0, 0, 12), 100)
        self.assertEqual(calc.aporte_necessario(100, 500, 1, 12), 0.0)

    def test_price(self):
        pmt = calc.parcela_price(10000, 1.5, 12)
        self.assertAlmostEqual(pmt, 916.80, places=2)
        t = calc.tabela_price(10000, 1.5, 12)
        self.assertAlmostEqual(t["saldo_devedor"].iloc[-1], 0, places=6)
        self.assertAlmostEqual(t["amortizacao"].sum(), 10000, places=6)
        self.assertAlmostEqual(calc.parcela_price(1200, 0, 12), 100)

    def test_regra_e_reserva(self):
        r = calc.regra_50_30_20(3000)
        self.assertEqual(list(r.values()), [1500, 900, 600])
        self.assertEqual(calc.reserva_emergencia(2000, 6), 12000)

    def test_formatacao(self):
        self.assertEqual(formatar_moeda(1234.5), "R$ 1.234,50")
        self.assertEqual(formatar_moeda(-0.001), "R$ 0,00")
        self.assertEqual(formatar_moeda(-1500), "-R$ 1.500,00")
        self.assertEqual(formatar_moeda(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(formatar_moeda(None), "R$ 0,00")
        self.assertEqual(formatar_pct(12.345), "12,3%")


if __name__ == "__main__":
    unittest.main()
