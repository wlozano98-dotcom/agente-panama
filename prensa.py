"""La Cronista: noticias y agenda de comisiones de la Asamblea Nacional de Panamá (www.asamblea.gob.pa).

Ese sitio tiene anti-bots F5 (TSPD): con curl no abre, con un navegador sí. Se abre una vez con Playwright (Chromium
sin ventana), se espera a que pase la verificación y desde la misma página se piden las dos APIs JSON que usa el sitio:
- Noticias: GET /Data/Noticias/Client/0/List?page=N&pageSize=30 (título, slug, fecha) y el texto de cada nota en
  /Noticias/Noticias/<slug>.
- Agenda de comisiones: POST /Data/Agenda/List/0 (DataTables; comisión, lugar, fecha y "Descripcion" con los temas).

Cada nota y cada cita se cruza con las fichas por el número que menciona ("proyecto de Ley 569", "Anteproyecto de Ley
360", "Proyectos de Ley: 692 «…» y 693 «…»"). La prensa a veces llama "proyecto" a un anteproyecto, así que con el
número se buscan los dos y se confirma con las palabras del título. También sirve un título entre comillas «…».
- Las notas que nombran fichas van a la bitácora (tabla eventos, fuente "noticia") y a la oficina.
- La agenda va a la tabla agenda (+ agenda_fichas); la oficina la muestra y la pizarra anuncia las próximas sesiones.
- Telegram (la Mensajera): nota nueva o sesión nueva sobre una ficha de impacto alto o medio.

Uso: python prensa.py [--prueba]   (--prueba: no escribe en la base, no avisa, no guarda estado)
"""
import argparse
import datetime
import json
import re
import sys

import agente as ag
import base
from db import d1

SITIO = "https://www.asamblea.gob.pa"
DIAS_NOTICIAS = 14          # la primera vez se leen las notas de las últimas dos semanas
DIAS_REVISION = 3           # después, las de los últimos días que no se hayan visto
CITAS_AGENDA = 100          # las más recientes (unas tres semanas)
AVISAR = ("alto", "medio")  # impacto de las fichas cuyas notas y sesiones se avisan por Telegram
MESES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                          "septiembre", "octubre", "noviembre", "diciembre"])}
VACIAS = {"QUE", "PARA", "SOBRE", "DESDE", "ENTRE", "LEY", "LEYES", "PROYECTO", "ESTABLECE", "MODIFICA", "DICTA", "OTRAS",
          "DISPOSICIONES", "ARTICULOS", "ARTICULO", "REPUBLICA", "PANAMA", "NACIONAL", "DONDE", "CUAL", "CUALES", "COMO",
          "ESTA", "ESTE", "SUS", "LOS", "LAS", "DEL", "POR", "CON", "UNA", "ADICIONA", "DECLARA", "CREA"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS agenda (
  id INTEGER PRIMARY KEY,           -- ID de la cita en el sitio de la Asamblea
  fecha TEXT, hora TEXT,            -- AAAA-MM-DD y HH:MM (24 h, hora de Panamá)
  comision TEXT, lugar TEXT, organizador TEXT,
  descripcion TEXT,                 -- tipo de reunión y temas, tal cual
  fichas TEXT,                      -- fichas mencionadas, separadas por coma
  actualizado TEXT
);
CREATE INDEX IF NOT EXISTS agenda_fecha ON agenda(fecha);
CREATE TABLE IF NOT EXISTS agenda_fichas (agenda_id INTEGER, ficha INTEGER, PRIMARY KEY (agenda_id, ficha));
CREATE INDEX IF NOT EXISTS agenda_fichas_ficha ON agenda_fichas(ficha);
"""

JS_NOTICIAS = "async (n) => (await fetch('/Data/Noticias/Client/0/List?page=' + n + '&pageSize=30&search=')).text()"
JS_NOTA = """async (s) => { const h = await (await fetch('/Noticias/Noticias/' + s)).text();
  const d = new DOMParser().parseFromString(h, 'text/html'); const m = d.querySelector('main') || d.body;
  m.querySelectorAll('script,style').forEach(x => x.remove()); return m.textContent; }"""
JS_AGENDA = """async (n) => {
  const cols = ['', 'Ubicacion', 'Categoria.Nombre', 'Persona', 'FechaView'];
  const p = new URLSearchParams({draw: '1', start: '0', length: String(n), 'search[value]': '', 'search[regex]': 'false',
    'order[0][column]': '4', 'order[0][dir]': 'desc'});
  cols.forEach((c, i) => { p.set(`columns[${i}][data]`, c); p.set(`columns[${i}][searchable]`, 'true');
    p.set(`columns[${i}][orderable]`, i ? 'true' : 'false'); });
  const r = await fetch('/Data/Agenda/List/0', {method: 'POST', body: p, headers: {'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}});
  return await r.text(); }"""


# ---------------------------------------------------------------- el navegador

class Sitio:
    """Abre www.asamblea.gob.pa en Chromium sin ventana y espera a que pase la verificación del anti-bots."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._nav = self._pw.chromium.launch()
        self.pagina = self._nav.new_page()
        self.pagina.goto(SITIO + "/Page/Noticias", timeout=120000)
        for _ in range(40):  # la verificación recarga la página una o dos veces
            self.pagina.wait_for_timeout(1500)
            if self.pagina.title():
                return self
        raise RuntimeError("el sitio de la Asamblea no pasó la verificación del anti-bots")

    def __exit__(self, *_):
        self._nav.close()
        self._pw.stop()

    def json(self, js, arg):
        return json.loads(self.pagina.evaluate(js, arg))

    def texto(self, js, arg):
        return self.pagina.evaluate(js, arg)


# ---------------------------------------------------------------- cruce con las fichas

def palabras(texto):
    return {w for w in re.findall(r"[A-Z]{4,}", ag.normalizar(texto)) if w not in VACIAS}


class Indice:
    def __init__(self, fichas):
        self.fichas = fichas
        self.por = {"proyecto": {}, "anteproyecto": {}}
        for f in fichas.values():
            for tipo in self.por:
                n = str(f.get(tipo) or "").strip()
                if n not in ("", "0"):
                    self.por[tipo].setdefault(int(n), []).append(f)
        self.titulos = [(ag.normalizar(f["titulo"])[:60], f) for f in fichas.values() if len(f.get("titulo") or "") > 30]

    def buscar(self, texto):
        """Fichas que menciona un texto: por número (confirmado con el título) o por título entre comillas."""
        encontradas, contexto = {}, palabras(texto)
        for m in re.finditer(r"\b(ante)?proyectos?\s+de\s+ley\b", texto, re.I):
            tipo = "anteproyecto" if m.group(1) else "proyecto"
            for n, cerca in numeros(texto[m.end():]):
                # se confirma con el título que acompaña al número (lo que sigue, hasta el próximo número)
                f = self.elegir(n, tipo, palabras(cerca) or contexto)
                if f:
                    encontradas[f["ficha"]] = f
        for q in re.findall(r"[«“\"]([^»”\"]{25,400})[»”\"]", texto):
            nq = ag.normalizar(q)[:60]
            for t, f in self.titulos:
                if len(nq) >= 30 and (t.startswith(nq[:50]) or nq.startswith(t[:50])):
                    encontradas[f["ficha"]] = f
        return list(encontradas.values())

    def elegir(self, n, tipo, contexto):
        otro = "anteproyecto" if tipo == "proyecto" else "proyecto"
        mejor, puntos = None, 0.0
        for t, bono in ((tipo, 0.15), (otro, 0.0)):
            for f in self.por[t].get(n, []):
                pt = palabras(f["titulo"])
                p = (len(pt & contexto) / len(pt) if pt else 0) + bono
                if p > puntos or (p == puntos and mejor and f.get("fecha", "") > mejor.get("fecha", "")):
                    mejor, puntos = f, p
        return mejor if puntos >= 0.35 else None


def numeros(resto):
    """[(número, texto que lo acompaña)]: '569 que crea…' → 569; ': 692 «…» y 693 «…»' → 692 y 693; 'N° 12, 13 y 14'."""
    out, i = [], 0
    m = re.match(r"\s*(?:n\.?\s*[°º]|no\.|núm(?:ero)?\.?)?\s*:?\s*", resto, re.I)
    i = m.end()
    while True:
        m = re.match(r"(\d{1,4})\b", resto[i:])
        if not m:
            return out
        i += m.end()
        q = re.match(r"\s*[«“\"][^»”\"]{0,500}[»”\"]", resto[i:])
        cerca = q.group(0) if q else re.split(r"\b\d{1,4}\b", resto[i:i + 250])[0]
        out.append((int(m.group(1)), cerca))
        if q:
            i += q.end()
        s = re.match(r"\s*(?:,|y|e)\s*(?:(?:el|al|del)\s+)?(?:(?:ante)?proyecto\s+de\s+ley\s*)?", resto[i:], re.I)
        if not s or not re.match(r"\d", resto[i + s.end():]):
            return out
        i += s.end()


# ---------------------------------------------------------------- noticias

def limpiar_nota(crudo, titulo):
    """Del texto de la página queda solo el cuerpo de la nota (entre la firma "Por …" y la galería)."""
    t = re.sub(r"[ \t]+", " ", crudo)
    t = re.split(r"\n\s*(?:Galer[ií]a fotogr[aá]fica|COMPARTIR)\s*\n", t, flags=re.I)[0]
    lineas = [x.strip() for x in t.split("\n") if x.strip()]
    for k, x in enumerate(lineas):
        if re.match(r"^Por\s", x):
            lineas = lineas[k + 1:]
            break
    else:
        lineas = [x for x in lineas if ag.normalizar(x) != ag.normalizar(titulo) and not re.match(r"^(Noticias|Volver|[\d/: APM]+)$", x)]
    cuerpo = " ".join(lineas)
    return re.sub(r"([a-záéíóúñ0-9\)])\.([A-ZÁÉÍÓÚÑ])", r"\1. \2", cuerpo)  # "debate.Según" → "debate. Según"


def resumen(cuerpo, largo=320):
    if len(cuerpo) <= largo:
        return cuerpo
    corte = cuerpo[:largo]
    fin = max(corte.rfind(". "), corte.rfind("; "))
    return (corte[:fin + 1] if fin > 120 else corte.rsplit(" ", 1)[0] + "…").strip()


def oracion(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t[:1] + t[1:].lower() if t.isupper() else t


def leer_noticias(sitio, vistas, desde):
    """Notas publicadas desde `desde` que no se hayan visto: [{id, fecha, titulo, url, cuerpo}]."""
    nuevas = []
    for pagina in range(1, 15):
        lote = sitio.json(JS_NOTICIAS, pagina).get("data") or []
        for x in lote:
            fecha = (x.get("FechaEdit") or "")[:10]
            if fecha < desde or str(x["ID"]) in vistas:
                continue
            nuevas.append({"id": str(x["ID"]), "fecha": fecha, "titulo": oracion(x.get("Titulo")), "slug": x.get("Slug") or "",
                           "url": f"{SITIO}/Noticias/Noticias/{x.get('Slug') or ''}"})
        if not lote or (lote[-1].get("FechaEdit") or "")[:10] < desde:
            break
    for n in nuevas:
        try:
            n["cuerpo"] = limpiar_nota(sitio.texto(JS_NOTA, n["slug"]), n["titulo"])
        except Exception as ex:
            print(f"  nota {n['id']}: {ex}")
            n["cuerpo"] = ""
    return nuevas


# ---------------------------------------------------------------- agenda

def fecha_hora(vista):
    """'09 octubre, 2026 1:00 p. m.' → ('2026-10-09', '13:00')."""
    m = re.match(r"(\d{1,2})\s+(\w+),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*([ap])", vista or "", re.I)
    if not m:
        return None, None
    d, mes, a, h, mi, ap = m.groups()
    h = int(h) % 12 + (12 if ap.lower() == "p" else 0)
    return f"{a}-{MESES.get(mes.lower(), 1):02d}-{int(d):02d}", f"{h:02d}:{mi}"


def leer_agenda(sitio):
    citas = []
    for x in sitio.json(JS_AGENDA, CITAS_AGENDA).get("data") or []:
        fecha, hora = fecha_hora(x.get("FechaView"))
        if not fecha:
            continue
        persona = (x.get("Persona") or "").strip(" .")
        citas.append({"id": int(x["ID"]), "fecha": fecha, "hora": hora,
                      "comision": ag.nombre_comision("COMISION DE " + ((x.get("Categoria") or {}).get("Nombre") or "")).strip(),
                      "lugar": re.sub(r"\s+", " ", x.get("Ubicacion") or "").strip(),
                      "organizador": ag.titulo(persona) if persona else "",
                      "descripcion": re.sub(r"[ \t]+", " ", x.get("Descripcion") or "").strip()})
    return citas


# ---------------------------------------------------------------- avisos

def impacto(f):
    return (f.get("analisis") or {}).get("impacto")


def nombre(f):
    return (f.get("analisis") or {}).get("titulo") or ag.titulo(f["titulo"])


def aviso_nota(n, fichas):
    lineas = [f"📰 <b>Noticia de la Asamblea</b> · {ag.ddmm(n['fecha'])}", f"<b>{ag.e(n['titulo'])}</b>", ag.e(resumen(n['cuerpo'], 400)), ""]
    for f in fichas:
        lineas.append(f"{ag.ICONOS.get(impacto(f), '⚪')} {ag.numero(f)}: {ag.e(nombre(f))} ({ag.e(f['etapa'])})")
    lineas.append(f'<a href="{n["url"]}">Leer la nota</a>')
    return "\n".join(lineas)


def aviso_cita(c, fichas):
    lineas = [f"📅 <b>Agenda de comisión</b> · {ag.ddmm(c['fecha'])} {c['hora']}", f"<b>{ag.e(c['comision'])}</b>",
              ag.e(resumen(c["descripcion"], 400)), ag.e(c["lugar"]), ""]
    for f in fichas:
        lineas.append(f"{ag.ICONOS.get(impacto(f), '⚪')} {ag.numero(f)}: {ag.e(nombre(f))} ({ag.e(f['etapa'])})")
    return "\n".join(lineas)


# ---------------------------------------------------------------- principal

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prueba", action="store_true", help="no escribe en la base, no avisa, no guarda estado")
    args = parser.parse_args()
    ag.cargar_env()
    estado = ag.cargar_estado()
    if not estado["fichas"]:
        sys.exit("No hay fichas en el estado: corre primero agente.py.")
    prensa = estado.setdefault("prensa", {})
    primera = "noticias" not in prensa
    vistas = set(prensa.get("noticias", []))
    citas_vistas = set(map(str, prensa.get("agenda", [])))
    indice = Indice(estado["fichas"])
    hoy = ag.hoy()
    desde = (datetime.date.today() - datetime.timedelta(days=DIAS_NOTICIAS if primera else DIAS_REVISION)).isoformat()

    with Sitio() as sitio:
        notas = leer_noticias(sitio, vistas, desde)
        citas = leer_agenda(sitio)
    print(f"Prensa: {len(notas)} notas nuevas desde {desde}, {len(citas)} citas de agenda")

    eventos, avisos = [], []
    for n in notas:
        fichas = indice.buscar(n["titulo"] + "\n" + n["cuerpo"])
        print(f"  nota {n['fecha']} {n['titulo'][:70]} → {[ag.numero(f) for f in fichas]}")
        for f in fichas:
            eventos.append([int(f["ficha"]), n["fecha"], "Noticia", f"{n['titulo']}. {resumen(n['cuerpo'])}", "noticia",
                            f"noticia:{n['id']}:{f['ficha']}", base.ahora(), n["url"]])
        de_impacto = [f for f in fichas if impacto(f) in AVISAR]
        if de_impacto and not primera:
            avisos.append(aviso_nota(n, de_impacto))
    filas, relaciones = [], []
    for c in citas:
        fichas = indice.buscar(c["descripcion"])
        c["fichas"] = [f["ficha"] for f in fichas]
        filas.append([c["id"], c["fecha"], c["hora"], c["comision"], c["lugar"], c["organizador"], c["descripcion"],
                      ",".join(c["fichas"]), base.ahora()])
        relaciones += [[c["id"], int(x)] for x in c["fichas"]]
        de_impacto = [f for f in fichas if impacto(f) in AVISAR]
        if de_impacto and not primera and str(c["id"]) not in citas_vistas and c["fecha"] >= hoy:
            avisos.append(aviso_cita(c, de_impacto))
    con_fichas = sum(1 for c in citas if c["fichas"])
    print(f"  agenda: {con_fichas} de {len(citas)} citas tratan fichas conocidas; {len(eventos)} notas a la bitácora; {len(avisos)} avisos")

    if args.prueba:
        for c in citas[:12]:
            print(f"  cita {c['fecha']} {c['hora']} {c['comision']}: {[ag.numero(estado['fichas'][x]) for x in c['fichas']]}")
        for a in avisos[:3]:
            print("---\n" + a)
        return
    if base.disponible():
        d1.ejecutar_varias(ESQUEMA)
        try:
            d1.ejecutar_varias("ALTER TABLE eventos ADD COLUMN url TEXT")
        except Exception:
            pass  # ya existe
        d1.insertar_muchas("eventos", ["ficha", "fecha", "etapa", "texto", "fuente", "id_origen", "creado", "url"], eventos,
                           modo="INSERT OR IGNORE")
        d1.insertar_muchas("agenda", ["id", "fecha", "hora", "comision", "lugar", "organizador", "descripcion", "fichas",
                                      "actualizado"], filas)
        ids = ",".join(str(c["id"]) for c in citas)
        if ids:
            d1.ejecutar_varias(f"DELETE FROM agenda_fichas WHERE agenda_id IN ({ids})")
        d1.insertar_muchas("agenda_fichas", ["agenda_id", "ficha"], relaciones, modo="INSERT OR IGNORE")
    for a in avisos:
        try:
            ag.telegram("sendMessage", {"text": a, "parse_mode": "HTML", "disable_web_page_preview": True})
        except Exception as ex:
            print(f"  aviso: {ex}")
    prensa["noticias"] = sorted(vistas | {n["id"] for n in notas}, key=int)[-400:]
    prensa["agenda"] = sorted(citas_vistas | {str(c["id"]) for c in citas}, key=int)[-600:]
    prensa["revisada"] = base.ahora()
    ag.guardar_estado(estado)


if __name__ == "__main__":
    main()
