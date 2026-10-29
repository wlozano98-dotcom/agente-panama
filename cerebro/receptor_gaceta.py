"""Receptor local de la Gaceta Oficial: recibe en la Mac los PDF que el Chrome de la oficina baja de gacetaoficial.gob.pa.

Uso: python3 cerebro/receptor_gaceta.py   (escucha en http://127.0.0.1:8765, solo esta máquina)

También recibe de la extensión del Chrome de la oficina (extension/) los edictos del Pleno y los comunicados de la
Corte (fuentes "oj_edicto" y "oj_comunicado"; los analiza cerebro/judicial.py).
La web de la Gaceta pide un captcha que marca una persona; después, Claude en Chrome abre la portada y, desde la
misma pestaña, envía aquí cada edición nueva (ver VIGIA_JS). Cada PDF se guarda en salidas/gaceta/, se extrae su
texto (pypdf) y entra al cerebro como documento (fuente "gaceta", id = número de edición con su letra).
"""
import http.server
import io
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

PUERTO = 8765
CARPETA = os.path.join(cerebro.CARPETA, "salidas", "gaceta")
ORIGEN = "https://www.gacetaoficial.gob.pa"
# también recibe lo de la Corte que trae la extensión del Chrome de la oficina (extension/), y desde su web
ORIGENES = (ORIGEN, "https://www.organojudicial.gob.pa", "chrome-extension://")
ULTIMA_ALERTA = {}

# Lo que corre Claude en la pestaña de la Gaceta (javascript_tool): pregunta qué ediciones ya están y envía las nuevas.
VIGIA_JS = """
const ultimas = [...document.querySelectorAll('a')].filter(a => /^\\d{5}( [A-Z])?$/.test(a.innerText.trim())).map(a => a.href);
const ya = await (await fetch('http://127.0.0.1:8765/tengo')).json();
const enviadas = [];
for (const url of ultimas) {
  const numero = (/gacetas\\/\\d{4}\\/\\d{2}\\/(\\d{5}(?:_[A-Z])?)\\//.exec(url) || [])[1];
  if (!numero || ya.includes(numero)) continue;
  const pdf = await (await fetch(url)).arrayBuffer();
  const r = await fetch('http://127.0.0.1:8765/gaceta?numero=' + numero + '&url=' + encodeURIComponent(url),
                        {method: 'POST', body: pdf});
  enviadas.push(numero + ': ' + (await r.text()));
}
({ultimas: ultimas.length, enviadas})
"""

MESES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
                                        "diciembre".split())}


def texto_pdf(datos):
    import pypdf
    lector = pypdf.PdfReader(io.BytesIO(datos))
    return "\n".join(p.extract_text() or "" for p in lector.pages), len(lector.pages)


def fecha_de(texto, url):
    m = re.search(r"_(\d{4})(\d{2})(\d{2})\.pdf", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", texto)
    return f"{m.group(3)}-{MESES.get(m.group(2).lower(), 1):02d}-{int(m.group(1)):02d}" if m else None


def tengo():
    filas = d1.consulta("SELECT titulo FROM documentos WHERE fuente = 'gaceta' ORDER BY creado DESC LIMIT 200")
    return [re.sub(r"^Gaceta Oficial (\d{5})(?:-([A-Z]))?.*", lambda m: m.group(1) + ("_" + m.group(2) if m.group(2) else ""),
                   f["titulo"]) for f in filas]


def guardar(numero, url, datos):
    os.makedirs(CARPETA, exist_ok=True)
    open(os.path.join(CARPETA, f"{numero}.pdf"), "wb").write(datos)
    texto, paginas = texto_pdf(datos)
    etiqueta = numero.replace("_", "-")
    doc, nuevo = cerebro.guardar_documento("gaceta", numero, texto, tipo="gaceta", url=url, fecha=fecha_de(texto, url),
                                           titulo=f"Gaceta Oficial {etiqueta}")
    if nuevo:
        cerebro.enlazar()
    return f"{'nueva' if nuevo else 'ya estaba'}, {paginas} páginas, {len(texto)} caracteres"


def judicial(ruta, q, datos):
    """Lo que la extensión del Chrome de la oficina trae de la web de la Corte (cerebro/judicial.py lo analiza)."""
    url, titulo = (q.get("url") or [""])[0], (q.get("titulo") or [""])[0]
    if ruta == "/judicial/alerta":  # la web pidió verificación: que una persona la pase en ese Chrome
        import time
        que = (q.get("que") or ["corte"])[0]
        if time.time() - ULTIMA_ALERTA.get(que, 0) > 3 * 3600:
            ULTIMA_ALERTA[que] = time.time()
            if que == "x":
                cerebro.telegram("⚠️ X cerró la sesión de la cuenta de la oficina. Entra a x.com en el Chrome de la "
                                 "oficina; Paula y Diego siguen solos después.", destino="general")
            elif que == "gaceta":
                cerebro.telegram("⚠️ La Gaceta pide «Soy humano». Abre gacetaoficial.gob.pa en el Chrome de la oficina y "
                                 "marca la casilla; Inés sigue sola después.", destino="gaceta")
            else:
                cerebro.telegram("⚠️ La web de la Corte pide verificación. Abre organojudicial.gob.pa en el Chrome de la "
                                 "oficina y pásala; Elena sigue sola después.", destino="general")
        return f"alerta de {que}"
    if not url.startswith("https://www.organojudicial.gob.pa/"):
        raise ValueError("solo se reciben documentos de organojudicial.gob.pa")
    if ruta == "/judicial/edicto":
        if not datos.startswith(b"%PDF"):
            raise ValueError("no es un PDF")
        os.makedirs(os.path.join(cerebro.CARPETA, "salidas", "judicial"), exist_ok=True)
        open(os.path.join(cerebro.CARPETA, "salidas", "judicial", url.rsplit("/", 1)[-1]), "wb").write(datos)
        texto, paginas = texto_pdf(datos)
        _, nuevo = cerebro.guardar_documento("oj_edicto", url, texto, tipo="edicto", titulo=titulo or url.rsplit("/", 1)[-1],
                                             url=url, fecha=fecha_de(titulo.lower(), ""))
        return f"edicto {'nuevo' if nuevo else 'ya estaba'}: {paginas} páginas, {len(texto)} caracteres"
    if ruta == "/judicial/comunicado":
        pagina = datos.decode("utf-8", "ignore")
        cuerpo = re.search(r"(?is)<article.*?</article>", pagina) or re.search(r"(?is)<main.*?</main>", pagina)
        texto = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style).*?</\1>|<[^>]+>", " ", cuerpo.group(0) if cuerpo else pagina))
        import html as html_mod
        texto = html_mod.unescape(texto).strip()[:20000]
        fecha = re.search(r"Publicado:\s*(\d{4}-\d{2}-\d{2})", texto)
        _, nuevo = cerebro.guardar_documento("oj_comunicado", url, texto, tipo="comunicado", titulo=titulo, url=url,
                                             fecha=fecha.group(1) if fecha else None)
        return f"comunicado {'nuevo' if nuevo else 'ya estaba'}: {len(texto)} caracteres"
    raise ValueError("ruta desconocida")


def boletines(lista):
    """Los boletines de prensa de la Asamblea que trae la extensión: cada uno nuevo va al chat de la Asamblea, de a uno
    y con pausas (Andrés, 2026-10-26). La primera vez solo se anotan; lo de más de 3 días no se manda."""
    ruta = os.path.join(cerebro.CARPETA, "salidas", "redes", "boletines_vistos.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    primera = not os.path.exists(ruta)
    vistos = set() if primera else set(json.load(open(ruta)))
    desde = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
    nuevos = [b for b in lista if b.get("id") and b["id"] not in vistos and (b.get("fecha") or "") >= desde]
    json.dump(sorted(vistos | {b["id"] for b in lista if b.get("id")}, key=lambda x: int(x) if x.isdigit() else 0)[-600:], open(ruta, "w"))
    if primera:
        return f"{len(lista)} anotados (primera vez)"
    for b in sorted(nuevos, key=lambda b: b["id"]):
        titulo = b["titulo"].strip()
        if titulo.isupper():
            titulo = titulo.capitalize()
        cerebro.telegram_pausado(f"📰 {titulo}\n{b['url']}", vista_previa=True, destino="asamblea")
    return f"{len(nuevos)} nuevos"


class Receptor(http.server.BaseHTTPRequestHandler):
    def _cabeceras(self, codigo=200, tipo="application/json"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        origen = self.headers.get("Origin") or ""
        self.send_header("Access-Control-Allow-Origin", origen if origen.startswith(ORIGENES) else ORIGEN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")  # https público → localhost
        self.end_headers()

    def do_OPTIONS(self):
        self._cabeceras(204)

    def do_GET(self):
        if self.path.startswith("/judicial/vistos"):
            self._cabeceras()
            filas = d1.consulta("SELECT url FROM documentos WHERE fuente IN ('oj_edicto', 'oj_comunicado')")
            self.wfile.write(json.dumps([f["url"] for f in filas]).encode())
        elif self.path.startswith("/tengo"):
            self._cabeceras()
            self.wfile.write(json.dumps(tengo()).encode())
        else:
            self._cabeceras(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/extension/latido":  # cada revisión de la extensión del Chrome de la oficina deja su resultado
            linea = f"{time.strftime('%Y-%m-%d %H:%M')} {'(a mano) ' if (q.get('a_mano') or ['0'])[0] == '1' else ''}"
            if q.get("redes"):
                linea += f"Redes: {q['redes'][0]}"
            else:
                linea += (f"Gaceta: {(q.get('gaceta') or ['?'])[0]} · Corte: {(q.get('corte') or ['?'])[0]}"
                          f" · Boletines: {(q.get('boletines') or ['?'])[0]}")
            print(f"extensión: {linea}", flush=True)
            with open(os.path.join(cerebro.CARPETA, "salidas", "logs", "extension.log"), "a") as f:
                f.write(linea + "\n")
            self._cabeceras(200, "text/plain; charset=utf-8")
            self.wfile.write(b"ok")
            return
        if u.path == "/asamblea/boletines":  # boletines de prensa de la Asamblea → chat de la Asamblea
            try:
                resultado, codigo = boletines(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"[]")), 200
            except Exception as e:
                resultado, codigo = f"error: {e}", 500
            self._cabeceras(codigo, "text/plain; charset=utf-8")
            self.wfile.write(resultado.encode())
            return
        if u.path == "/redes/posts":  # publicaciones de las listas de X (cerebro/redes.py)
            from cerebro import redes
            try:
                posts = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"[]")
                resultado, codigo = redes.recibir((q.get("lista") or ["?"])[0], posts), 200
            except Exception as e:
                resultado, codigo = f"error: {e}", 500
            self._cabeceras(codigo, "text/plain; charset=utf-8")
            self.wfile.write(resultado.encode())
            return
        if u.path.startswith("/judicial/"):
            datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                resultado, codigo = judicial(u.path, q, datos), 200
            except Exception as e:
                resultado, codigo = f"error: {e}", 500
            print(f"{u.path}: {resultado}", flush=True)
            self._cabeceras(codigo, "text/plain; charset=utf-8")
            self.wfile.write(resultado.encode())
            return
        numero = (q.get("numero") or [""])[0]
        if u.path != "/gaceta" or not re.match(r"^\d{5}(_[A-Z])?$", numero):
            self._cabeceras(400)
            return
        datos = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            if not datos.startswith(b"%PDF"):
                raise ValueError("no es un PDF (¿volvió a pedir el captcha?)")
            resultado = guardar(numero, (q.get("url") or [""])[0], datos)
            codigo = 200
        except Exception as e:  # el error vuelve a la pestaña para que Claude lo informe
            resultado, codigo = f"error: {e}", 500
        print(f"{numero}: {resultado}", flush=True)
        self._cabeceras(codigo, "text/plain; charset=utf-8")
        self.wfile.write(resultado.encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    cerebro.cargar_env()
    print(f"Receptor de la Gaceta en http://127.0.0.1:{PUERTO}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Receptor).serve_forever()
