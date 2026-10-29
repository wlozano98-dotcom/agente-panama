"""Directorio de actores: carga en el cerebro las tablas de la investigación de ChatGPT (Invesitgacion/).

Uso: python3 cerebro/directorio.py [--prueba]
Lee el informe "Directorio verificado de actores…" (diputados, junta directiva, gabinete, autoridades, partidos,
gremios) y el roster oficial del gabinete del informe de normativa (cargo tal como lo escribe Presidencia). Los cargos
se toman tal cual de la fuente: nunca se deduce el género de un nombre.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import alias_de_persona, normal, slug  # noqa: E402
from db import d1  # noqa: E402

CARPETA_INV = os.path.join(cerebro.CARPETA, "Invesitgacion")

# Las 15 comisiones permanentes; la clave es una palabra que basta para reconocerlas en los textos.
COMISIONES = {
    "CREDENCIALES": "Credenciales, Reglamento, Ética Parlamentaria y Asuntos Judiciales",
    "PRESUPUESTO": "Presupuesto",
    "GOBIERNO": "Gobierno, Justicia y Asuntos Constitucionales",
    "RELACIONES EXTERIORES": "Relaciones Exteriores",
    "ECONOMIA": "Economía y Finanzas",
    "COMERCIO": "Comercio y Asuntos Económicos",
    "EDUCACION": "Educación, Cultura y Deportes",
    "INFRAESTRUCTURA": "Infraestructura Pública y Asuntos del Canal",
    "TRABAJO": "Trabajo, Salud y Desarrollo Social",
    "COMUNICACION": "Comunicación y Transporte",
    "AGROPECUARIO": "Asuntos Agropecuarios",
    "POBLACION": "Población, Ambiente y Desarrollo",
    "INDIGENA": "Asuntos Indígenas",
    "MUJER": "Mujer, Niñez, Juventud y Familia",
    "MUNICIPAL": "Asuntos Municipales",
}
PARTIDOS = {"PRD": "Partido Revolucionario Democrático", "RM": "Realizando Metas", "CD": "Cambio Democrático",
            "PP": "Partido Popular", "MOLIRENA": "Molirena", "PAN": "Partido Panameñista",
            "MOCA": "Movimiento Otro Camino", "LP": "Libre Postulación", "ALIANZA": "Partido Alianza"}


def limpiar(celda):
    """Quita negritas, marcas de cita de la investigación y enlaces Markdown (devuelve el texto)."""
    t = re.sub(r"cite.*?", "", celda)        # marcas de cita de ChatGPT
    t = re.sub(r"cite(turn\d+\w+)+", "", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)
    t = t.replace("**", "").replace("<br>", "\n")
    return re.sub(r"[ \t]+", " ", t).strip()


def enlaces(celda):
    return re.findall(r"\((https?://[^)\s]+)\)", celda)


def negritas(celda):
    return [limpiar(n) for n in re.findall(r"\*\*([^*]+)\*\*", celda)]


def tablas(texto):
    """{título de sección: [filas como dict]} de las tablas Markdown del informe."""
    out, seccion, cabecera = {}, None, None
    for linea in texto.splitlines():
        if linea.startswith("#"):
            seccion, cabecera = linea.lstrip("# ").strip(), None
        elif linea.startswith("|---"):
            continue
        elif linea.startswith("|"):
            celdas = [c.strip() for c in linea.strip().strip("|").split(" | ")]
            if cabecera is None:
                cabecera = [limpiar(c) for c in celdas]
            else:
                out.setdefault(seccion, []).append(dict(zip(cabecera, celdas)))
        else:
            cabecera = None if linea.strip() else cabecera
    return out


def comisiones_en(texto):
    """[(nombre oficial, preside)] de un texto como 'Presupuesto; presidente de Gobierno, Justicia…; Credenciales'."""
    out = []
    for parte in re.split(r";", limpiar(texto)):
        n = normal(parte)
        for clave, oficial in COMISIONES.items():
            if clave in n and all(o != oficial for o, _ in out):
                out.append((oficial, bool(re.search(r"\bPRESIDENT", n))))
                break
    return out


def partido_de(texto):
    n = normal(limpiar(texto)).split()
    for sigla in n:
        if sigla in PARTIDOS:
            return sigla
    t = normal(texto)
    for sigla, nombre in PARTIDOS.items():
        if normal(nombre) in t:
            return sigla
    if "PANAMENISTA" in t:
        return "PAN"
    if "OTRO CAMINO" in t:
        return "MOCA"
    if "LIBRE POSTULACION" in t or "INDEPENDIENTE" in t:
        return "LP"
    return None


def persona(nombre, subtipo, cargo=None, datos=None, perfil=None, fuente=None):
    nombre = limpiar(nombre)
    return {"id": f"persona:{slug(nombre)}", "tipo": "persona", "subtipo": subtipo, "nombre": nombre, "cargo": cargo,
            "datos": datos or {}, "perfil": perfil, "fuente": fuente, "alias": alias_de_persona(nombre)}


def institucion(nombre, subtipo="institucion", perfil=None, fuente=None, alias=()):
    nombre = limpiar(nombre)
    return {"id": f"institucion:{slug(nombre)}", "tipo": "institucion", "subtipo": subtipo, "nombre": nombre,
            "perfil": perfil, "fuente": fuente, "alias": {normal(a) for a in alias}}


def cargar(prueba=False):
    informe = next(f for f in glob.glob(os.path.join(CARPETA_INV, "*.md"))
                   if open(f, encoding="utf-8").read(200).startswith("# Directorio verificado de actores"))
    secciones = tablas(open(informe, encoding="utf-8").read())
    entidades, relaciones = {}, []

    def agregar(e):
        e.setdefault("datos", {})
        e.setdefault("alias", set())
        if e["id"] in entidades:  # se completa la que ya estaba
            viejo = entidades[e["id"]]
            viejo["datos"].update(e.get("datos") or {})
            viejo["alias"] |= e.get("alias") or set()
            for k in ("cargo", "perfil", "subtipo", "fuente"):
                viejo[k] = viejo.get(k) or e.get(k)
        else:
            entidades[e["id"]] = e
        return e["id"]

    for clave, oficial in COMISIONES.items():
        agregar({"id": f"comision:{slug(oficial)}", "tipo": "comision", "nombre": f"Comisión de {oficial}",
                 "alias": {normal(f"Comisión de {oficial}")}, "fuente": "Asamblea Nacional"})
    for sigla, nombre in PARTIDOS.items():
        agregar({"id": f"partido:{slug(sigla)}", "tipo": "partido", "nombre": nombre,
                 "alias": {normal(nombre)} | ({sigla} if len(sigla) >= 5 else set())})

    # Diputados
    for f in next(v for k, v in secciones.items() if k.startswith("Diputados")):
        sigla = partido_de(f["Partido; bancada actual / cambios"])
        circuito = limpiar(f["Circuito / provincia"])
        coms = comisiones_en(f["Comisiones 2026-27; presidencia"])
        junta = limpiar(f["Junta Directiva"]).strip("— ")
        datos = {"partido": sigla, "bancada": limpiar(f["Partido; bancada actual / cambios"]), "circuito": circuito,
                 "suplente": limpiar(f["Suplente"]), "comisiones": [c for c, _ in coms],
                 "preside": [c for c, p in coms if p], "junta_directiva": junta or None,
                 "redes": limpiar(f["Redes"]), "fuentes": enlaces(f["Fuente URL"])}
        cargo = f"Asamblea Nacional, circuito {circuito}" + (f" · {sigla}" if sigla else "")
        if junta:
            cargo = f"{junta} · {cargo}"
        d = agregar(persona(f["Diputado"], "diputado", cargo, datos, limpiar(f["Mini perfil de inteligencia pública"]),
                            "Investigación ChatGPT 2026-10-24"))
        if sigla:
            relaciones.append((d, "pertenece_a", f"partido:{slug(sigla)}", None, None, datos["bancada"]))
        for c, preside in coms:
            relaciones.append((d, "preside" if preside else "integra", f"comision:{slug(c)}", None, "2026-07-01",
                               "período 2026-2027"))
        sup = re.sub(r"\[NV.*?\]|\(.*?\)", "", datos["suplente"]).strip()
        if sup and "NV" not in sup and len(sup.split()) >= 2:
            s = agregar(persona(sup, "suplente", f"Suplente de {limpiar(f['Diputado'])}"))
            relaciones.append((s, "suplente_de", d, None, None, None))

    # Gabinete: cargos tal como los escribe Presidencia (roster oficial del informe de normativa)
    cargos_oficiales = {}
    for ruta in glob.glob(os.path.join(CARPETA_INV, "*.md")):
        for k, filas in tablas(open(ruta, encoding="utf-8").read()).items():
            if k.startswith("Gabinete ministerial"):
                for f in filas:
                    cargos_oficiales[normal(limpiar(f["Titular"]))] = limpiar(f["Cargo"])
    for f in next(v for k, v in secciones.items() if k.startswith("Presidente, gabinete")):
        titular = negritas(f["Titular actual"])
        if not titular or "Sin titular" in titular[0]:
            continue
        cartera = limpiar(f["Cargo / cartera"])
        nombre = titular[0]
        cargo = cargos_oficiales.get(normal(nombre)) or (cartera if cartera.startswith("Presidente") else None)
        ministerio = None
        if not cartera.startswith(("Presidente", "Vicepresidente")):
            ministerio = agregar(institucion(cartera if cartera.startswith("Ministerio") else f"Ministerio de {cartera}",
                                             "ministerio"))
        p = persona(nombre, "ministro" if ministerio else "presidente", cargo or f"Titular: {cartera}",
                            {"nombramiento": limpiar(f["Nombramiento / inicio"]), "redes": limpiar(f["Redes verificadas"]),
                             "fuentes": enlaces(f["Fuente URL"])},
                     limpiar(f["Mini perfil / agenda"]), "Investigación ChatGPT 2026-10-24")
        if not ministerio:  # al presidente la prensa lo nombra por el apellido
            apellido = normal(nombre).split()[-2]
            p["alias"] |= {apellido, f"PRESIDENTE {apellido}"}
        d = agregar(p)
        if ministerio:
            relaciones.append((d, "dirige", ministerio, None, None, None))
        # viceministros: "**Nombre**, viceministra de …"
        for m in re.finditer(r"\*\*([^*]+)\*\*,?\s*([^;*\[]*)", f["Viceministro(s) verificados al corte"]):
            vnombre, vcargo = limpiar(m.group(1)), limpiar(m.group(2)).strip(" ,;")
            if len(vnombre.split()) < 2:
                continue
            v = agregar(persona(vnombre, "viceministro", vcargo[:1].upper() + vcargo[1:] if vcargo else None))
            if ministerio:
                relaciones.append((v, "integra", ministerio, None, None, vcargo))

    # Autoridades constitucionales, judiciales y regulatorias
    for f in next(v for k, v in secciones.items() if k.startswith("Autoridades")):
        inst = agregar(institucion(f["Institución / función"]))
        funcion = limpiar(f["Sala / función específica"])
        for nombre in negritas(f["Titular(es) al corte"]) or [limpiar(f["Titular(es) al corte"])]:
            if len(nombre.split()) < 2 or "NV" in nombre:
                continue
            d = agregar(persona(nombre, "autoridad", funcion or None, {"fuentes": enlaces(f["Fuente URL"])},
                                limpiar(f["Perfil o dato clave"]), "Investigación ChatGPT 2026-10-24"))
            relaciones.append((d, "dirige", inst, None, None, funcion))

    # Partidos y gremios: el perfil se guarda en la entidad
    for f in next(v for k, v in secciones.items() if k.startswith("Partidos")):
        sigla = partido_de(f["Actor partidario / bloque"])
        if sigla:
            e = entidades[f"partido:{slug(sigla)}"]
            e["perfil"] = limpiar(f["Relación con Gobierno / posición legislativa"] + "\n" + f["Claves de inteligencia"])
            e["datos"] = {"liderazgo": limpiar(f["Liderazgo actual"]), "diputados": limpiar(f["Diputados"])}
    for f in next(v for k, v in secciones.items() if k.startswith("Gremios")):
        g = agregar(institucion(f["Organización"], "gremio",
                                limpiar(f["Perfil / temas de incidencia"] + "\n" + f["Lectura para asuntos públicos"])))
        for nombre in negritas(f["Líder actual verificado"]):
            if len(nombre.split()) >= 2 and "NV" not in nombre:
                relaciones.append((agregar(persona(nombre, "lider_gremial", None)), "dirige", g, None, None, None))

    # Junta Directiva: relación con la Asamblea
    asamblea = agregar(institucion("Asamblea Nacional", "organo", alias=["Asamblea Nacional de Diputados"]))
    for f in next(v for k, v in secciones.items() if k.startswith("Junta Directiva")):
        nombre = limpiar(f["Titular"])
        pid = f"persona:{slug(nombre)}"
        if pid in entidades and normal(f["Órgano / cargo"]).startswith(("PRESIDENCIA DE LA ASAMBLEA", "PRIMERA", "SEGUNDA")):
            relaciones.append((pid, "junta_directiva", asamblea, None, "2026-07-01", limpiar(f["Órgano / cargo"])))

    # se une cada diputado con su forma de nombre en los proyectos (tabla proponentes del monitor legislativo)
    if not prueba:
        nombres_prop = [r["nombre"] for r in d1.consulta("SELECT DISTINCT nombre FROM proponentes")]
        for e in entidades.values():
            if e.get("subtipo") not in ("diputado", "suplente"):
                continue
            pal = set(normal(e["nombre"]).split())
            calzan = [n for n in nombres_prop if set(normal(n).split()) <= pal or pal <= set(normal(n).split())]
            calzan = [n for n in calzan if len(set(normal(n).split()) & pal) >= 2]
            if len(calzan) == 1:
                e["datos"]["nombre_en_proyectos"] = calzan[0]
                e["alias"] |= alias_de_persona(calzan[0])

    entidades = list(entidades.values())
    resumen = {}
    for e in entidades:
        resumen[e.get("subtipo") or e["tipo"]] = resumen.get(e.get("subtipo") or e["tipo"], 0) + 1
    print("entidades:", resumen, "| relaciones:", len(relaciones))
    if prueba:
        for e in entidades[:3] + [x for x in entidades if x.get("subtipo") == "ministro"][:2]:
            print(json.dumps({k: (sorted(v) if isinstance(v, set) else v) for k, v in e.items()}, ensure_ascii=False)[:700])
        return
    cerebro.crear()
    cerebro.guardar_entidades(entidades)
    cerebro.relacionar(relaciones)
    # la investigación misma entra al cerebro como documento (buscable y citable)
    for ruta in sorted(glob.glob(os.path.join(CARPETA_INV, "*.md"))):
        texto = open(ruta, encoding="utf-8").read()
        titulo = texto.splitlines()[0].lstrip("# ").strip()
        _, nuevo = cerebro.guardar_documento("investigacion", os.path.basename(ruta), limpiar(texto), tipo="investigacion",
                                             titulo=titulo, fecha="2026-10-24")
        print(("nuevo: " if nuevo else "ya estaba: ") + titulo)
    print("enlazados:", cerebro.enlazar())


if __name__ == "__main__":
    cerebro.cargar_env()
    cargar(prueba="--prueba" in sys.argv)
