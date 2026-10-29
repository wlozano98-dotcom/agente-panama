"""Oficina de PRUEBA, solo en esta Mac (2026-10-26): la oficina de siempre con la escena publicada MÁS UNA ENTRADA
en el medio (bot/escena_entrada.js y .css: Kiwi con el logo de Keyword y el cerebro colgando del techo) y el mapa del cerebro,
SIN publicar nada. Los datos son los reales: lo que pide la página se reenvía al Worker; /oficina/grafo y
/oficina/mapa los arma la Mac desde D1 (cerebro/mapa.py). Cuando Andrés apruebe, se pasa al Worker.

Uso: python3 bot/prueba_local.py      → abrir http://127.0.0.1:8778/oficina
Solo escucha en 127.0.0.1 (esta Mac): la clave de la oficina la agrega el servidor al reenviar, no hace falta en la dirección.
"""
import base64
import http.server
import json
import os
import sys
import time
import urllib.error
import urllib.request

CARPETA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(CARPETA))
import cerebro  # noqa: E402
from cerebro import mapa  # noqa: E402

PUERTO = 8778
WORKER = "https://agente-panama.agentemonitoreopa.workers.dev"
CACHE = {}


def pagina():
    p = open(os.path.join(CARPETA, "oficina.html"), encoding="utf-8").read()
    for nombre in ("keyword-negro", "keyword-blanco"):
        datos = base64.b64encode(open(os.path.join(CARPETA, "img", nombre + ".png"), "rb").read()).decode()
        p = p.replace(f"__LOGO_{nombre.split('-')[1].upper()}__", "data:image/png;base64," + datos)
    css = open(os.path.join(CARPETA, "escena_entrada.css"), encoding="utf-8").read()
    js = open(os.path.join(CARPETA, "escena_entrada.js"), encoding="utf-8").read()
    p = p.replace("Math.min(2, base", "Math.min(3, base")  # cuatro zonas: al arrastrar se llega hasta la económica
    fin = p.rindex("})();")
    return (p[:fin] + js + "\n" + p[fin:]).replace("</style>", css + "\n</style>", 1).replace(
        "<title>", '<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet"><title>', 1)


def grafo():
    """Puntos y líneas del mapa (con el grado de cada punto), guardados 10 minutos."""
    if CACHE.get("grafo", (0, None))[0] < time.time() - 600:
        nodos, lineas = mapa.datos()
        grado = {}
        for l in lineas:
            grado[l["a"]] = grado.get(l["a"], 0) + 1
            grado[l["b"]] = grado.get(l["b"], 0) + 1
        CACHE["grafo"] = (time.time(), {"nodos": [{"id": n["id"], "tipo": n["tipo"], "grado": grado.get(n["id"], 0)} for n in nodos],
                                        "lineas": [{"a": l["a"], "b": l["b"]} for l in lineas]})
    return CACHE["grafo"][1]


class Prueba(http.server.BaseHTTPRequestHandler):
    def _responder(self, codigo, tipo, cuerpo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _reenviar(self, metodo):
        datos = self.rfile.read(int(self.headers.get("Content-Length", 0))) if metodo == "POST" else None
        ruta = self.path if "k=" in self.path else self.path + ("&" if "?" in self.path else "?") + "k=" + os.environ["OFICINA_CLAVE"]
        req = urllib.request.Request(WORKER + ruta, data=datos, method=metodo, headers={
            "Content-Type": self.headers.get("Content-Type", "application/json"), "User-Agent": "Mozilla/5.0 (oficina de prueba)"})
        try:
            r = urllib.request.urlopen(req, timeout=120)
            self._responder(r.status, r.headers.get("Content-Type", "application/json"), r.read())
        except urllib.error.HTTPError as e:
            self._responder(e.code, e.headers.get("Content-Type", "text/plain"), e.read())

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/oficina":
            return self._responder(200, "text/html; charset=utf-8", pagina().encode())
        if ruta == "/oficina/grafo":
            return self._responder(200, "application/json", json.dumps(grafo()).encode())
        if ruta == "/oficina/mapa":
            mapa.escribir()
            return self._responder(200, "text/html; charset=utf-8", open(mapa.SALIDA, "rb").read())
        self._reenviar("GET")

    def do_POST(self):
        self._reenviar("POST")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    cerebro.cargar_env()
    print(f"Oficina de prueba en http://127.0.0.1:{PUERTO}/oficina  (solo en esta Mac)", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Prueba).serve_forever()
