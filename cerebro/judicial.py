"""Órgano Judicial (Elena): enterarse rápido de lo que resuelve la Corte Suprema, sobre todo el Pleno (que decide la
constitucionalidad, art. 206) y la Sala Tercera (contencioso-administrativo).

Uso: python3 cerebro/judicial.py            (revisa los canales automáticos, analiza lo nuevo y avisa por Telegram)
     python3 cerebro/judicial.py --redactar <id,id…>
Canales (investigación de ChatGPT, Invesitgacion/…report-3 5.md; comprobados el 2026-10-25):
- Automáticos (sin anti-bots): RSS de TVN, La Prensa (general y Judiciales) y Telemetro (Nacionales). Los medios
  publican el mismo día los fallos que la Corte comunica (Panama Ports: comunicado y notas en horas).
- Con el Chrome de la oficina (la web del Órgano Judicial tiene Radware, que no se esquiva): comunicados de la Corte
  y la lista de edictos del Pleno. Entran por el receptor local, como la Gaceta (pendiente).
- Consulta de Fallos (consultafallos.organojudicial.gob.pa) corre sobre vLex: no se lee automáticamente.
La Gaceta publica los fallos de inconstitucionalidad entre 25 y 110 días después: no sirve de alerta.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from cerebro.normativa import REDACCION, ESQUEMA_REDACCION, SECTORES  # noqa: E402
from db import d1  # noqa: E402

NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
# Andrés (2026-10-25): NADA de prensa, solo fuentes de la Corte (comunicados y edictos del Pleno). Esos están detrás
# de Radware y entran con el Chrome de la oficina; mientras tanto no hay fuente automática.
FEEDS = []
# para no mandar todo el diario a la IA: solo lo que nombra a la Corte, sus salas o un fallo constitucional
JUDICIAL = re.compile(r"corte suprema|\bcsj\b|magistrad|inconstitucional|constitucionalidad|pleno de la corte|amparo de garant|"
                      r"sala (tercera|primera|segunda|cuarta|de lo contencioso)|contencioso.administrativ|fallo de la corte|"
                      r"advertencia de inconstitucionalidad|demanda de nulidad", re.I)

ESQUEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"},
    "es_decision": {"type": "boolean", "description": "true si informa una decisión ya tomada por la Corte (fallo, admisión, rechazo)"},
    "tribunal": {"type": "string", "description": "Pleno, Sala Primera, Sala Segunda, Sala Tercera, Sala Cuarta u otro"},
    "proceso": {"type": "string", "description": "inconstitucionalidad, advertencia, amparo, contencioso-administrativo, otro"},
    "nombre": {"type": "string", "description": "3 a 8 palabras: qué resolvió"},
    "resumen": {"type": "string", "description": "dos o tres oraciones neutrales: qué se resolvió, sobre qué norma o acto y a quién afecta"},
    "sectores": {"type": "array", "items": {"type": "string", "enum": SECTORES}},
    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo", "ninguno"]},
    "economica": {"type": "boolean", "description": "true si toca impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o incentivos"},
}, "required": ["id", "es_decision", "tribunal", "proceso", "nombre", "resumen", "sectores", "impacto", "economica"]}}}, "required": ["items"]}

ANALISIS = """Eres Elena, analista judicial de Keyword, consultora de asuntos públicos en Panamá. Recibes notas de prensa y
comunicados sobre la Corte Suprema de Justicia. Para cada una di si informa una DECISIÓN ya tomada por la Corte (no
una demanda recién presentada, una audiencia o una opinión), qué tribunal y qué tipo de proceso, y resume solo lo que
dice el texto. Impacto para empresas: alto si declara (in)constitucional una ley, contrato o norma general o anula un
acto que afecta a un sector; medio si afecta a una empresa o institución importante; bajo o ninguno si es penal
individual, disciplinario o sin efecto económico. "economica" = true si la decisión toca impuestos, tarifas, aranceles,
precios, presupuesto, deuda, salario mínimo, subsidios o incentivos."""


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def limpio(t):
    t = re.sub(r"<!\[CDATA\[|\]\]>", "", t or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(t))).strip()


def fecha_rss(t):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(t).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()


def prensa():
    out, vistos = [], set()
    for medio, url in FEEDS:
        try:
            rss = bajar(url)
        except Exception as e:
            print(f"  {medio}: no respondió ({e})", flush=True)
            continue
        for it in re.findall(r"<item>(.*?)</item>", rss, re.S):
            titulo = limpio((re.findall(r"<title>(.*?)</title>", it, re.S) or [""])[0])
            enlace = limpio((re.findall(r"<link>(.*?)</link>", it, re.S) or [""])[0])
            desc = limpio((re.findall(r"<description>(.*?)</description>", it, re.S) or [""])[0])
            # la sección judicial se toma entera (la IA decide si es una decisión de la Corte); el resto, filtrado
            if not enlace or enlace in vistos or ("judiciales" not in url and not JUDICIAL.search(titulo + " " + desc)):
                continue
            vistos.add(enlace)
            out.append({"canal": "prensa", "fuente": medio, "titulo": titulo, "descripcion": desc[:1500], "url": enlace,
                        "fecha": fecha_rss((re.findall(r"<pubDate>(.*?)</pubDate>", it) or [""])[0])})
    return out


def revisar():
    vistos = {f["id"] for f in d1.consulta("SELECT id FROM judiciales")}
    nuevos = []
    for it in prensa():
        it["id"] = cerebro.huella("judicial", it["url"])
        if it["id"] not in vistos:
            vistos.add(it["id"])
            nuevos.append(it)
    print(f"  prensa: {len(nuevos)} notas nuevas sobre la Corte", flush=True)
    if not nuevos:
        return 0
    for i in range(0, len(nuevos), 10):
        grupo = nuevos[i:i + 10]
        lista = "\n\n".join(f"### id {x['id']}\n{x['fuente']} · {x['fecha']}\n{x['titulo']}\n{x['descripcion']}" for x in grupo)
        r = ia.generar_json(ANALISIS, lista, ESQUEMA)
        por_id = {x["id"]: x for x in r["items"]}
        for x in grupo:
            a = por_id.get(x["id"], {})
            x.update(es_decision=1 if a.get("es_decision") else 0, tribunal=a.get("tribunal", ""), proceso=a.get("proceso", ""),
                     nombre=a.get("nombre") or x["titulo"], resumen=a.get("resumen", ""),
                     sectores=json.dumps(a.get("sectores", []), ensure_ascii=False), impacto=a.get("impacto", "bajo"))
            doc, _ = cerebro.guardar_documento("judicial", x["url"], f"{x['fuente']}: {x['titulo']}\n{x['descripcion']}\n\n{x['resumen']}",
                                               tipo="nota_judicial", titulo=f"{x['fuente']}: {x['titulo']}", url=x["url"],
                                               fecha=x["fecha"], resumen=x["resumen"])
            x["documento"] = doc
    d1.insertar_muchas("judiciales", ["id", "canal", "fuente", "titulo", "descripcion", "url", "fecha", "es_decision", "tribunal",
                                      "proceso", "nombre", "resumen", "sectores", "impacto", "documento", "creado"],
                       [[x["id"], x["canal"], x["fuente"], x["titulo"], x["descripcion"], x["url"], x["fecha"], x["es_decision"],
                         x["tribunal"], x["proceso"], x["nombre"], x["resumen"], x["sectores"], x["impacto"], x["documento"],
                         cerebro.ahora()] for x in nuevos], modo="INSERT OR IGNORE")
    cerebro.enlazar()
    decisiones = [x for x in nuevos if x["es_decision"] and x["impacto"] in ("alto", "medio")]
    if decisiones:
        cerebro.telegram("⚖️ La Corte resolvió:\n" + "\n".join(
            f"• {x['tribunal']} · {x['nombre']} ({x['impacto']}) — {x['fuente']}" for x in decisiones[:8]) +
            "\nMíralo en la oficina (mesa de Elena · Órgano Judicial).", destino="gaceta")
    return len(nuevos)


ESQUEMA_EDICTOS = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "expediente": {"type": "string", "description": "número de entrada o expediente, tal como aparece"},
    "proceso": {"type": "string", "description": "inconstitucionalidad, advertencia de inconstitucionalidad, amparo de garantías, "
                                                  "consulta de constitucionalidad, otro"},
    "es_decision": {"type": "boolean", "description": "true si notifica una resolución que decide (fallo, admisión, rechazo, no viabilidad)"},
    "fecha_resolucion": {"type": "string", "description": "AAAA-MM-DD de la resolución notificada, si aparece; si no, vacío"},
    "nombre": {"type": "string", "description": "3 a 8 palabras: qué resolvió el Pleno"},
    "resumen": {"type": "string", "description": "dos o tres oraciones: quién demandó, contra qué norma o acto, qué resolvió el Pleno"},
    "sectores": {"type": "array", "items": {"type": "string", "enum": SECTORES}},
    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo", "ninguno"]},
    "economica": {"type": "boolean", "description": "true si toca impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o incentivos"},
}, "required": ["expediente", "proceso", "es_decision", "fecha_resolucion", "nombre", "resumen", "sectores", "impacto", "economica"]}}},
    "required": ["items"]}

EDICTOS = """Eres Elena, analista judicial de Keyword, consultora de asuntos públicos en Panamá. Recibes el texto de los
edictos que fijó un día la Secretaría General del Pleno de la Corte Suprema de Justicia. Cada edicto notifica una
resolución de un expediente. Devuelve UNA entrada por expediente (si un expediente aparece varias veces, una sola) con
lo que dice el texto, sin inventar. Impacto para empresas: alto si declara inconstitucional (o constitucional) una
ley, contrato, decreto o norma general, o admite una demanda contra una norma económica relevante; medio si decide
un amparo o advertencia que afecta a una empresa o institución importante; bajo si es un trámite (no admite por
forma, desistimiento) de poco alcance; ninguno si es penal individual o puramente procesal. "economica" = true si
toca impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o incentivos. Si un edicto no es del
Pleno o no se entiende, omítelo."""


def procesar():
    """Analiza lo que trajo la extensión del Chrome de la oficina (edictos del Pleno y comunicados de la Corte)."""
    d1.consulta("CREATE TABLE IF NOT EXISTS judicial_procesados (documento TEXT PRIMARY KEY, creado TEXT)")
    docs = d1.consulta("SELECT id, fuente, titulo, url, fecha FROM documentos WHERE fuente IN ('oj_edicto', 'oj_comunicado') "
                       "AND id NOT IN (SELECT documento FROM judicial_procesados) ORDER BY fecha LIMIT 10")
    filas, avisos = [], []
    for doc in docs:
        texto = cerebro.texto_documento(doc["id"])
        if doc["fuente"] == "oj_edicto":
            # los edictos suelen venir escaneados (sin texto): Gemini lee el PDF, como con la Gaceta
            pdf = os.path.join(cerebro.CARPETA, "salidas", "judicial", doc["url"].rsplit("/", 1)[-1])
            if len(texto) < 500 and os.path.exists(pdf):
                import agente
                uri = agente.gemini_subir(doc["titulo"], open(pdf, "rb").read())
                r = ia.generar_pdf_json(EDICTOS, uri, doc["titulo"], ESQUEMA_EDICTOS)
            else:
                r = ia.generar_json(EDICTOS, f"{doc['titulo']}\n\n{texto[:90000]}", ESQUEMA_EDICTOS)
            for x in r["items"]:
                fila = {"id": cerebro.huella("edicto", doc["url"], x["expediente"]), "canal": "edicto", "fuente": "Edictos del Pleno",
                        "titulo": f"Expediente {x['expediente']} · {x['proceso']}", "descripcion": "", "url": doc["url"],
                        "fecha": x["fecha_resolucion"] or doc["fecha"], "es_decision": 1 if x["es_decision"] else 0,
                        "tribunal": "Pleno", "proceso": x["proceso"], "nombre": x["nombre"], "resumen": x["resumen"],
                        "sectores": json.dumps(x["sectores"], ensure_ascii=False), "impacto": x["impacto"], "documento": doc["id"],
                        "economica": 1 if x.get("economica") else 0}
                filas.append(fila)
        else:
            x = {"id": cerebro.huella("comunicado", doc["url"]), "fuente": "Órgano Judicial", "titulo": doc["titulo"],
                 "descripcion": texto[:1500], "fecha": doc["fecha"]}
            r = ia.generar_json(ANALISIS, f"### id {x['id']}\nComunicado del Órgano Judicial · {doc['fecha']}\n{doc['titulo']}\n{texto[:6000]}", ESQUEMA)
            a = (r["items"] or [{}])[0]
            filas.append({**x, "canal": "comunicado", "url": doc["url"], "es_decision": 1 if a.get("es_decision") else 0,
                          "tribunal": a.get("tribunal", ""), "proceso": a.get("proceso", ""), "nombre": a.get("nombre") or doc["titulo"],
                          "resumen": a.get("resumen", ""), "sectores": json.dumps(a.get("sectores", []), ensure_ascii=False),
                          "impacto": a.get("impacto", "ninguno"), "documento": doc["id"], "economica": 1 if a.get("economica") else 0})
        d1.consulta("INSERT OR IGNORE INTO judicial_procesados (documento, creado) VALUES (?, ?)", [doc["id"], cerebro.ahora()])
    if filas:
        try:
            d1.consulta("ALTER TABLE judiciales ADD COLUMN economica INTEGER")  # para los pases a Tomás (2026-10-26)
        except Exception:
            pass
        d1.insertar_muchas("judiciales", ["id", "canal", "fuente", "titulo", "descripcion", "url", "fecha", "es_decision", "tribunal",
                                          "proceso", "nombre", "resumen", "sectores", "impacto", "documento", "creado", "economica"],
                           [[f["id"], f["canal"], f["fuente"], f["titulo"], f["descripcion"], f["url"], f["fecha"], f["es_decision"],
                             f["tribunal"], f["proceso"], f["nombre"], f["resumen"], f["sectores"], f["impacto"], f["documento"],
                             cerebro.ahora(), f["economica"]] for f in filas], modo="INSERT OR IGNORE")
        avisos = [f for f in filas if f["es_decision"] and f["impacto"] in ("alto", "medio")]
        if avisos:
            from cerebro import pases
            cerebro.telegram("⚖️ La Corte resolvió:\n" + "\n".join(
                f"• {f['tribunal']} · {f['nombre']} ({f['impacto']}) — {'comunicado' if f['canal'] == 'comunicado' else 'edicto'}"
                for f in avisos[:10]) + "".join("\n" + l for l in pases.de_entes("judicial", avisos)) +
                "\nMíralo en la oficina (mesa de Elena · Órgano Judicial).", destino="gaceta", agente="judicial",
                ref="judiciales:" + ",".join(f["id"] for f in avisos[:10]))
    return f"{len(docs)} documentos de la Corte analizados, {len(filas)} entradas, {len(avisos)} avisos"


def redactar(ids):
    """Keymonitor de los fallos que eligió la oficina (con lo que dice la nota; el fallo íntegro, cuando esté)."""
    marcas = ",".join("?" * len(ids))
    hechos = []
    for x in d1.consulta(f"SELECT * FROM judiciales WHERE id IN ({marcas}) AND producto IS NULL", list(ids)):
        texto = cerebro.texto_documento(x["documento"]) if x["documento"] else x["descripcion"]
        instr = REDACCION.replace("Recibes una edición de\nla Gaceta Oficial (PDF) y la lista de normas que la oficina eligió.",
                                  "Recibes la información de un fallo de la Corte Suprema de Justicia que la oficina eligió.")
        r = ia.generar_json(instr + cerebro.ejemplos("Keymonitor"),
                            f"id {x['id']}\nTribunal: {x['tribunal']} · Proceso: {x['proceso']}\nFuente: {x['fuente']} ({x['url']})\n\n{texto[:10000]}",
                            ESQUEMA_REDACCION)
        for k in r["keymonitor"][:1]:
            pid = cerebro.huella("keymonitor", x["id"])
            editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                             "fuentes", "creado", "actualizado"],
                               [[pid, "keymonitor", k["asunto"], None, k["cuerpo"], x["url"], "borrador", "judicial",
                                 json.dumps([x["documento"]] if x["documento"] else []), cerebro.ahora(), cerebro.ahora()]])
            d1.consulta("UPDATE judiciales SET producto = ? WHERE id = ?", [pid, x["id"]])
            hechos.append(k["asunto"])
    if hechos:
        cerebro.telegram("📝 Keymonitor judiciales listos para revisar:\n" + "\n".join("• " + h for h in hechos), destino="gaceta")
    return f"{len(hechos)} Keymonitor en borrador"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "--redactar":
        print(redactar(sys.argv[2].split(",")))
    else:
        print(procesar())
