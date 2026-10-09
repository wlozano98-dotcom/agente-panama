"""La base (Cloudflare D1) y la matriz de seguimiento (Google Sheets).

- La base es la fuente de verdad de las fichas: al final de cada revisión se le pasa lo que cambió en el estado
  (solo las fichas cuyo contenido cambió, para cuidar las escrituras).
- La matriz es una VISTA de la base: se rehace completa en cada revisión. Lo único que el equipo escribe en ella son
  las Notas (columna M), que se recogen antes de rehacerla, y las filas de ficha que borra a mano (la ficha deja de
  estar en seguimiento y no vuelve sola). Cualquier otro cambio a mano se pierde.

En seguimiento = fichas analizadas con algún impacto (alto, medio o bajo) que el equipo no haya descartado.
"""
import datetime
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from db import d1

CARPETA = os.path.dirname(os.path.abspath(__file__))
MATRIZ_NOMBRE = "Matriz de seguimiento"
MATRIZ_HOJA = "Proyectos"
# Fila de la ficha: A-L y N-O las escribe el agente; M ("Notas") es del equipo; N es la clave (ficha), oculta.
# Debajo van subfilas agrupadas (+/-) con el historial de etapas, de la más nueva a la más vieja.
MATRIZ_COLUMNAS = [
    ("Proyecto", 380), ("Número", 120), ("Proponente", 200), ("Comisión", 220), ("Etapa", 140),
    ("Última novedad", 110), ("Qué pasó", 260), ("Presentado", 100), ("Impacto", 80), ("Sectores", 200),
    ("Clientes", 200), ("Carpeta", 80), ("Notas", 300), ("Ficha", 60), ("Resumen", 420),
]
COL_CLAVE = 13  # N
COL_NOTAS = 12  # M


def ahora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def disponible():
    return bool(os.environ.get("CLOUDFLARE_TOKEN") and os.environ.get("CLOUDFLARE_ACCOUNT_ID"))


def crear():
    """Crea la base y sus tablas (se puede repetir: todo es IF NOT EXISTS)."""
    d1.id_base(crear=True)
    d1.ejecutar_varias(open(os.path.join(CARPETA, "db", "esquema.sql"), encoding="utf-8").read())


# ---------------------------------------------------------------- estado → base


def _huella(*partes):
    return hashlib.md5(json.dumps(partes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def sincronizar(estado, ag):
    """Pasa a la base las fichas que cambiaron desde la última vez (datos, análisis e historial)."""
    huellas = estado.setdefault("huellas_base", {})
    filas, eventos, impactos, tocadas = [], [], [], []
    for ficha, f in estado["fichas"].items():
        r = f.get("analisis") or {}
        h = _huella({k: v for k, v in f.items() if k != "analisis"}, r)
        if huellas.get(ficha) == h:
            continue
        tocadas.append(ficha)
        filas.append([int(ficha), f.get("proyecto") or "", f.get("anteproyecto") or "", f["titulo"], r.get("titulo"),
                      r.get("titulo_corto"), f["fecha"], ag.nombre_proponente(f["proponente"]),
                      ag.nombre_comision(f.get("comision")), f["etapa"], 1 if f.get("tiene_documento") else 0,
                      r.get("fecha_analisis"), r.get("impacto"), ", ".join(r.get("sectores") or []) or None,
                      ", ".join(ag.clientes_afectados(r)) or None if r else None, r.get("resumen"), r.get("razon"),
                      json.dumps(r.get("disposiciones") or [], ensure_ascii=False) if r else None, r.get("drive"),
                      1 if r.get("impacto") in ("alto", "medio", "bajo") else 0, ahora()])
        for x in f.get("etapas") or []:
            eventos.append([int(ficha), x["fecha"], x["etapa"], x["comentario"], "seglegis",
                            f"seglegis:{ficha}:{x['fecha']}:{x['etapa']}:{x['comentario']}", ahora()])
        for x in r.get("impactos") or []:
            impactos.append([int(ficha), x["sector"], x["nivel"], x["razon"], r.get("fecha_analisis")])
    if not tocadas:
        print("base: sin cambios")
        return
    columnas = ["ficha", "proyecto", "anteproyecto", "titulo_oficial", "titulo", "titulo_corto", "fecha_presentacion",
                "proponente", "comision", "etapa", "tiene_pdf", "analizado", "impacto", "sectores", "clientes", "resumen",
                "razon", "disposiciones", "carpeta_url", "en_seguimiento", "actualizado"]
    # UPSERT: no toca notas ni descartada (son del equipo); una ficha descartada no vuelve a la matriz
    actualizar = ", ".join(f"{c} = excluded.{c}" for c in columnas[1:] if c != "en_seguimiento")
    for i in range(0, len(filas), 100):
        valores = ",\n".join("(" + ",".join(d1.literal(v) for v in fila) + ")" for fila in filas[i:i + 100])
        d1.ejecutar_varias(
            f"INSERT INTO proyectos ({','.join(columnas)}) VALUES\n{valores}\n"
            f"ON CONFLICT(ficha) DO UPDATE SET {actualizar}, "
            f"en_seguimiento = CASE WHEN proyectos.descartada = 1 THEN 0 ELSE excluded.en_seguimiento END")
    d1.insertar_muchas("eventos", ["ficha", "fecha", "etapa", "texto", "fuente", "id_origen", "creado"], eventos,
                       modo="INSERT OR IGNORE")
    con_impacto = sorted({str(x[0]) for x in impactos})
    for i in range(0, len(con_impacto), 90):  # el análisis nuevo reemplaza al anterior
        d1.ejecutar_varias(f"DELETE FROM impactos WHERE ficha IN ({','.join(con_impacto[i:i + 90])})")
    d1.insertar_muchas("impactos", ["ficha", "sector", "nivel", "razon", "actualizado"], impactos)
    for ficha in tocadas:
        f = estado["fichas"][ficha]
        huellas[ficha] = _huella({k: v for k, v in f.items() if k != "analisis"}, f.get("analisis") or {})
    print(f"base: {len(tocadas)} fichas actualizadas, {len(eventos)} etapas, {len(impactos)} impactos "
          f"({d1.USO['consultas']} consultas, {d1.USO['rows_written']} filas escritas)")


# ---------------------------------------------------------------- Google (Sheets y Drive)

_token = {}


def google_token():
    if _token.get("vence", 0) > time.time() + 60:
        return _token["token"]
    permiso = json.loads(os.environ["DRIVE_TOKEN"])
    datos = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": permiso["refresh_token"], "grant_type": "refresh_token",
    }).encode()
    r = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data=datos, timeout=30))
    _token.update(token=r["access_token"], vence=time.time() + r["expires_in"])
    return r["access_token"]


def google(metodo, url, cuerpo=None):
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode() if cuerpo is not None else None, method=metodo,
                                 headers={"Authorization": "Bearer " + google_token(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        texto = r.read()
    return json.loads(texto) if texto else {}


def drive_buscar(consulta):
    q = urllib.parse.quote(consulta + " and trashed = false")
    return google("GET", f"https://www.googleapis.com/drive/v3/files?q={q}&fields=files(id,name)")["files"]


def matriz_id(estado, raiz_nombre):
    """Busca la matriz en la carpeta principal de Drive; si no existe, la crea con su formato."""
    if estado.get("matriz_id"):
        return estado["matriz_id"]
    carpetas = drive_buscar(f"name = '{raiz_nombre}' and mimeType = 'application/vnd.google-apps.folder' and 'root' in parents")
    if carpetas:
        raiz = carpetas[0]["id"]
    else:
        raiz = google("POST", "https://www.googleapis.com/drive/v3/files",
                      {"name": raiz_nombre, "mimeType": "application/vnd.google-apps.folder"})["id"]
    existentes = drive_buscar(f"name = '{MATRIZ_NOMBRE}' and '{raiz}' in parents")
    if existentes:
        estado["matriz_id"] = existentes[0]["id"]
        return estado["matriz_id"]
    sid = google("POST", "https://www.googleapis.com/drive/v3/files",
                 {"name": MATRIZ_NOMBRE, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [raiz]})["id"]
    hoja_id = google("GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties")["sheets"][0]["properties"]["sheetId"]
    n = len(MATRIZ_COLUMNAS)
    pedidos = [
        {"updateSpreadsheetProperties": {"properties": {"locale": "en_US", "timeZone": "America/Panama"},
                                         "fields": "locale,timeZone"}},  # inglés solo para que las fórmulas usen coma
        {"updateSheetProperties": {"properties": {"sheetId": hoja_id, "title": MATRIZ_HOJA,
                                                  "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1,
                                                                    "rowGroupControlAfter": False}},
                                   "fields": "title,gridProperties.frozenRowCount,gridProperties.frozenColumnCount,"
                                             "gridProperties.rowGroupControlAfter"}},
        {"updateCells": {"range": {"sheetId": hoja_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                         "rows": [{"values": [{"userEnteredValue": {"stringValue": c}} for c, _ in MATRIZ_COLUMNAS]}],
                         "fields": "userEnteredValue"}},
        {"repeatCell": {"range": {"sheetId": hoja_id, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                                       "backgroundColor": {"red": 0.16, "green": 0.25, "blue": 0.42},
                                                       "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment)"}},
        {"setBasicFilter": {"filter": {"range": {"sheetId": hoja_id, "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": n}}}},
    ]
    for i, (_, ancho) in enumerate(MATRIZ_COLUMNAS):
        pedidos.append({"updateDimensionProperties": {
            "range": {"sheetId": hoja_id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": ancho, "hiddenByUser": i == COL_CLAVE}, "fields": "pixelSize,hiddenByUser"}})
    google("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate", {"requests": pedidos})
    estado["matriz_id"] = sid
    print(f"  matriz creada: https://docs.google.com/spreadsheets/d/{sid}")
    return sid


# ---------------------------------------------------------------- la matriz como vista de la base


def fichas_en_seguimiento():
    """Fichas de la matriz con su historial (el más nuevo primero)."""
    fichas = d1.consulta("SELECT * FROM proyectos WHERE en_seguimiento = 1")
    eventos = d1.consulta("SELECT e.ficha, e.fecha, e.etapa, e.texto, e.id FROM eventos e "
                          "JOIN proyectos p ON p.ficha = e.ficha WHERE p.en_seguimiento = 1 ORDER BY e.fecha DESC, e.id ASC")
    por_ficha = {}
    for e in eventos:
        por_ficha.setdefault(e["ficha"], []).append(e)
    for f in fichas:
        f["eventos"] = por_ficha.get(f["ficha"], [])
    return fichas


def _recoger_cambios_del_equipo(estado, valores, fichas):
    """Notas escritas a mano → base; filas de ficha borradas a mano → descartada (no vuelve sola)."""
    previa = estado.get("matriz_generada")
    en_hoja = {}
    for fila in valores[1:]:
        fila = [str(x) for x in fila] + [""] * 15
        if fila[COL_CLAVE] and "#" not in fila[COL_CLAVE]:
            en_hoja[fila[COL_CLAVE]] = fila[COL_NOTAS]
    por_clave = {str(f["ficha"]): f for f in fichas}
    cambios = 0
    for clave, notas in en_hoja.items():
        f = por_clave.get(clave)
        if f and previa and _huella(notas) != previa["notas"].get(clave) and notas.strip() != (f["notas"] or "").strip():
            d1.consulta("UPDATE proyectos SET notas = ?, actualizado = ? WHERE ficha = ?", [notas, ahora(), int(clave)])
            f["notas"] = notas
            cambios += 1
    borradas = [c for c in (previa or {}).get("claves", []) if c not in en_hoja and c in por_clave]
    for clave in borradas:
        d1.consulta("UPDATE proyectos SET en_seguimiento = 0, descartada = 1, actualizado = ? WHERE ficha = ?", [ahora(), int(clave)])
        fichas.remove(por_clave[clave])
        print(f"  la ficha {clave} se borró a mano de la matriz: deja de estar en seguimiento")
    return cambios, len(borradas)


def numero(f):
    if f["proyecto"] not in ("", "0", None):
        return f"Proyecto {f['proyecto']}"
    if f["anteproyecto"] not in ("", "0", None):
        return f"Anteproyecto {f['anteproyecto']}"
    return ""


def dma(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


def matriz_generar(estado, raiz_nombre):
    """Rehace la hoja 'Proyectos' desde la base: una fila por ficha (las de novedad más reciente arriba) y subfilas
    agrupadas con el historial de etapas."""
    sid = matriz_id(estado, raiz_nombre)
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}"
    try:
        valores = google("GET", f"{base}/values/{MATRIZ_HOJA}!A1:O").get("values", [])
    except urllib.error.HTTPError as ex:
        if ex.code != 404:
            raise
        estado.pop("matriz_id", None)  # la borraron: se crea de nuevo
        return matriz_generar(estado, raiz_nombre)
    fichas = fichas_en_seguimiento()
    notas, borradas = _recoger_cambios_del_equipo(estado, valores, fichas)
    sueltas = [[str(x) for x in f] + [""] * (15 - len(f)) for f in valores[1:] if f and str(f[0]).strip()
               and not (len(f) > COL_CLAVE and str(f[COL_CLAVE]).strip()) and not str(f[0]).strip().startswith("↳")]

    orden = {"alto": 0, "medio": 1, "bajo": 2}
    fichas.sort(key=lambda f: (f["eventos"][0]["fecha"] if f["eventos"] else f["fecha_presentacion"] or "",
                               -orden.get(f["impacto"], 3)), reverse=True)
    filas, sub, enlaces = [], [], []
    for f in fichas:
        ult = f["eventos"][0] if f["eventos"] else None
        filas.append([f["titulo"] or f["titulo_oficial"], numero(f), f["proponente"] or "", f["comision"] or "",
                      f["etapa"] or "", dma(ult["fecha"]) if ult else "", (ult["texto"] or "").capitalize() if ult else "",
                      dma(f["fecha_presentacion"]), (f["impacto"] or "").capitalize(), f["sectores"] or "",
                      f["clientes"] or "", "", f["notas"] or "", str(f["ficha"]), f["resumen"] or ""])
        if f["carpeta_url"]:
            enlaces.append((len(filas) + 1, f["carpeta_url"]))
        if f["eventos"]:
            inicio = len(filas) + 1
            for e in f["eventos"]:
                filas.append(["   ↳", "", "", "", e["etapa"] or "", dma(e["fecha"]), (e["texto"] or "").capitalize(),
                              "", "", "", "", "", "", f"{f['ficha']}#{e['id']}", ""])
            sub.append((inicio, len(filas) + 1))
    filas += sueltas
    total = len(filas) + 1

    hoja = google("GET", f"{base}?fields=sheets(properties(sheetId,gridProperties.rowCount),rowGroups)")["sheets"][0]
    hoja_id, filas_hoja = hoja["properties"]["sheetId"], hoja["properties"]["gridProperties"]["rowCount"]
    pedidos = []
    for _ in range(max([g.get("depth", 1) for g in hoja.get("rowGroups", [])] or [0])):
        pedidos.append({"deleteDimensionGroup": {"range": {"sheetId": hoja_id, "dimension": "ROWS", "startIndex": 1,
                                                           "endIndex": max(filas_hoja, total)}}})
    if filas_hoja < total + 20:
        pedidos.append({"appendDimension": {"sheetId": hoja_id, "dimension": "ROWS", "length": total + 20 - filas_hoja}})
    elif filas_hoja > total + 200:
        pedidos.append({"deleteDimension": {"range": {"sheetId": hoja_id, "dimension": "ROWS", "startIndex": total + 100,
                                                      "endIndex": filas_hoja}}})
    if pedidos:
        google("POST", f"{base}:batchUpdate", {"requests": pedidos})
    google("POST", f"{base}/values/{MATRIZ_HOJA}!A2:O:clear", {})
    if filas:
        google("PUT", f"{base}/values/{MATRIZ_HOJA}!A2:O{total}?valueInputOption=RAW", {"values": filas})
    if enlaces:
        google("POST", f"{base}/values:batchUpdate", {"valueInputOption": "USER_ENTERED", "data": [
            {"range": f"{MATRIZ_HOJA}!L{fila}", "values": [[f'=HYPERLINK("{url}","Abrir")']]} for fila, url in enlaces]})
    colores = {"Alto": (0.99, 0.87, 0.85), "Medio": (1, 0.93, 0.8), "Bajo": (1, 0.98, 0.84)}
    formato = [{"repeatCell": {"range": {"sheetId": hoja_id, "startRowIndex": 1},
                               "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
                                                              "wrapStrategy": "WRAP", "verticalAlignment": "TOP",
                                                              "textFormat": {"fontSize": 10}}},
                               "fields": "userEnteredFormat(backgroundColor,wrapStrategy,verticalAlignment,textFormat)"}}]
    for i, fila in enumerate(filas):
        if fila[8] in colores:
            rojo, verde, azul = colores[fila[8]]
            formato.append({"repeatCell": {"range": {"sheetId": hoja_id, "startRowIndex": i + 1, "endRowIndex": i + 2,
                                                     "startColumnIndex": 8, "endColumnIndex": 9},
                                           "cell": {"userEnteredFormat": {"backgroundColor": {"red": rojo, "green": verde, "blue": azul}}},
                                           "fields": "userEnteredFormat.backgroundColor"}})
    formato += [{"repeatCell": {"range": {"sheetId": hoja_id, "startRowIndex": a, "endRowIndex": b},
                                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.95, "green": 0.96, "blue": 0.98},
                                                               "textFormat": {"fontSize": 9}}},
                                "fields": "userEnteredFormat(backgroundColor,textFormat)"}} for a, b in sub]
    formato += [{"addDimensionGroup": {"range": {"sheetId": hoja_id, "dimension": "ROWS", "startIndex": a, "endIndex": b}}}
                for a, b in sub]
    google("POST", f"{base}:batchUpdate", {"requests": formato})
    estado["matriz_generada"] = {"fecha": ahora(), "claves": [str(f["ficha"]) for f in fichas],
                                 "notas": {str(f["ficha"]): _huella(f["notas"] or "") for f in fichas}}
    print(f"matriz: {len(fichas)} fichas, {sum(len(f['eventos']) for f in fichas)} etapas"
          f"{f', {notas} notas del equipo' if notas else ''}{f', {borradas} borradas a mano' if borradas else ''}"
          f" — https://docs.google.com/spreadsheets/d/{sid}")
