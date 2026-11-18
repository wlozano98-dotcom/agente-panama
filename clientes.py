"""Cruce LOCAL de lo que encuentran los agentes con los clientes (los nombres nunca pasan por Gemini).

La ficha de clientes NO está en el repo (es público): se lee del secreto/variable CLIENTES_JSON o, en la máquina de la
oficina, de datos/clientes_privados.json (en .gitignore). Forma:

{"<Cliente>": {"sector": ["ALIMENTOS"],            # sectores del catálogo (OTROS e INDUSTRIAS no cuentan: son generales)
               "temas": ["Tema", ...],    # temas que Gemini puede marcar en las fichas (sin nombres)
               "nombres": ["Razón social", "Marca"], # razones sociales y marcas distintivas: si aparecen, P1
               "palabras": ["frase clave", ...]}}  # frases que, si aparecen en el título o resumen, lo marcan

Un aviso lleva al cliente si coincide el sector, un tema, un nombre o una palabra clave. `motivo` dice cuál.
"""
import json
import os
import re
import unicodedata

CARPETA = os.path.dirname(os.path.abspath(__file__))
PRIVADO = os.path.join(CARPETA, "datos", "clientes_privados.json")
GENERALES = {"OTROS", "INDUSTRIAS", "TODAS LAS EMPRESAS"}


def _cargar():
    crudo = os.environ.get("CLIENTES_JSON")
    if not crudo and os.path.exists(PRIVADO):
        crudo = open(PRIVADO, encoding="utf-8").read()
    try:
        datos = json.loads(crudo) if crudo else {}
    except ValueError:
        datos = {}
    return {k: v for k, v in datos.items() if not k.startswith("_")}


CLIENTES = _cargar()


def normal(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return " " + re.sub(r"[^a-z0-9ñ]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")) + " "


def _lista(x):
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            x = [x] if x else []
    return set(x or [])


def temas():
    return sorted({t for c in CLIENTES.values() for t in c.get("temas", [])})


def afectados(sectores=(), temas_=(), texto=""):
    """{cliente: motivo} — motivo: 'menciona X', 'tema X', 'palabra X' o 'sector X' (el más fuerte primero)."""
    sectores, temas_, t = _lista(sectores) - GENERALES, _lista(temas_), normal(texto)
    salida = {}
    for nombre, c in CLIENTES.items():
        motivo = (next((f"menciona {n}" for n in c.get("nombres", []) if normal(n) in t), None)
                  or next((f"tema {x}" for x in c.get("temas", []) if x in temas_), None)
                  or next((f"«{p}»" for p in c.get("palabras", []) if normal(p) in t), None)
                  or next((f"sector {s}" for s in _lista(c.get("sector")) if s in sectores), None))
        if motivo:
            salida[nombre] = motivo
    return salida


def enmascarar(texto, extra=()):
    """Tapa con [cliente] los nombres y marcas de los clientes (y `extra`) antes de mandar un texto a un modelo externo."""
    texto = str(texto or "")
    nombres = [n for c, d in CLIENTES.items() for n in [c] + list(d.get("nombres", []))] + list(extra)
    for n in sorted({n for n in nombres if n and len(n) > 2}, key=len, reverse=True):
        patron = "".join("[" + re.escape(ch) + re.escape(normal(ch).strip() or ch).upper() + re.escape(normal(ch).strip()) + "]"
                         if normal(ch).strip() and normal(ch).strip() != ch.lower() else re.escape(ch) for ch in n)
        texto = re.sub(r"(?<!\w)" + patron + r"(?!\w)", "[cliente]", texto, flags=re.I)
    return texto


def linea(sectores=(), temas_=(), texto="", html=False):
    """'👥 Cliente (menciona Marca)' o '' si no toca a ningún cliente."""
    a = afectados(sectores, temas_, texto)
    if not a:
        return ""
    txt = ", ".join(f"{n} ({m})" for n, m in a.items())
    if html:
        txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "👥 " + txt


if __name__ == "__main__":
    import sys
    print(f"{len(CLIENTES)} clientes: {', '.join(CLIENTES) or '—'}")
    if len(sys.argv) > 1:
        print(afectados(texto=" ".join(sys.argv[1:])) or "ninguno")
