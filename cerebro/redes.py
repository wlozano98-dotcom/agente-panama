"""Redes sociales (X) con el Chrome de la oficina: la extensión (extension/oficina-chrome) lee cada 15 minutos las dos
listas privadas de la cuenta de la oficina (Medios Panamá y Autoridades Panamá) y manda las publicaciones al receptor
de la Mac, que guarda solo las nuevas en una bandeja local (no en D1: son cientos por día). Paula (cerebro/monitor.py)
las toma junto con los RSS y manda al chat la URL de las importantes; Diego saca de ellas la agenda de medios: los
invitados que anuncia cada programa ("Hoy nos acompaña…", #CaraACara, #RadioGrafía) y las apariciones de autoridades
(tabla `medios_agenda`). Andrés, 2026-10-26: "Autoridades en medios" muestra SOLO a quienes seguimos (las personas
del directorio del cerebro: Presidente, vicepresidenta, ministros, viceministros, diputados…) y Diego escucha sus
entrevistas solo; el resto queda en "Agenda de medios" con un botón "Seguir" (si no, se transcribiría demasiado).
La mesa (escuchar_anunciadas) busca la transmisión en el canal de YouTube del medio y la escucha.

Uso: python3 cerebro/redes.py        (muestra lo que hay en la bandeja, sin tomarlo)
"""
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

CARPETA = os.path.join(cerebro.CARPETA, "salidas", "redes")
VISTOS = os.path.join(CARPETA, "vistos.json")
BANDEJA = os.path.join(CARPETA, "bandeja.jsonl")
CANDADO = threading.Lock()
HORAS = 12  # lo publicado hace más de 12 horas ya no es noticia: se anota como visto y no se revisa

# solo pasan a Diego las publicaciones que pueden anunciar una entrevista o una aparición (ahorra Gemini)
PISTAS = re.compile(r"entrevista|invitad|nos acompaña|acompañan|conversamos|conversa con|dialogamos|#caraacara|"
                    r"#radiograf|en vivo|estar[áé] en|conferencia|declaraciones|en el programa|en estudio|en cabina|"
                    r"hoy en|este domingo|esta noche|mañana en|agenda", re.I)

AGENDA = """Eres Diego, de Keyword (consultora de asuntos públicos en Panamá), y armas la agenda de medios del día.
Recibes publicaciones de X de medios y de autoridades de Panamá. Devuelve SOLO las que anuncian o cuentan una
entrevista o aparición de una persona con peso público (autoridad, diputado, dirigente, gremio, experto) en un
programa o medio: un medio que presenta a su invitado ("Hoy nos acompaña…", "#CaraACara", "En #RadioGrafía…",
"en entrevista con…"), una autoridad que avisa que estará en un programa (también dentro de su agenda del día), o una conferencia de
prensa anunciada.
NO devuelvas notas de prensa comunes, citas de un discurso o publicaciones sin invitado. Por cada una:
- id: el id de la publicación.
- quien: el nombre como aparece; cargo: el cargo SOLO si la publicación lo dice (nunca lo deduzcas).
- medio y programa (vacío si no se sabe); cuando: "hoy 7:30", "domingo 11:30", etc., como lo dice (vacío si no).
- estado: "anunciada" si todavía no ocurre o está en curso; "emitida" si ya pasó."""
ESQUEMA_AGENDA = {"type": "object", "properties": {"apariciones": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "quien": {"type": "string"}, "cargo": {"type": "string"}, "medio": {"type": "string"},
    "programa": {"type": "string"}, "cuando": {"type": "string"},
    "estado": {"type": "string", "enum": ["anunciada", "emitida"]}},
    "required": ["id", "quien", "cargo", "medio", "programa", "cuando", "estado"]}}},
    "required": ["apariciones"]}


# canal de YouTube de cada medio (investigación de ChatGPT, Invesitgacion/…report-3 6.md), por palabras de la cuenta,
# el medio o el programa
CANALES = [
    (r"ecopanama|ecotv|eco tv|radiograf|rpc|enfoque", "https://www.youtube.com/@ECOtvPanama/streams"),
    (r"treporta|telemetro|cara ?a ?cara|debate abierto", "https://www.youtube.com/@telemetropa/streams"),
    (r"tvn", "https://www.youtube.com/@TVNNoticiasYT/streams"),
    (r"sertv", "https://www.youtube.com/@SertvNoticias/streams"),
    (r"radiopanama|radio panam|panam[aá] hoy|pol[ií]tica a debate", "https://www.youtube.com/@RadioPanama945/streams"),
    (r"miller", "https://www.youtube.com/@JulioMillerPma/streams"),
    (r"kw ?continente", "https://www.youtube.com/@kwcontinente95.7/streams"),
    (r"\bnex", "https://www.youtube.com/@NexNoticias/streams"),
    (r"presidencia", "https://www.youtube.com/@presidenciapma/streams"),
]


def canal_de(fila):
    texto = " ".join(str(fila.get(k) or "") for k in ("cuenta", "medio", "programa")).lower()
    return next((url for patron, url in CANALES if re.search(patron, texto)), None)


def seguido(quien, alias=None):
    """La entidad del directorio (persona) si es alguien a quien seguimos; si no, None."""
    actores = [e for e in cerebro.menciones_en(quien, alias or cerebro.cargar_alias()) if e.startswith("persona:")]
    return actores[0] if len(actores) == 1 else None


def recibir(lista, posts):
    """Lo que trae la extensión: guarda en la bandeja solo lo nuevo y reciente. La primera vez solo anota lo que hay."""
    os.makedirs(CARPETA, exist_ok=True)
    with CANDADO:
        primera = not os.path.exists(VISTOS)
        vistos = {} if primera else json.load(open(VISTOS))
        limite = time.time() - 4 * 86400
        vistos = {k: v for k, v in vistos.items() if v > limite}
        reciente = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - HORAS * 3600))
        nuevos = [dict(p, lista=lista) for p in posts if p.get("id") and p["id"] not in vistos and (p.get("fecha") or "") >= reciente]
        for p in posts:
            if p.get("id"):
                vistos.setdefault(p["id"], time.time())
        json.dump(vistos, open(VISTOS, "w"))
        if primera:
            return f"{len(posts)} leídas, primera vez: solo anotadas"
        with open(BANDEJA, "a", encoding="utf-8") as f:
            for p in nuevos:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    from cerebro import agenda_x
    for p in nuevos:  # la agenda del día que publica la Asamblea en imágenes (cerebro/agenda_x.py)
        if (p.get("cuenta") or "").lower() == "asambleapa" and p.get("fotos") and not p.get("repost"):
            agenda_x.encolar(p)
    return f"{len(posts)} leídas, {len(nuevos)} nuevas, {sum(1 for p in posts if p.get('fotos'))} con fotos"


def tomar():
    """Saca de la bandeja todo lo pendiente (la bandeja queda vacía)."""
    with CANDADO:
        if not os.path.exists(BANDEJA):
            return []
        en_proceso = BANDEJA + ".tomada"
        os.replace(BANDEJA, en_proceso)
    posts = [json.loads(l) for l in open(en_proceso, encoding="utf-8") if l.strip()]
    os.remove(en_proceso)
    return posts


def devolver(posts):
    """Si Gemini no pudo revisarlas (p. ej. sin cuota), vuelven a la bandeja para la próxima vuelta."""
    with CANDADO, open(BANDEJA, "a", encoding="utf-8") as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def hora_local(iso):
    """'2026-10-26T05:12:05.000Z' → '2026-10-26T00:12:05' (hora de la Mac, que es la de Panamá)."""
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone))
    except (TypeError, ValueError):
        return cerebro.ahora()


def como_titulares(posts):
    """Las publicaciones en el formato de los titulares de Paula (monitor.py)."""
    return [{"id": cerebro.huella("x", p["id"]), "medio": f"X @{p['cuenta']}",
             "titulo": (p.get("texto") or "").replace("\n", " ")[:400] + (" (repost)" if p.get("repost") else ""),
             "url": p["url"]} for p in posts if p.get("texto")]


def crear_tabla():
    # seguir: 0 = no, 1 = escuchar cuando transmita, 2 = escuchando o escuchada (video), 3 = no se encontró transmisión
    d1.consulta("CREATE TABLE IF NOT EXISTS medios_agenda (id TEXT PRIMARY KEY, lista TEXT, cuenta TEXT, fecha TEXT, "
                "quien TEXT, cargo TEXT, medio TEXT, programa TEXT, cuando TEXT, estado TEXT, url TEXT, texto TEXT, "
                "creado TEXT, entidad TEXT, seguir INTEGER DEFAULT 0, video TEXT)")


def agenda(posts):
    """Diego: invitados y apariciones anunciados en las redes → medios_agenda; Telegram avisa los anunciados."""
    candidatas = [p for p in posts if PISTAS.search(p.get("texto") or "")]
    if not candidatas:
        return "sin anuncios de entrevistas"
    crear_tabla()
    por_id = {p["id"]: p for p in candidatas}
    r = ia.generar_json(AGENDA, "\n\n".join(f"{p['id']} · @{p['cuenta']} ({p.get('nombre') or ''}) · {p.get('fecha') or ''}\n"
                                           f"{p['texto'][:800]}" for p in candidatas), ESQUEMA_AGENDA)
    filas, alias = [], cerebro.cargar_alias()
    for a in r["apariciones"]:
        p = por_id.get(a["id"])
        if not p or not a["quien"].strip():
            continue
        entidad = seguido(a["quien"], alias)
        filas.append([p["id"], p["lista"], p["cuenta"], hora_local(p.get("fecha")), a["quien"], a["cargo"],
                      a["medio"] or p.get("nombre") or "", a["programa"], a["cuando"], a["estado"], p["url"], p["texto"][:1500],
                      cerebro.ahora(), entidad, 1 if entidad and a["estado"] == "anunciada" else 0])
        if a["estado"] == "anunciada" and entidad:  # solo se avisa lo de quienes seguimos
            programa = " · ".join(x for x in (a["programa"], a["medio"]) if x)
            cerebro.telegram_pausado(f"🎙 {a['quien']}{', ' + a['cargo'] if a['cargo'] else ''}"
                             f"{' en ' + programa if programa else ''}{' (' + a['cuando'] + ')' if a['cuando'] else ''}\n{p['url']}")
    if filas:
        d1.insertar_muchas("medios_agenda", ["id", "lista", "cuenta", "fecha", "quien", "cargo", "medio", "programa", "cuando",
                                             "estado", "url", "texto", "creado", "entidad", "seguir"], filas, modo="INSERT OR IGNORE")
    return f"{len(candidatas)} con pistas, {len(filas)} entrevistas o apariciones"


if __name__ == "__main__":
    pend = [json.loads(l) for l in open(BANDEJA, encoding="utf-8")] if os.path.exists(BANDEJA) else []
    print(f"{len(pend)} publicaciones en la bandeja")
    for p in pend[:20]:
        print(f"  [{p['lista']}] @{p['cuenta']} {p.get('fecha', '')[:16]}  {(p.get('texto') or '')[:90]!r}")
