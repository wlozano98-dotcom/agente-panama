"""Agenda parlamentaria publicada en X (@asambleapa): la Asamblea publica cada mañana la agenda del día en IMÁGENES,
y trae más que la Agenda de Comisiones de su web (27/10/2026: la web tenía 4 sesiones; X, 7 y el Pleno; Comercio con
2 de 4 puntos). La extensión manda las publicaciones de las listas con los enlaces de sus fotos; el receptor deja en
una cola las de @asambleapa con fotos; aquí Gemini lee las imágenes y lo que la web no trae se suma a la tabla agenda:
- sesión que la web no tiene → fila propia (id = X_BASE + huella; organizador "Agenda publicada en X (@asambleapa)").
  Si después la web la publica, se borra la de X. El Pleno de X se borra cuando entra su Orden del Día.
- puntos que faltan en una sesión de la web → se agregan al final de su descripción. prensa.py (GitHub, cada hora)
  reescribe esas filas, así que aplicar() los vuelve a poner cada 5 minutos (tabla agenda_x guarda lo leído).

Uso: python3 cerebro/agenda_x.py                    (procesa la cola y aplica)
     python3 cerebro/agenda_x.py <url foto> [...]   (lee esas imágenes a mano, p. ej. una agenda que ya pasó)
"""
import base64
import datetime
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

COLA = os.path.join(cerebro.CARPETA, "salidas", "redes", "agenda_x.jsonl")
X_BASE = 2_000_000_000   # ids de las sesiones que solo están en X (la web usa ids chicos; el Pleno, 10.000.000 + id)
PLENO_BASE = 10_000_000
MARCA = "Agregado de la agenda publicada en X (@asambleapa):"
ORGANIZADOR = "Agenda publicada en X (@asambleapa)"
PISTA = re.compile(r"agenda", re.I)

LEER = """Lees las imágenes de la "Agenda Parlamentaria" que publica la Asamblea Nacional de Panamá en X. Si las imágenes
no son una agenda de sesiones (fotos de un acto, afiches, etc.), devuelve es_agenda=false y sesiones vacías.
Si lo son, copia TODAS las sesiones, tal cual, sin resumir ni inventar:
- fecha: la fecha de la agenda (AAAA-MM-DD); si la imagen no la dice, la de la publicación.
- hora: 24 h, "HH:MM".
- comision: el nombre de la comisión SIN "Comisión de" ni "Subcomisión de" (p. ej. "Trabajo, Salud y Desarrollo
  Social", "Asuntos Municipales", "Investigación"); para el Pleno, "Pleno".
- subcomision: true si dice "Subcomisión".
- lugar y preside (el nombre que sigue a "Presidida por", sin "H.D.").
- tipo_reunion: "Reunión ordinaria", "Sesión de instalación", "Sesión ordinaria"… como lo dice ("" si no).
- puntos: cada viñeta. tipo = "proyecto" (Proyecto de Ley), "anteproyecto" (Anteproyecto de Ley) u "otro";
  numero = el número del proyecto o anteproyecto (0 si no tiene); texto = la viñeta completa, tal cual."""
ESQUEMA = {"type": "object", "properties": {
    "es_agenda": {"type": "boolean"},
    "sesiones": {"type": "array", "items": {"type": "object", "properties": {
        "fecha": {"type": "string"}, "hora": {"type": "string"}, "comision": {"type": "string"},
        "subcomision": {"type": "boolean"}, "lugar": {"type": "string"}, "preside": {"type": "string"},
        "tipo_reunion": {"type": "string"},
        "puntos": {"type": "array", "items": {"type": "object", "properties": {
            "tipo": {"type": "string", "enum": ["proyecto", "anteproyecto", "otro"]}, "numero": {"type": "integer"},
            "texto": {"type": "string"}}, "required": ["tipo", "numero", "texto"]}}},
        "required": ["fecha", "hora", "comision", "subcomision", "lugar", "preside", "tipo_reunion", "puntos"]}}},
    "required": ["es_agenda", "sesiones"]}


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS agenda_x (id TEXT PRIMARY KEY, post TEXT, fecha TEXT, hora TEXT, "
                "comision TEXT, datos TEXT, avisado INTEGER DEFAULT 0, creado TEXT)")


def encolar(post):
    """Lo llama redes.recibir con cada publicación nueva de @asambleapa que trae fotos."""
    os.makedirs(os.path.dirname(COLA), exist_ok=True)
    with open(COLA, "a", encoding="utf-8") as f:
        f.write(json.dumps(post, ensure_ascii=False) + "\n")


def clave(comision):
    """'Subcomisión de Trabajo, Salud y Desarrollo Social' y 'Comisión de Trabajo, Salud…' → misma clave."""
    t = cerebro.normal(comision).lower()
    if t.startswith("pleno"):
        return "pleno"
    t = re.sub(r"\b(sub)?comision(es)?\b|\bde\b|\bdel\b|\by\b|\bla\b|\bel\b", " ", t)
    return " ".join(t.split())


def imagenes(urls):
    out = []
    for u in urls[:8]:
        if not re.match(r"https://pbs\.twimg\.com/", u):
            continue  # solo las fotos de X
        try:
            datos = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        except Exception as e:
            print(f"  foto {u}: {e}", flush=True)
            continue
        out.append({"inline_data": {"mime_type": "image/png" if "format=png" in u else "image/jpeg",
                                    "data": base64.b64encode(datos).decode()}})
    return out


def leer(post):
    """Las sesiones de la agenda que muestran las fotos de una publicación ([] si no es una agenda)."""
    adjuntos = imagenes(post.get("fotos") or [])
    if not adjuntos:
        return []
    fecha = (post.get("fecha") or "")[:10] or datetime.date.today().isoformat()
    r = ia.generar_json(LEER, f"Publicación del {fecha}: {post.get('texto') or '(sin texto)'}", ESQUEMA, adjuntos=adjuntos)
    return r["sesiones"] if r.get("es_agenda") else []


def guardar(post, sesiones):
    crear_tabla()
    for s in sesiones:
        s["hora"] = (s.get("hora") or "")[:5]
        id_ = cerebro.huella(s["fecha"], s["hora"], clave(s["comision"]))
        d1.consulta("INSERT OR IGNORE INTO agenda_x (id, post, fecha, hora, comision, datos, creado) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [id_, post.get("url") or "", s["fecha"], s["hora"], s["comision"], json.dumps(s, ensure_ascii=False),
                     cerebro.ahora()])


def procesar():
    """Saca la cola y lee cada publicación. Si Gemini falla, la publicación vuelve a la cola."""
    if not os.path.exists(COLA):
        return 0
    tomada = COLA + ".tomada"
    os.replace(COLA, tomada)
    posts = [json.loads(l) for l in open(tomada, encoding="utf-8") if l.strip()]
    os.remove(tomada)
    n = 0
    for p in posts:
        try:
            sesiones = leer(p)
        except Exception as e:
            print(f"agenda x: {p.get('url')}: {e}", flush=True)
            encolar(p)
            continue
        if sesiones:
            guardar(p, sesiones)
            n += len(sesiones)
            print(f"agenda x: {len(sesiones)} sesiones en {p.get('url')}", flush=True)
    return n


# ---------------------------------------------------------------- a la tabla agenda

def linea_punto(p):
    """Con el formato de la web ("Proyecto de Ley 713 «…»") para que el cruce con las fichas lo encuentre."""
    texto = re.sub(r"\s+", " ", p["texto"]).strip()
    if p["tipo"] != "otro" and p["numero"] and not re.search(rf"\b{p['numero']}\b", texto[:80]):
        texto = f"{'Anteproyecto' if p['tipo'] == 'anteproyecto' else 'Proyecto'} de Ley {p['numero']}: {texto}"
    return "- " + texto


def descripcion(s):
    inicio = s.get("tipo_reunion") or "Reunión"
    if s.get("subcomision") and "subcomisi" not in inicio.lower():
        inicio = "Reunión de subcomisión" if inicio.lower().startswith("reuni") else f"{inicio} (subcomisión)"
    lineas = [inicio.rstrip(".") + "."] + [linea_punto(p) for p in s["puntos"]
                                           if cerebro.normal(p["texto"]) != cerebro.normal(inicio)]
    if s.get("preside"):
        lineas.append(f"Preside: H.D. {s['preside']}.")
    return "\n".join(lineas)


def nombre_comision(s):
    import agente
    return "Pleno de la Asamblea" if clave(s["comision"]) == "pleno" else agente.nombre_comision("COMISION DE " + s["comision"].upper())


def fichas_de(texto, indice):
    return [str(f["ficha"]) for f in indice.buscar(texto)]


def indice_fichas():
    import prensa
    filas = d1.consulta("SELECT ficha, proyecto, anteproyecto, titulo_oficial, fecha_presentacion FROM proyectos")
    return prensa.Indice({str(f["ficha"]): {"ficha": str(f["ficha"]), "proyecto": f["proyecto"], "anteproyecto": f["anteproyecto"],
                                            "titulo": f["titulo_oficial"] or "", "fecha": f["fecha_presentacion"] or ""} for f in filas})


def poner_fichas(agenda_id, fichas):
    if fichas:
        d1.consulta("INSERT OR IGNORE INTO agenda_fichas (agenda_id, ficha) VALUES " + ",".join("(?, ?)" for _ in fichas),
                    [x for f in fichas for x in (agenda_id, int(f))])


def aplicar():
    """Suma a la agenda lo de X que la web no tiene (desde ayer). Devuelve los avisos de lo que se agregó por primera vez."""
    crear_tabla()
    hoy = datetime.date.today()
    desde = (hoy - datetime.timedelta(days=1)).isoformat()
    xs = d1.consulta("SELECT * FROM agenda_x WHERE fecha >= ? ORDER BY fecha, hora", [desde])
    if not xs:
        return []
    filas = d1.consulta("SELECT id, fecha, hora, comision, descripcion, fichas FROM agenda WHERE fecha >= ?", [desde])
    indice, avisos = None, []
    for x in xs:
        s = json.loads(x["datos"])
        k, propia = clave(s["comision"]), X_BASE + int(x["id"][:7], 16)
        web = [f for f in filas if f["fecha"] == x["fecha"] and f["id"] < X_BASE and clave(f["comision"]) == k]
        web.sort(key=lambda f: abs(int(f["hora"][:2] or 0) - int(x["hora"][:2] or 0)))
        indice = indice or indice_fichas()
        if web:  # la web ya la tiene: si había fila de X, sobra; se agregan los puntos que la web no trae
            if any(f["id"] == propia for f in filas):
                d1.consulta("DELETE FROM agenda WHERE id = ?", [propia])
                d1.consulta("DELETE FROM agenda_fichas WHERE agenda_id = ?", [propia])
            f = web[0]
            if k == "pleno" or MARCA in (f["descripcion"] or ""):
                continue
            faltan = [p for p in s["puntos"] if p["tipo"] != "otro" and p["numero"]
                      and not re.search(rf"\b{p['numero']}\b", f["descripcion"] or "")]
            if not faltan:
                continue
            extra = "\n".join(linea_punto(p) for p in faltan)
            nuevas = fichas_de(extra, indice)
            todas = sorted(set(filter(None, (f["fichas"] or "").split(","))) | set(nuevas))
            d1.consulta("UPDATE agenda SET descripcion = ?, fichas = ? WHERE id = ?",
                        [f"{f['descripcion']}\n\n{MARCA}\n{extra}", ",".join(todas), f["id"]])
            poner_fichas(f["id"], nuevas)
            if not x["avisado"]:
                avisos.append(f"• {x['hora']} · {f['comision']}: la web no traía {len(faltan)} punto(s)\n{extra}")
        else:
            texto = descripcion(s)
            if any(f["id"] == propia and f["descripcion"] == texto for f in filas):
                continue  # ya está (se escribe solo lo que cambia: límite diario de escrituras de D1)
            fichas = fichas_de(texto, indice)
            d1.consulta("INSERT OR REPLACE INTO agenda (id, fecha, hora, comision, lugar, organizador, descripcion, fichas, actualizado) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [propia, x["fecha"], x["hora"], nombre_comision(s), s.get("lugar") or "", ORGANIZADOR, texto,
                         ",".join(fichas), cerebro.ahora()])
            poner_fichas(propia, fichas)
            if not x["avisado"]:
                avisos.append(f"• {x['hora']} · {nombre_comision(s)} (no estaba en la web)\n{texto}")
        if not x["avisado"]:
            d1.consulta("UPDATE agenda_x SET avisado = 1 WHERE id = ?", [x["id"]])
    return avisos


def revisar():
    n = procesar()
    avisos = aplicar()
    if avisos:
        cerebro.telegram("📅 Agenda de hoy publicada por la Asamblea en X: lo que no estaba en la web\n\n" + "\n\n".join(avisos),
                         destino="asamblea", agente="cronista")
    return f"{n} sesiones leídas, {len(avisos)} agregadas a la agenda"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 1:
        sesiones = leer({"fotos": sys.argv[1:], "fecha": datetime.date.today().isoformat(), "url": "a mano"})
        print(json.dumps(sesiones, ensure_ascii=False, indent=1))
        if sesiones:
            guardar({"url": "a mano"}, sesiones)
    print(revisar())
