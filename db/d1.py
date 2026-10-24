"""Acceso a la base de datos D1 de Cloudflare (API HTTP). Usa CLOUDFLARE_TOKEN y CLOUDFLARE_ACCOUNT_ID de .env."""
import json
import os
import urllib.error
import urllib.request

NOMBRE_BASE = "agente-panama"
_ID = {"valor": os.environ.get("D1_ID")}
USO = {"rows_read": 0, "rows_written": 0, "consultas": 0}  # suma de lo que cobra D1 en esta corrida


def _api(metodo, ruta, datos=None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/d1{ruta}"
    req = urllib.request.Request(url, data=json.dumps(datos).encode() if datos is not None else None, method=metodo,
                                 headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_TOKEN"],
                                          "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"D1 {metodo} {ruta}: {e.code} {e.read().decode()[:600]}")
    if not r.get("success"):
        raise RuntimeError(f"D1 {metodo} {ruta}: {r.get('errors')}")
    if ruta.endswith("/query"):
        for x in r["result"] or []:
            USO["consultas"] += 1
            for k in ("rows_read", "rows_written"):
                USO[k] += (x.get("meta") or {}).get(k, 0)
    return r["result"]


def id_base(crear=False):
    """Id de la base (la crea si se pide y no existe)."""
    if _ID["valor"]:
        return _ID["valor"]
    for b in _api("GET", f"/database?name={NOMBRE_BASE}"):
        if b["name"] == NOMBRE_BASE:
            _ID["valor"] = b["uuid"]
            return b["uuid"]
    if not crear:
        raise RuntimeError(f"no existe la base {NOMBRE_BASE}")
    _ID["valor"] = _api("POST", "/database", {"name": NOMBRE_BASE})["uuid"]
    return _ID["valor"]


def consulta(sql, params=None):
    """Ejecuta una sentencia y devuelve sus filas (lista de dicts). Máximo 100 parámetros por sentencia."""
    r = _api("POST", f"/database/{id_base()}/query", {"sql": sql, "params": params or []})
    return r[0]["results"] if r else []


def ejecutar_varias(sql):
    """Ejecuta varias sentencias separadas por ';' (sin parámetros)."""
    return _api("POST", f"/database/{id_base()}/query", {"sql": sql})


def literal(v):
    """Valor como literal SQL (para cargas grandes sin parámetros)."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def lotes(filas, por_lote=200, maximo=90_000):
    """Agrupa filas como listas de VALUES, sin pasar por_lote filas ni ~maximo bytes (D1 corta a los 100 KB)."""
    lote, tam = [], 0
    for f in filas:
        tupla = "(" + ",".join(literal(v) for v in f) + ")"
        if lote and (len(lote) >= por_lote or tam + len(tupla.encode()) > maximo):
            yield ",\n".join(lote)
            lote, tam = [], 0
        lote.append(tupla)
        tam += len(tupla.encode()) + 2
    if lote:
        yield ",\n".join(lote)


def insertar_muchas(tabla, columnas, filas, por_lote=200, modo="INSERT OR REPLACE"):
    """Inserta muchas filas en lotes, con literales escapados."""
    for valores in lotes(filas, por_lote):
        ejecutar_varias(f"{modo} INTO {tabla} ({','.join(columnas)}) VALUES\n{valores}")
