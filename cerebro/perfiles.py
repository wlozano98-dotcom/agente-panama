"""Carga los perfiles de actores que investiga ChatGPT (tandas en Invesitgacion/, no se suben) al cerebro.

Uso: python3 cerebro/perfiles.py
Cada informe entra entero como "investigacion"; además, cada bloque "## Nombre" que trae subsecciones de perfil
(### Estudios, ### Trayectoria…) entra como documento propio (fuente "investigacion_perfil"), así el enlazador lo une
a la persona y Kiwi y el Perfilador lo leen completo. No duplica: se puede correr cada vez que llega una tanda.
"""
import difflib
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro.directorio import CARPETA_INV, limpiar  # noqa: E402
from db import d1  # noqa: E402

GENERALES = {"resumen ejecutivo", "mapa vigente y nombramientos", "fuentes", "metodología", "metodologia"}


def cargar():
    nuevos = 0
    for ruta in sorted(glob.glob(os.path.join(CARPETA_INV, "*.md"))):
        texto = open(ruta, encoding="utf-8").read()
        titulo = texto.splitlines()[0].lstrip("# ").strip()
        archivo = os.path.basename(ruta)
        _, nuevo = cerebro.guardar_documento("investigacion", archivo, limpiar(texto), tipo="investigacion",
                                             titulo=titulo, fecha=cerebro.ahora()[:10])
        nuevos += nuevo
        # bloques de perfil: "## Nombre" con sus subsecciones (### Estudios, ### Trayectoria…)
        bloques = re.split(r"^## ", texto, flags=re.M)[1:]
        for b in bloques:
            nombre = b.splitlines()[0].strip()
            if nombre.lower() in GENERALES or not re.search(r"^### (Estudios|Trayectoria)", b, re.M):
                continue
            _, nuevo = cerebro.guardar_documento("investigacion_perfil", f"{archivo}#{nombre}", limpiar("## " + b),
                                                 tipo="perfil", titulo=f"Perfil de {nombre} ({titulo})",
                                                 fecha=cerebro.ahora()[:10])
            nuevos += nuevo
            print(("nuevo: " if nuevo else "ya estaba: ") + nombre)
    print("personas nuevas en el directorio:", sumar_personas())
    print("documentos nuevos:", nuevos, "| enlazados:", cerebro.enlazar())


def apretado(nombre):
    """El nombre sin tildes, espacios ni signos y sin letras repetidas: para comparar escrituras distintas."""
    return re.sub(r"(.)\1+", r"\1", cerebro.normal(nombre).replace(" ", ""))


def sumar_personas():
    """Quien tiene perfil investigado pero no está en el directorio (viceministros, secretarios de la Asamblea…) entra
    como persona nueva, con el cargo tal como lo escribe la investigación ("Cargo actual: …")."""
    personas = d1.consulta("SELECT id, nombre FROM entidades WHERE tipo = 'persona'")
    nuevas = {}
    for ruta in sorted(glob.glob(os.path.join(CARPETA_INV, "*.md"))):
        for b in re.split(r"^## ", open(ruta, encoding="utf-8").read(), flags=re.M)[1:]:
            nombre = re.sub(r"\s*\[[^\]]*\]", "", b.splitlines()[0]).strip()
            m = re.search(r"\*\*Cargo actual:\*\*\s*(.+)", b)
            if not m or not re.search(r"^### (Estudios|Trayectoria)", b, re.M):
                continue
            if cerebro.fichas_de_personas(nombre, personas) or cerebro.fichas_de_personas(nombre, list(nuevas.values())):
                continue
            # la misma persona escrita distinto (D’Orcy / D'Orcy, Degracia / de Gracia, Yesica / Yessica) no es nueva
            if any(difflib.SequenceMatcher(None, apretado(nombre), apretado(p["nombre"])).ratio() >= .9 for p in personas):
                continue
            if re.match(r"H\.?\s*D\b", m.group(1).strip()):  # "H.D": es diputado y ya debería estar en el directorio
                print(f"  ? {nombre}: diputado que no calza con el directorio (revisar el nombre)")
                continue
            cargo = limpiar(m.group(1)).split(". ")[0].split(";")[0].split(", luego")[0].split(" desde ")[0].strip(" .")[:140]
            cargo = cargo[:1].upper() + cargo[1:]
            subtipo = "viceministro" if re.search(r"viceminist", cargo, re.I) else "ministro" if re.match(r"ministr", cargo, re.I) \
                else "autoridad"
            nuevas[nombre] = {"id": "persona:" + cerebro.slug(nombre), "tipo": "persona", "subtipo": subtipo, "nombre": nombre,
                              "cargo": cargo, "datos": {}, "fuente": os.path.basename(ruta),
                              "alias": set(cerebro.alias_de_persona(nombre))}
    cerebro.guardar_entidades(list(nuevas.values()))
    for e in nuevas.values():
        print(f"  + {e['nombre']}: {e['cargo']} ({e['subtipo']})")
    return len(nuevas)


if __name__ == "__main__":
    cerebro.cargar_env()
    cargar()
