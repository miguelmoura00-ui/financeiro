"""Constantes e configurações do sistema (sem dependência do Streamlit)."""

CORES = {
    "verde": "#16a34a",     # entradas e resultados positivos
    "vermelho": "#dc2626",  # saídas e despesas
    "azul": "#2563eb",      # saldo e informações gerais
    "laranja": "#f59e0b",   # alertas e pagamentos próximos
    "cinza": "#64748b",
}

CATEGORIAS_ENTRADA = [
    "Salário",
    "Renda extra",
    "Trabalho autônomo",
    "Comissão",
    "Bonificação",
    "Investimentos recebidos",
    "Presente em dinheiro",
    "Outras fontes",
]

CATEGORIAS_DESPESA = [
    "Alimentação",
    "Moradia",
    "Água",
    "Energia elétrica",
    "Internet",
    "Transporte",
    "Combustível",
    "Educação",
    "Saúde",
    "Lazer",
    "Compras",
    "Assinaturas",
    "Cartão de crédito",
    "Outros gastos",
]

FORMAS_PAGAMENTO = [
    "PIX",
    "Dinheiro",
    "Cartão de débito",
    "Cartão de crédito",
    "Boleto",
    "Transferência",
    "Débito automático",
]

STATUS_PAGO = "Pago"
STATUS_PENDENTE = "Pendente"
STATUS_DESPESA = [STATUS_PAGO, STATUS_PENDENTE]

TIPO_FIXA = "Fixa"
TIPO_VARIAVEL = "Variável"
TIPOS_DESPESA = [TIPO_FIXA, TIPO_VARIAVEL]

RENDA_PRINCIPAL = "Principal"
RENDA_SECUNDARIA = "Secundária"
TIPOS_RENDA = [RENDA_PRINCIPAL, RENDA_SECUNDARIA]

MOV_DEPOSITO = "Depósito"
MOV_RETIRADA = "Retirada"
TIPOS_POUPANCA = [MOV_DEPOSITO, MOV_RETIRADA]

# Situação das contas a pagar
SIT_PAGA = "Paga"
SIT_PENDENTE = "Pendente"
SIT_PROXIMA = "Próxima do vencimento"
SIT_ATRASADA = "Atrasada"

# Tipos de movimentação no histórico
MOV_ENTRADA = "Entrada"
MOV_SAIDA = "Saída"
MOV_POUP_DEP = "Poupança (depósito)"
MOV_POUP_RET = "Poupança (retirada)"

DIAS_ALERTA_VENCIMENTO = 7       # conta "próxima" se vence em até N dias
LIMITE_ALERTA_ORCAMENTO = 0.8    # alerta quando 80% do limite foi usado

PERIODO_7D = "Últimos 7 dias"
PERIODO_30D = "Últimos 30 dias"
PERIODO_6M = "Últimos 6 meses"
PERIODO_1A = "Último ano"
PERIODO_PERSONALIZADO = "Período personalizado"
PERIODOS = [PERIODO_7D, PERIODO_30D, PERIODO_6M, PERIODO_1A, PERIODO_PERSONALIZADO]
