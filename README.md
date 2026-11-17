# 💰 Controle Financeiro Pessoal

Aplicativo de gestão financeira feito com **Python + Streamlit + Pandas + Plotly + SQLite**.
Os dados ficam em um único arquivo local (`data/financas.db`), sem conta nem internet.

## Como executar

```bash
# 1. (recomendado) crie um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. instale as dependências
pip install -r requirements.txt

# 3. confira o ambiente (versão do Python e bibliotecas)
python verificar_ambiente.py

# 4. abra o aplicativo
streamlit run app.py
```

Na primeira vez o banco está vazio: use **✨ Carregar dados de exemplo** na barra lateral para conhecer o sistema, ou comece cadastrando a sua renda.

## Compatibilidade com Python 3.15.2

O projeto usa apenas recursos padrão do Python (3.10+). A camada de dados e os cálculos (`database.py`, `calculos.py`)
têm testes automatizados que passam em Python 3.13 com pandas 3.0; as páginas do Streamlit foram exercitadas
com Streamlit/Plotly simulados, **mas ainda não foram executadas com as bibliotecas reais** — abra o app e navegue
por todas as páginas antes de confiar nele para valer.

Segundo um guia de upgrade consultado, numpy 2.5, pandas 3.0.6 e pyarrow 26 já publicavam pacotes prontos para o 3.15
(testado só em macOS com Apple silicon). **Streamlit e Plotly não puderam ser confirmados** para o 3.15 — por isso o
`verificar_ambiente.py`. Se o `pip install` falhar no 3.15, use Python 3.14 ou 3.13 num ambiente virtual.

## Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | Ponto de entrada e navegação |
| `database.py` | Banco SQLite: tabelas, CRUD e operações compostas (pagar conta, histórico de renda…) |
| `calculos.py` | Todas as regras e cálculos (sem Streamlit, testável) |
| `config.py` | Categorias, cores e constantes |
| `formatacao.py` | Moeda, porcentagem e data no padrão brasileiro |
| `ui.py` | Cartões coloridos, barras de progresso, seletor de período |
| `seed.py` | Dados de exemplo |
| `views/` | Uma página por arquivo: painel, entradas, despesas, renda, planejamento, poupança, contas, gráficos, histórico e calculadoras |
| `tests/` | Testes automatizados da camada de dados e dos cálculos |

Para mudar categorias, formas de pagamento ou cores, edite o `config.py`.

## Como os números são calculados

- **Gasto** = despesas com status *Pago*.
- **Saldo disponível** = todas as entradas − despesas pagas − dinheiro guardado na poupança.
- **Economizado no mês** = recebido no mês − gasto no mês; **% economizado** = isso ÷ recebido no mês.
- **Contas a pagar**: ao marcar uma conta como paga, o sistema cria a despesa correspondente (e remove se você desfizer o pagamento), evitando contar duas vezes. Uma conta é *próxima* se vence em até 7 dias e *atrasada* depois do vencimento.
- **Orçamento por categoria**: considera despesas pagas **e** pendentes do mês (dinheiro já comprometido). Alerta amarelo a partir de 80% do limite e vermelho acima de 100%.
- **Poupança**: cada depósito/retirada pode ser ligado a uma meta; não é possível retirar mais do que há na meta (ou na reserva geral).

## Testes

```bash
python -m unittest discover -s tests -v
```

## Backup

O botão **⬇️ Backup do banco** na barra lateral baixa o arquivo SQLite. Para restaurar, substitua `data/financas.db` por ele.
