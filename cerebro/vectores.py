"""Búsqueda por SIGNIFICADO (2026-10-26): cada trozo del cerebro (tabla `fragmentos`) se convierte en un embedding
(gemini-embedding-001, 768 dimensiones: una lista de números que representa su sentido) y se guarda en Cloudflare
Vectorize (índice `cerebro-panama`, cuenta agentemonitoreopa). Kiwi (worker.js, contextoCerebro) busca a la vez por
palabras (FTS5) y por significado (Vectorize) y junta lo mejor de las dos: las palabras encuentran lo exacto ("Ley
644"), el significado encuentra el tema aunque se diga distinto ("subsidio al transporte" → MiBus).

El id de cada vector es el rowid del fragmento; config "vectores_hasta" guarda hasta qué rowid ya se pasó, así cada
corrida solo manda lo nuevo. La mesa lo corre cada 10 minutos.

Uso: python3 cerebro/vectores.py               (pasa lo nuevo)
     python3 cerebro/vectores.py --crear       (crea el índice; una sola vez)
     python3 cerebro/vectores.py --buscar <texto>
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

INDICE = "cerebro-panama"
DIMENSIONES = 768
MODELO = "gemini-embedding-001"
LOTE = 50  # trozos por pedido a Gemini


def _cf(metodo, ruta, datos=None, tipo="application/json"):
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/vectorize/v2/indexes{ruta}"
    cuerpo = datos if isinstance(datos, bytes) or datos is None else json.dumps(datos).encode()
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={
        "Authorization": "Bearer " + os.environ["CLOUDFLARE_TOKEN"], "Content-Type": tipo})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))["result"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Vectorize {metodo} {ruta}: {e.code} {e.read().decode()[:400]}")


def crear():
    return _cf("POST", "", {"name": INDICE, "description": "Cerebro de Keyword Panamá: fragmentos con embeddings de Gemini",
                            "config": {"dimensions": DIMENSIONES, "metric": "cosine"}})


def embeddings(textos, tarea="RETRIEVAL_DOCUMENT"):
    """Embeddings de Gemini, en el mismo orden. Si la cuota se agota, espera y reintenta."""
    cuerpo = json.dumps({"requests": [{"model": f"models/{MODELO}", "content": {"parts": [{"text": t[:8000]}]},
                                       "taskType": tarea, "outputDimensionality": DIMENSIONES} for t in textos]}).encode()
    for intento in range(5):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:batchEmbedContents",
            data=cuerpo, headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_KEY"]})
        try:
            return [e["values"] for e in json.load(urllib.request.urlopen(req, timeout=120))["embeddings"]]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and intento < 4:
                time.sleep(20 * (intento + 1))
                continue
            raise RuntimeError(f"Gemini embeddings: {e.code} {e.read().decode()[:300]}")


def hasta():
    f = d1.consulta("SELECT valor FROM config WHERE clave = 'vectores_hasta'")
    return int(f[0]["valor"]) if f else 0


def pasar(maximo=2000):
    """Manda a Vectorize los fragmentos nuevos (rowid mayor que el último pasado)."""
    d1.consulta("CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT, actualizado TEXT)")
    desde, total = hasta(), 0
    while total < maximo:
        filas = d1.consulta("SELECT f.rowid AS id, f.documento, f.n, f.texto, d.fuente, d.fecha FROM fragmentos f "
                            "JOIN documentos d ON d.id = f.documento WHERE f.rowid > ? ORDER BY f.rowid LIMIT ?", [desde, LOTE])
        if not filas:
            break
        vectores = embeddings([f["texto"] or "" for f in filas])
        lineas = [json.dumps({"id": str(f["id"]), "values": v,
                              "metadata": {"documento": f["documento"], "fuente": f["fuente"] or "", "fecha": f["fecha"] or ""}})
                  for f, v in zip(filas, vectores)]
        _cf("POST", f"/{INDICE}/upsert", "\n".join(lineas).encode(), tipo="application/x-ndjson")
        desde = filas[-1]["id"]
        d1.consulta("INSERT OR REPLACE INTO config (clave, valor, actualizado) VALUES ('vectores_hasta', ?, ?)",
                    [str(desde), cerebro.ahora()])
        total += len(filas)
    return f"{total} trozos nuevos en Vectorize (hasta el {desde})"


def buscar(texto, n=8):
    v = embeddings([texto], tarea="RETRIEVAL_QUERY")[0]
    r = _cf("POST", f"/{INDICE}/query", {"vector": v, "topK": n, "returnMetadata": "all"})
    out = []
    for m in r.get("matches", []):
        f = d1.consulta("SELECT d.titulo, substr(f.texto, 1, 200) AS trozo FROM fragmentos f JOIN documentos d "
                        "ON d.id = f.documento WHERE f.rowid = ?", [int(m["id"])])
        if f:
            out.append((round(m["score"], 3), f[0]["titulo"], f[0]["trozo"].replace("\n", " ")))
    return out


if __name__ == "__main__":
    cerebro.cargar_env()
    if "--crear" in sys.argv:
        print(crear())
    elif "--buscar" in sys.argv:
        for x in buscar(" ".join(sys.argv[sys.argv.index("--buscar") + 1:])):
            print(x)
    else:
        print(pasar())
