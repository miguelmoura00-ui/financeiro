"""Verifica se o ambiente atende ao projeto.  Uso:  python verificar_ambiente.py"""
import importlib
import sqlite3
import sys

ALVO = (3, 15, 2)
MINIMAS = {"streamlit": (1, 40), "pandas": (2, 2), "plotly": (5, 24)}


def versao_tupla(texto: str) -> tuple:
    partes = []
    for p in texto.split("."):
        digitos = "".join(ch for ch in p if ch.isdigit())
        if not digitos:
            break
        partes.append(int(digitos))
    return tuple(partes)


def main() -> int:
    problemas = 0
    atual = sys.version_info[:3]
    print(f"Python em uso: {'.'.join(map(str, atual))}")
    if atual < (3, 10):
        print("  ✗ O código usa sintaxe de Python 3.10+ (ex.: `str | None`). Atualize o Python.")
        problemas += 1
    elif atual < ALVO:
        print(f"  ! Você pediu Python {'.'.join(map(str, ALVO))}; este funciona, mas é mais antigo.")
    else:
        print("  ✓ Versão do Python adequada.")

    print(f"SQLite: {sqlite3.sqlite_version} ✓")

    for nome, minima in MINIMAS.items():
        try:
            modulo = importlib.import_module(nome)
        except ImportError as erro:
            print(f"{nome}: ✗ não instalado ({erro}). Rode: pip install -r requirements.txt")
            problemas += 1
            continue
        versao = getattr(modulo, "__version__", "?")
        if versao_tupla(versao) < minima:
            print(f"{nome}: ✗ versão {versao} (mínimo {'.'.join(map(str, minima))})")
            problemas += 1
        else:
            print(f"{nome}: {versao} ✓")

    print()
    if problemas:
        print(f"{problemas} problema(s) encontrado(s).")
        print("Se o pip falhar ao instalar no Python 3.15 (por exemplo, por falta de wheel de alguma dependência "
              "como pyarrow ou pillow), use um ambiente com Python 3.14 ou 3.13, que têm suporte mais maduro.")
    else:
        print("Tudo certo! Rode:  streamlit run app.py")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
