"""Entes Reguladores: resoluciones, acuerdos y consultas públicas de los reguladores de Panamá.

Uso: python3 cerebro/reguladores.py            (revisa todas las fuentes, analiza lo nuevo y avisa por Telegram)
     python3 cerebro/reguladores.py --redactar <id,id…>   (Keymonitor de lo que eligió la oficina)
Fuentes (investigación de ChatGPT en Invesitgacion/, comprobadas el 2026-10-25; ninguna tiene anti-bots):
ASEP (API de WordPress: resoluciones y avisos de electricidad, telecomunicaciones, agua, radio y TV), Superintendencia
de Seguros (acuerdos en consulta pública y acuerdos), SMV (proyectos de acuerdo y acuerdos del año, API de WordPress),
Superintendencia de Bancos (acuerdos del año) y DGNTI/MICI (consulta pública de reglamentos técnicos). ACODECO no:
no publica normas (Andrés, 2026-10-25: si no genera normativa, no entra).
Cada aviso nuevo entra a la tabla `regulatorias` con resumen, sectores e impacto (Gemini); su texto, al cerebro. La
primera vez que se lee una fuente solo se analiza lo reciente: lo viejo queda como "base" (visto, sin aviso).
"""
import datetime
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from cerebro.normativa import REDACCION, ESQUEMA_REDACCION, SECTORES  # noqa: E402
from db import d1  # noqa: E402

NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
DIAS_INICIO = 45  # solo se analiza lo de los últimos 45 días (o, la primera vez, lo último de cada fuente)

ESQUEMA_ANALISIS = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"},
    "nombre": {"type": "string", "description": "nombre corto de 3 a 8 palabras, en español, que diga de qué trata"},
    "resumen": {"type": "string", "description": "dos o tres oraciones: qué decide o propone, a quién afecta y desde cuándo"},
    "sectores": {"type": "array", "items": {"type": "string", "enum": SECTORES}},
    "impacto": {"type": "string", "enum": ["alto", "medio", "bajo", "ninguno"]},
    "plazo": {"type": "string", "description": "si es consulta pública: fecha límite para comentarios AAAA-MM-DD; si no, vacío"},
    "economica": {"type": "boolean", "description": "true si toca impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o incentivos"},
}, "required": ["id", "nombre", "resumen", "sectores", "impacto", "plazo", "economica"]}}}, "required": ["items"]}

ANALISIS = """Eres el analista de Entes Reguladores de Keyword, consultora de asuntos públicos en Panamá. Recibes
resoluciones, acuerdos, avisos y consultas públicas de reguladores (ASEP, superintendencias, MICI). Para cada uno:
nombre corto, resumen neutral (solo lo que dice el texto), sectores empresariales afectados e impacto para empresas:
- alto: cambia reglas generales de un sector (tarifas, requisitos, normas técnicas obligatorias, reglamentos, multas
  generales) o abre una consulta pública de una norma general;
- medio: afecta a una empresa grande o a un servicio público de forma relevante (licencias de generación, concesiones,
  medidas a distribuidoras, sanciones importantes);
- bajo: trámites individuales de poco alcance; ninguno: actas, edictos de reclamo, nombramientos internos.
Si es consulta pública y el texto dice hasta cuándo se reciben comentarios, pon esa fecha en "plazo".
"economica" = true si toca impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o
incentivos."""


def bajar(url, binario=False):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = r.read()
    return datos if binario else datos.decode("utf-8", "ignore")


def limpio(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(t or ""))).strip()


def titulo_de_archivo(url):
    """"Acuerdo-Consulta-Publica-002-2026.pdf" → "Acuerdo Consulta Publica 002 2026"."""
    nombre = urllib.parse.unquote(url.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    return re.sub(r"[_-]+", " ", nombre).strip()


def enlaces(pagina, base, patron):
    """Enlaces a documentos (pdf, doc, xls) de una página, con su texto si lo tiene."""
    out, vistos = [], set()
    for href, texto in re.findall(r'<a[^>]+href="([^"]+\.(?:pdf|docx?|xlsx?))"[^>]*>(.*?)</a>', pagina, re.S | re.I):
        url = urllib.parse.urljoin(base, html.unescape(href))
        if url in vistos or not re.search(patron, url, re.I):
            continue
        vistos.add(url)
        out.append((url, limpio(texto)))
    return out


# ---------------------------------------------------------------- fuentes

def asep():
    cats = {278: "Electricidad", 108: "Telecomunicaciones", 110: "Agua y alcantarillado", 111: "Radio y televisión",
            64: "Electricidad", 95: "Telecomunicaciones", 97: "Agua y alcantarillado"}
    avisos = {64, 95, 97}
    # sector por sector: si se piden juntos, la electricidad (la que más publica) tapa a los demás
    posts = []
    for c in cats:
        posts += json.loads(bajar(f"https://asep.gob.pa/wp-json/wp/v2/posts?categories={c}&per_page=20"
                                  "&_fields=id,date,title,link,content,categories"))
    out = []
    for p in posts:
        c = p["categories"][0] if p["categories"] else 278
        texto = limpio(p["content"]["rendered"])
        if c == 95 and re.match(r"Acta de recepción", texto):  # recepción de solicitudes de frecuencias: rutina
            continue
        pdf = re.findall(r'href="([^"]+\.pdf)"', p["content"]["rendered"])
        out.append({"fuente": "asep", "ente": "ASEP · " + cats.get(c, ""), "tipo": "aviso" if c in avisos else "resolucion",
                    "titulo": limpio(p["title"]["rendered"]), "descripcion": texto[:1500],
                    "url": urllib.parse.urljoin("https://asep.gob.pa/", pdf[0]) if pdf else p["link"], "fecha": p["date"][:10]})
    return out


def superseguros():
    out = []
    for pagina, tipo in (("https://superseguros.gob.pa/legal/acuerdos-en-consulta-publica/", "consulta"),
                         ("https://superseguros.gob.pa/legal/acuerdos-y-fallos/", "acuerdo")):
        for url, texto in enlaces(bajar(pagina), pagina, r"20\d\d"):
            out.append({"fuente": "superseguros", "ente": "Superintendencia de Seguros", "tipo": tipo,
                        "titulo": texto or titulo_de_archivo(url), "descripcion": "", "url": url, "fecha": None})
    return out


def smv():
    out, ano = [], datetime.date.today().year
    for slug, tipo in ((f"proyectos-de-acuerdo-{ano}", "consulta"), (f"acuerdos-{ano}", "acuerdo")):
        paginas = json.loads(bajar(f"https://supervalores.gob.pa/wp-json/wp/v2/pages?slug={slug}&_fields=link,content"))
        for p in paginas:
            for url, texto in enlaces(p["content"]["rendered"], p["link"], r"."):
                out.append({"fuente": "smv", "ente": "Superintendencia del Mercado de Valores", "tipo": tipo,
                            "titulo": texto if texto and not texto.startswith("http") else titulo_de_archivo(url),
                            "descripcion": "", "url": url, "fecha": None})
    return out


def superbancos():
    ano = datetime.date.today().year
    pagina = "https://www.superbancos.gob.pa/acuerdos/bancarios"
    return [{"fuente": "superbancos", "ente": "Superintendencia de Bancos", "tipo": "acuerdo",
             "titulo": texto or titulo_de_archivo(url), "descripcion": "", "url": url, "fecha": None}
            for url, texto in enlaces(bajar(pagina), pagina, rf"/acuerdos/{ano}/")]


def dgnti():
    pagina = "https://mici.gob.pa/dgnti-consulta-publica/"
    return [{"fuente": "dgnti", "ente": "MICI · DGNTI (reglamentos técnicos)", "tipo": "consulta",
             "titulo": titulo_de_archivo(url), "descripcion": "", "url": url, "fecha": None}
            for url, texto in enlaces(bajar(pagina), pagina, r"/uploads/20\d\d/")
            if not re.search(r"reglamento-interno|comite", url, re.I)]


FUENTES = [asep, superseguros, smv, superbancos, dgnti]


# ---------------------------------------------------------------- revisar, analizar, avisar

def texto_pdf(url):
    import pypdf
    try:
        lector = pypdf.PdfReader(io.BytesIO(bajar(url, binario=True)))
        return "\n".join((p.extract_text() or "") for p in lector.pages[:6]).strip()[:7000]
    except Exception as e:
        print(f"  no pude leer {url}: {e}", flush=True)
        return ""


def revisar():
    """Lee todas las fuentes; analiza y guarda lo nuevo; avisa por Telegram. Devuelve cuántos avisos nuevos hubo."""
    hoy = datetime.date.today().isoformat()
    vistos = {f["id"] for f in d1.consulta("SELECT id FROM regulatorias")}
    conocidas = {f["fuente"] for f in d1.consulta("SELECT DISTINCT fuente FROM regulatorias")}
    nuevos, base = [], []
    for fuente in FUENTES:
        try:
            items = fuente()
        except Exception as e:
            print(f"  {fuente.__name__}: no respondió ({e})", flush=True)
            continue
        frescos = []
        for it in items:
            it["id"] = cerebro.huella("regulador", it["url"], it["titulo"])
            if it["id"] not in vistos:
                vistos.add(it["id"])
                frescos.append(it)
        limite = (datetime.date.today() - datetime.timedelta(days=DIAS_INICIO)).isoformat()
        viejos = [i for i in frescos if i["fecha"] and i["fecha"] < limite]
        base += viejos
        frescos = [i for i in frescos if i not in viejos]
        if fuente.__name__ not in conocidas and frescos:
            # primera vez: lo reciente se analiza; lo viejo queda visto
            recientes = [i for i in frescos if (i["fecha"] or "") >= limite] or frescos[:3]
            base += [i for i in frescos if i not in recientes]
            frescos = recientes
        nuevos += frescos
        print(f"  {fuente.__name__}: {len(items)} publicados, {len(frescos)} nuevos", flush=True)
    for it in base:
        it.update(nombre=it["titulo"], resumen="", sectores="[]", impacto="base", plazo="", documento=None, economica=0)
    if base:
        guardar(base, hoy)
    if not nuevos:
        return 0
    for it in nuevos:  # el texto: la descripción (ASEP) o el comienzo del PDF
        it["texto"] = it["descripcion"] or (texto_pdf(it["url"]) if it["url"].lower().endswith(".pdf") else "")
    for i in range(0, len(nuevos), 10):
        grupo = nuevos[i:i + 10]
        lista = "\n\n".join(f"### id {it['id']}\nEnte: {it['ente']} · tipo: {it['tipo']} · título: {it['titulo']}\n"
                            f"{(it['texto'] or '(sin texto: usa el título)')[:3500]}" for it in grupo)
        r = ia.generar_json(ANALISIS, lista, ESQUEMA_ANALISIS)
        por_id = {x["id"]: x for x in r["items"]}
        for it in grupo:
            a = por_id.get(it["id"], {})
            it.update(nombre=a.get("nombre") or it["titulo"], resumen=a.get("resumen", ""),
                      sectores=json.dumps(a.get("sectores", []), ensure_ascii=False), impacto=a.get("impacto", "bajo"),
                      plazo=a.get("plazo", ""), economica=1 if a.get("economica") else 0)
            doc, _ = cerebro.guardar_documento("regulador", it["url"], f"{it['ente']}. {it['titulo']}.\n{it['resumen']}\n\n{it['texto']}",
                                               tipo=it["tipo"], titulo=f"{it['ente']}: {it['nombre']}", url=it["url"],
                                               fecha=it["fecha"] or hoy, resumen=it["resumen"])
            it["documento"] = doc
    guardar(nuevos, hoy)
    cerebro.enlazar()
    avisar(nuevos)
    return len(nuevos)


def guardar(items, hoy):
    try:
        d1.consulta("ALTER TABLE regulatorias ADD COLUMN economica INTEGER")  # para los pases a Tomás (2026-10-26)
    except Exception:
        pass
    d1.insertar_muchas("regulatorias", ["id", "fuente", "ente", "tipo", "titulo", "nombre", "descripcion", "url", "fecha",
                                        "resumen", "sectores", "impacto", "plazo", "documento", "creado", "economica"],
                       [[i["id"], i["fuente"], i["ente"], i["tipo"], i["titulo"], i["nombre"], (i.get("descripcion") or "")[:1500],
                         i["url"], i["fecha"] or hoy, i["resumen"], i["sectores"], i["impacto"], i["plazo"] or None,
                         i["documento"], cerebro.ahora(), i.get("economica", 0)] for i in items], modo="INSERT OR IGNORE")


def avisar(nuevos):
    importantes = [i for i in nuevos if i["impacto"] in ("alto", "medio") or i["tipo"] == "consulta"]
    lineas = [f"🏛 Entes Reguladores: {len(nuevos)} publicaciones nuevas, {len(importantes)} para mirar."]
    for i in importantes[:12]:
        extra = f" · comentarios hasta {i['plazo']}" if i["plazo"] else ""
        lineas.append(f"• {'Consulta pública · ' if i['tipo'] == 'consulta' else ''}{i['ente']}: {i['nombre']} "
                      f"({i['impacto']}){extra}")
    from cerebro import pases
    lineas += pases.de_entes("regulatoria", importantes)
    lineas.append("Elige en la oficina (mesa de Entes Reguladores) cuáles van a Keymonitor.")
    cerebro.telegram("\n".join(lineas), destino="gaceta", agente="regulatoria",
                     ref="regulatorias:" + ",".join(i["id"] for i in importantes[:12]))


def redactar(ids):
    """Keymonitor de lo que eligió la oficina, con el formato de los Keymonitor de Keyword."""
    marcas = ",".join("?" * len(ids))
    items = d1.consulta(f"SELECT * FROM regulatorias WHERE id IN ({marcas}) AND producto IS NULL", list(ids))
    hechos = []
    for it in items:
        texto = cerebro.texto_documento(it["documento"]) if it["documento"] else ""
        if it["url"].lower().endswith(".pdf"):
            texto = texto_pdf(it["url"]) or texto
        instr = REDACCION.replace("Recibes una edición de\nla Gaceta Oficial (PDF) y la lista de normas que la oficina eligió.",
                                  "Recibes una resolución, acuerdo o consulta pública de un regulador que la oficina eligió.")
        r = ia.generar_json(instr + cerebro.ejemplos("Keymonitor"),
                            f"id {it['id']}\nEnte: {it['ente']}\nTipo: {it['tipo']}\nTítulo: {it['titulo']}\n"
                            f"{'Plazo de comentarios: ' + it['plazo'] if it['plazo'] else ''}\n\n{texto[:12000]}", ESQUEMA_REDACCION)
        for k in r["keymonitor"][:1]:
            pid = cerebro.huella("keymonitor", it["id"])
            editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                             "fuentes", "creado", "actualizado"],
                               [[pid, "keymonitor", k["asunto"], None, k["cuerpo"], it["url"], "borrador", "regulatoria",
                                 json.dumps([it["documento"]] if it["documento"] else []), cerebro.ahora(), cerebro.ahora()]])
            d1.consulta("UPDATE regulatorias SET producto = ? WHERE id = ?", [pid, it["id"]])
            hechos.append(k["asunto"])
    if hechos:
        cerebro.telegram("📝 Keymonitor de reguladores listos para revisar en la oficina:\n" + "\n".join("• " + h for h in hechos), destino="gaceta")
    return f"{len(hechos)} Keymonitor en borrador"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "--redactar":
        print(redactar(sys.argv[2].split(",")))
    else:
        print("nuevos:", revisar())
