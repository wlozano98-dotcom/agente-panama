"""El mapa del cerebro (2026-10-26, BORRADOR para que Andrés lo revise; no está en la oficina publicada): dibuja la
memoria conectada como una red. Puntos = personas, instituciones, comisiones, partidos, proyectos de ley y
documentos; líneas = relaciones del directorio (integra, preside, suplente de, dirige, pertenece a), proyectos que
presentó cada diputado (proponentes) y menciones (un actor aparece en un documento).

Uso: python3 cerebro/mapa.py      → salidas/mapa/mapa_cerebro.html (se abre en el navegador; no se sube a ningún lado)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

SALIDA = os.path.join(cerebro.CARPETA, "salidas", "mapa", "mapa_cerebro.html")
RELACION = {"integra": "integra", "preside": "preside", "pertenece_a": "pertenece a", "suplente_de": "suplente de",
            "dirige": "dirige", "junta_directiva": "junta directiva", "presento": "presentó", "menciona": "aparece en"}
FUENTE = {"youtube_asamblea": ("Sesión transcrita", "legal"), "gaceta": ("Gaceta Oficial", "legal"),
          "gaceta_norma": ("Norma de la Gaceta", "legal"), "gaceta_texto": ("Norma de la Gaceta", "legal"),
          "oj_edicto": ("Edicto de la Corte", "legal"), "oj_comunicado": ("Comunicado de la Corte", "legal"),
          "regulador": ("Ente regulador", "legal"), "entrevista": ("Entrevista", "politica"),
          "investigacion": ("Investigación", "politica"), "investigacion_perfil": ("Perfil investigado", "politica"),
          "inec": ("INEC", "economica"), "energia": ("Secretaría de Energía", "economica")}
PROYECTOS_MAX = 350


def datos():
    nodos, lineas = {}, []
    for e in d1.consulta("SELECT id, tipo, subtipo, nombre, cargo, datos FROM entidades"):
        d = json.loads(e["datos"] or "{}")
        nodos[e["id"]] = {"id": e["id"], "tipo": e["tipo"], "sub": e["subtipo"] or "", "nombre": e["nombre"],
                          "cargo": e["cargo"] or "", "partido": d.get("partido") or "", "area": "actores"}
    for r in d1.consulta("SELECT origen, tipo, destino, detalle FROM relaciones"):
        if r["origen"] in nodos and r["destino"] in nodos:
            lineas.append({"a": r["origen"], "b": r["destino"], "t": r["tipo"], "d": r["detalle"] or ""})
    # documentos donde aparece algún actor
    docs = {}
    for m in d1.consulta("SELECT m.documento, m.entidad, d.fuente, d.titulo, d.fecha, d.url, d.creado FROM menciones m "
                         "JOIN documentos d ON d.id = m.documento"):
        if m["entidad"] not in nodos:
            continue
        if m["documento"] not in docs:
            etiqueta, area = FUENTE.get(m["fuente"], (m["fuente"], "legal"))
            docs[m["documento"]] = {"id": m["documento"], "tipo": "documento", "sub": etiqueta, "nombre": m["titulo"] or etiqueta,
                                    "cargo": (m["fecha"] or "")[:10], "url": m["url"] or "", "area": area,
                                    "nuevo": (m["creado"] or "") >= cerebro.ahora()[:10]}
        lineas.append({"a": m["entidad"], "b": m["documento"], "t": "menciona", "d": ""})
    nodos.update(docs)
    # proyectos de ley presentados por actores del directorio (el principal), los más recientes
    por_nombre = {}
    for e in d1.consulta("SELECT id, datos FROM entidades WHERE tipo = 'persona'"):
        n = json.loads(e["datos"] or "{}").get("nombre_en_proyectos")
        if n:
            por_nombre[n] = e["id"]
    filas = d1.consulta("SELECT p.ficha, p.titulo, p.titulo_corto, p.etapa, p.fecha_presentacion, x.nombre FROM proponentes x "
                        "JOIN proyectos p ON p.ficha = x.ficha WHERE x.principal = 1 ORDER BY p.fecha_presentacion DESC")
    n = 0
    for f in filas:
        actor = por_nombre.get(f["nombre"])
        if not actor or n >= PROYECTOS_MAX:
            continue
        pid = f"proyecto:{f['ficha']}"
        if pid not in nodos:
            nodos[pid] = {"id": pid, "tipo": "proyecto", "sub": f["etapa"] or "", "area": "legal",
                          "nombre": f["titulo_corto"] or (f["titulo"] or "")[:90], "cargo": (f["fecha_presentacion"] or "")[:10]}
            n += 1
        lineas.append({"a": actor, "b": pid, "t": "presento", "d": ""})
    # se quitan los actores sueltos (sin ninguna línea): no aportan al dibujo
    usados = {l["a"] for l in lineas} | {l["b"] for l in lineas}
    return [x for k, x in nodos.items() if k in usados], lineas


def escribir():
    nodos, lineas = datos()
    plantilla = open(os.path.join(cerebro.CARPETA, "diseno", "mapa.html"), encoding="utf-8").read()
    html = plantilla.replace("__DATOS__", json.dumps({"nodos": nodos, "lineas": lineas, "relacion": RELACION,
                                                      "fecha": cerebro.ahora()[:16].replace("T", " ")}, ensure_ascii=False))
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    open(SALIDA, "w", encoding="utf-8").write(html)
    return f"{len(nodos)} puntos y {len(lineas)} líneas → {SALIDA}"


if __name__ == "__main__":
    cerebro.cargar_env()
    print(escribir())
