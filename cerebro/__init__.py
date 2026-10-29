"""El cerebro: una sola puerta para guardar, enlazar y buscar todo lo que entra (ver PLAN.md, sección 5).

- guardar_entidades(): actores, instituciones, comisiones... con sus alias.
- guardar_documento(): cualquier texto que entra, partido en fragmentos con búsqueda de texto completo. No duplica.
- enlazar(): busca en los documentos nuevos las entidades que mencionan (por alias) y anota las menciones.
- buscar(): búsqueda de texto completo en todo el cerebro.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata

CARPETA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CARPETA)
from db import d1  # noqa: E402

LARGO_FRAGMENTO = 1500
CONECTORES = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E"}
NOMBRES_DE_PILA = set("""JUAN CARLOS JOSE LUIS MARIA ANA JORGE MANUEL ANTONIO FRANCISCO JAVIER MIGUEL ANGEL RAUL RAMON
PEDRO PABLO JESUS ALBERTO EDUARDO ENRIQUE RICARDO ROBERTO FERNANDO DANIEL DAVID ERNESTO OSCAR VICTOR HECTOR ARIEL
ALEJANDRO ANDRES GABRIEL RAFAEL SERGIO MARIO MARCOS JULIO CESAR ALEXIS ROGELIO EDWIN NELSON ISAAC TOMAS RONALD
MARTA ROSA ELENA LUISA CARMEN ISABEL TERESA PATRICIA LAURA GRACIELA FLOR LILIA SHIRLEY DANA JANINE OLGA ALEXANDRA
BEATRIZ DINOSKA JACKELINE NIURKA MARUJA VIRNA DORIS GRETTEL AGNES DELIA MERCEDES EMERITA AURORA PAULETTE""".split())


def cargar_env():
    """En la Mac las claves vienen de .env; en GitHub Actions, de los secretos."""
    ruta = os.path.join(CARPETA, ".env")
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ahora():
    return datetime.datetime.now().isoformat(timespec="seconds")


# a dónde va cada aviso (Andrés, 2026-10-25): general = el GRUPO de la oficina (Paula, Diego, Tomás, lo importante de
# una sesión); gaceta = bot de la Gaceta (Inés); asamblea = bot de la Asamblea (sesiones en vivo, Keylaw); alertas =
# el bot actual (Corte, reguladores, avisos del sistema). Cada destino usa TELEGRAM_<DESTINO>_TOKEN y _CHAT del .env;
# si faltan, sale por el bot actual (TELEGRAM_TOKEN) al chat de Andrés (TELEGRAM_CHAT_ID).
DESTINOS = ("general", "gaceta", "asamblea", "alertas")


def telegram(texto, vista_previa=False, destino="alertas", ref=None, agente=None):
    """Aviso por Telegram al chat de su destino. Sin claves, solo lo imprime. vista_previa=True deja que Telegram
    muestre la tarjeta del enlace (titular e imagen): solo sale con UN enlace por mensaje. ref ("entrevista:<video>",
    "norma:<id>", "url:<enlace>"...) y agente quedan anotados en chat_mensajes: si alguien en el grupo RESPONDE a ese
    mensaje ("pásenme la bola roja de esto"), cerebro/chat.py sabe de qué se habla (chat de doble vía)."""
    import urllib.parse
    import urllib.request
    d = destino.upper()
    token = os.environ.get(f"TELEGRAM_{d}_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    # uno o varios chats separados por comas (cada persona que le dio "Iniciar" al bot); sin _CHAT, el de Andrés
    chats = [c.strip() for c in (os.environ.get(f"TELEGRAM_{d}_CHAT") or os.environ.get("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]
    chat = chats[0] if chats else None
    if not (token and chat):
        print("(sin Telegram) " + texto)
        return
    for chat in chats:
        datos = urllib.parse.urlencode({"chat_id": chat, "text": texto[:4000],
                                      "disable_web_page_preview": "false" if vista_previa else "true"}).encode()
        r = None
        for intento in range(3):  # un aviso que no sale nunca debe tumbar al agente que lo manda (2026-10-26: un 429
            try:                   # de Telegram cortó la grabación de la Línea 3 antes de empezar)
                r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=datos, timeout=30))
                break
            except Exception as e:
                espera = 5
                if getattr(e, "code", None) == 429:
                    try:
                        espera = json.loads(e.read().decode())["parameters"]["retry_after"] + 1
                    except Exception:
                        espera = 30
                print(f"telegram ({destino}): {e}; reintento en {espera} s", flush=True)
                import time
                time.sleep(min(espera, 120))
        if r is None:  # Telegram sigue frenando: el aviso espera y se reintenta, no se pierde
            print(f"telegram ({destino}): no salió, queda en espera: {texto[:80]}", flush=True)
            reintentar_luego(texto, vista_previa, destino, ref, agente, chat)
            continue
        if ref or agente:
            try:
                anotar_mensaje(chat, r["result"]["message_id"], destino, agente, ref, texto)
            except Exception as e:
                print(f"telegram (anotar): {e}", flush=True)


def reintentar_luego(texto, vista_previa, destino, ref, agente, chat, vez=1):
    """Un aviso que Telegram no dejó pasar (frenos o caídas de Telegram, como la del 26/10) se reintenta cada 2 minutos,
    hasta 30 veces (una hora), en un hilo aparte."""
    import threading
    import time
    import urllib.parse
    import urllib.request

    def otra_vez():
        time.sleep(120)
        token = os.environ.get(f"TELEGRAM_{destino.upper()}_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
        datos = urllib.parse.urlencode({"chat_id": chat, "text": texto[:4000],
                                        "disable_web_page_preview": "false" if vista_previa else "true"}).encode()
        try:
            r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=datos, timeout=30))
            print(f"telegram ({destino}): salió en el reintento {vez}", flush=True)
            if ref or agente:
                anotar_mensaje(chat, r["result"]["message_id"], destino, agente, ref, texto)
        except Exception as e:
            if vez < 30:
                reintentar_luego(texto, vista_previa, destino, ref, agente, chat, vez + 1)
            else:
                print(f"telegram ({destino}): se perdió tras 30 reintentos ({e}): {texto[:80]}", flush=True)
    threading.Thread(target=otra_vez, daemon=True).start()


def anotar_mensaje(chat, mensaje, destino, agente, ref, texto):
    d1.consulta("CREATE TABLE IF NOT EXISTS chat_mensajes (chat TEXT, mensaje INTEGER, destino TEXT, agente TEXT, ref TEXT, "
                "texto TEXT, creado TEXT, PRIMARY KEY (chat, mensaje))")
    d1.consulta("INSERT OR REPLACE INTO chat_mensajes VALUES (?, ?, ?, ?, ?, ?, ?)",
                [str(chat), mensaje, destino, agente, ref, texto[:2000], ahora()])


_COLA = {}


def telegram_pausado(texto, vista_previa=False, destino="general", ref=None, agente=None):
    """Como telegram(), pero en fila: entre un mensaje y otro espera de 1 a 2,5 minutos al azar, para que el chat se
    sienta humano y no llegue una ráfaga de enlaces (Andrés, 2026-10-26). La fila vive en este proceso (la mesa): si
    la mesa se reinicia, lo que estaba esperando se pierde."""
    import queue
    import random
    import threading
    import time
    if "fila" not in _COLA:
        _COLA["fila"] = queue.Queue()

        def emisor():
            while True:
                t, vp, de, rf, ag = _COLA["fila"].get()
                try:
                    telegram(t, vista_previa=vp, destino=de, ref=rf, agente=ag)
                except Exception as e:
                    print(f"telegram: {e}", flush=True)
                if not _COLA["fila"].empty():
                    time.sleep(random.uniform(60, 150))
        threading.Thread(target=emisor, daemon=True).start()
    _COLA["fila"].put((texto, vista_previa, destino, ref, agente))


def ejemplos(producto, n=3):
    """Correos reales de Keyword (ejemplos/keyword/<Producto>/, no se suben) para que los agentes copien tono y forma.
    Se quitan remitente y fecha; solo quedan asunto y cuerpo."""
    import glob
    rutas = sorted(glob.glob(os.path.join(CARPETA, "ejemplos", "keyword", producto, "*.txt")), reverse=True)[:n]
    out = []
    for r in rutas:
        lineas = [l for l in open(r, encoding="utf-8").read().splitlines() if not l.startswith(("Fecha:", "De:"))]
        out.append("\n".join(lineas).strip())
    tipo = {"Keylaw": "keylaw", "Keymonitor": "keymonitor", "BolaRoja": "bolaroja"}.get(producto)
    if not out:
        return aprendido(tipo) if tipo else ""
    return ("\n\nEJEMPLOS REALES de Keyword (son de Ecuador: copia su tono, registro, estructura y largo, NO sus "
            "instituciones ni datos):\n\n" + "\n\n-----\n\n".join(out)) + (aprendido(tipo) if tipo else "")


def aprendido(tipo, n=4, largo=2500):
    """Aprendizaje nivel 2: las últimas correcciones que el equipo hizo a reportes de este tipo en la oficina (la
    versión del agente y la corregida), para que el agente aprenda qué cambian. Vacío si todavía no hay."""
    import difflib
    from cerebro import aprendizaje
    from db import d1
    e = aprendizaje.estado()
    if not e["activo"]:  # apagado hasta el lanzamiento (Andrés, 2026-10-26)
        return ""
    try:
        filas = d1.consulta("SELECT original, corregido FROM correcciones WHERE tipo = ? AND actualizado >= ? "
                            "ORDER BY actualizado DESC LIMIT ?", [tipo, e["desde"], n * 3])
    except Exception:
        return ""
    casos = []
    for f in filas:
        a, b = (f["original"] or "").strip(), (f["corregido"] or "").strip()
        if a and b and difflib.SequenceMatcher(None, a, b).ratio() < 0.995:  # una coma no enseña nada
            casos.append(f"VERSIÓN DEL AGENTE:\n{a[:largo]}\n\nVERSIÓN CORREGIDA POR EL EQUIPO:\n{b[:largo]}")
        if len(casos) >= n:
            break
    if not casos:
        return ""
    return ("\n\nCORRECCIONES DEL EQUIPO DE KEYWORD PANAMÁ a reportes anteriores de este tipo (lo más importante: aprende "
            "qué cambian —tono, largo, orden, qué agregan o quitan— y aplícalo; NO copies sus datos):\n\n"
            + "\n\n-----\n\n".join(casos))


def normal(texto):
    """Sin tildes, en mayúsculas y solo letras y números: la forma en que se comparan nombres y textos."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", t).strip()


def slug(texto):
    return normal(texto).lower().replace(" ", "-")


def huella(*partes):
    return hashlib.sha1("|".join(str(p) for p in partes).encode()).hexdigest()[:16]


def crear():
    """Crea las tablas del cerebro (se puede repetir: todo es IF NOT EXISTS)."""
    d1.ejecutar_varias(open(os.path.join(CARPETA, "cerebro", "esquema.sql"), encoding="utf-8").read())


# ---------------------------------------------------------------- entidades

def alias_de_persona(nombre):
    """Formas en que la prensa y las actas nombran a una persona: completo, nombre + primer apellido, etc.
    Supone el orden hispano: uno o dos nombres y uno o dos apellidos ("de" y "del" van pegados al apellido)."""
    palabras = normal(nombre).split()
    bloques, i = [], 0
    while i < len(palabras):  # "DE LA GUARDIA" es un solo bloque
        j = i
        while j < len(palabras) - 1 and palabras[j] in CONECTORES:
            j += 1
        bloques.append(" ".join(palabras[i:j + 1]))
        i = j + 1
    formas = {" ".join(bloques)}
    if len(bloques) >= 4:  # dos nombres y dos apellidos
        nombres, apellidos = bloques[:2], bloques[2:]
        formas |= {f"{nombres[0]} {apellidos[0]}", " ".join([nombres[0]] + apellidos), " ".join(nombres + apellidos[:1])}
    elif len(bloques) == 3:  # puede ser "Juan Carlos Orillac" o "Benicio Robinson Grajales": solo formas con el último
        formas |= {f"{bloques[0]} {bloques[2]}", f"{bloques[1]} {bloques[2]}", f"{bloques[0]} {bloques[1]}"}
    # una forma hecha solo de nombres de pila ("JUAN CARLOS") confundiría a medio país
    return {f for f in formas if len(f.split()) >= 2 and not set(f.split()) <= NOMBRES_DE_PILA}


def guardar_entidades(entidades):
    """entidades: [{id, tipo, subtipo, nombre, cargo, datos (dict), perfil, fuente, alias (set)}]. Reemplaza las que
    ya existen. Un alias que calza con dos entidades distintas se descarta (sería ambiguo para el enlazador)."""
    if not entidades:
        return
    filas = [[e["id"], e["tipo"], e.get("subtipo"), e["nombre"], e.get("cargo"),
              json.dumps(e.get("datos") or {}, ensure_ascii=False), e.get("perfil"), e.get("fuente"), ahora()]
             for e in entidades]
    d1.insertar_muchas("entidades", ["id", "tipo", "subtipo", "nombre", "cargo", "datos", "perfil", "fuente",
                                     "actualizado"], filas, por_lote=50)
    duenos = {}
    for e in entidades:
        for a in set(e.get("alias") or ()) | {normal(e["nombre"])}:
            duenos.setdefault(a, set()).add(e["id"])
    ids = ",".join(d1.literal(e["id"]) for e in entidades)
    d1.ejecutar_varias(f"DELETE FROM alias WHERE entidad IN ({ids})")
    d1.insertar_muchas("alias", ["alias", "entidad"],
                       [[a, next(iter(ds))] for a, ds in duenos.items() if len(ds) == 1 and len(a) >= 5],
                       modo="INSERT OR IGNORE")


def relacionar(relaciones):
    """relaciones: [(origen, tipo, destino, documento, fecha, detalle)]."""
    d1.insertar_muchas("relaciones", ["origen", "tipo", "destino", "documento", "fecha", "detalle"],
                       [list(r) for r in relaciones])


# ---------------------------------------------------------------- documentos

def fragmentar(texto):
    """Trozos de ~1500 caracteres que terminan en un fin de párrafo o de oración cuando se puede."""
    texto = re.sub(r"[ \t]+", " ", texto or "").strip()
    trozos = []
    while len(texto) > LARGO_FRAGMENTO:
        corte = max(texto.rfind("\n", 0, LARGO_FRAGMENTO), texto.rfind(". ", 0, LARGO_FRAGMENTO))
        corte = corte + 1 if corte > LARGO_FRAGMENTO // 2 else LARGO_FRAGMENTO
        trozos.append(texto[:corte].strip())
        texto = texto[corte:]
    if texto.strip():
        trozos.append(texto.strip())
    return trozos


def guardar_documento(fuente, id_origen, texto, tipo=None, titulo=None, url=None, fecha=None, resumen=None):
    """La puerta única de entrada. Devuelve (id, nuevo). Si ya existía, no hace nada."""
    id_ = huella(fuente, id_origen)
    if d1.consulta("SELECT 1 FROM documentos WHERE id = ?", [id_]):
        return id_, False
    trozos = fragmentar(texto)
    d1.insertar_muchas("fragmentos", ["documento", "n", "texto"], [[id_, i, t] for i, t in enumerate(trozos)])
    d1.insertar_muchas("documentos", ["id", "fuente", "tipo", "titulo", "url", "fecha", "resumen", "largo", "estado",
                                      "creado"],
                       [[id_, fuente, tipo, titulo, url, fecha, resumen, len(texto or ""), "nuevo", ahora()]])
    return id_, True


def texto_documento(id_):
    return "\n".join(f["texto"] for f in d1.consulta(
        "SELECT texto FROM fragmentos WHERE documento = ? ORDER BY CAST(n AS INTEGER)", [id_]))


# ---------------------------------------------------------------- enlazador

VACIAS = {"DE", "LA", "DEL", "LOS", "LAS", "Y"}


def fichas_de_personas(nombre, personas):
    """Ids de las personas cuyo nombre calza con `nombre` por palabras (en cualquier orden, sin tildes):
    "Julio Armando Moltó Alaín" calza con "Julio Moltó"; se ignoran comillas, apodos y marcas como [NV]."""
    limpio = re.sub(r"\[[^\]]*\]|[“”\"«»][^“”\"«»]*[“”\"«»]|\([^)]*\)", " ", nombre)
    def palabras_de(t):
        return {w for w in re.sub(r"[’'`´.\-]", " ", normal(t)).split() if w not in VACIAS and len(w) > 1}
    palabras = palabras_de(limpio)
    out = []
    for p in personas:
        suyas = palabras_de(p["nombre"])
        if len(suyas) >= 2 and (suyas <= palabras or (len(palabras) >= 2 and palabras <= suyas)):
            out.append(p["id"])
    return out


def cargar_alias():
    return {f["alias"]: f["entidad"] for f in d1.consulta("SELECT alias, entidad FROM alias")}


def menciones_en(texto, alias):
    """{entidad: (veces, cita)} de las entidades nombradas en el texto."""
    plano = " " + normal(texto) + " "
    encontradas = {}
    for a, entidad in alias.items():
        n = plano.count(f" {a} ")
        if n:
            veces, cita = encontradas.get(entidad, (0, None))
            if cita is None:
                cita = _cita(texto, a)
            encontradas[entidad] = (veces + n, cita)
    return encontradas


def _cita(texto, alias_normal):
    """Unos 300 caracteres alrededor de la primera aparición (buscando en el texto original sin tildes)."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()
    patron = r"\W+".join(re.escape(p) for p in alias_normal.split())
    m = re.search(patron, plano)
    if not m:
        return None
    ini, fin = max(0, m.start() - 150), min(len(texto), m.end() + 150)
    return ("…" if ini else "") + re.sub(r"\s+", " ", texto[ini:fin]).strip() + ("…" if fin < len(texto) else "")


def enlazar(limite=200):
    """Anota las menciones de los documentos nuevos. Devuelve cuántos documentos enlazó."""
    pendientes = d1.consulta("SELECT id FROM documentos WHERE estado = 'nuevo' LIMIT ?", [limite])
    if not pendientes:
        return 0
    alias = cargar_alias()
    filas = []
    for p in pendientes:
        for entidad, (veces, cita) in menciones_en(texto_documento(p["id"]), alias).items():
            filas.append([p["id"], entidad, veces, cita])
    d1.insertar_muchas("menciones", ["documento", "entidad", "veces", "cita"], filas)
    ids = ",".join(d1.literal(p["id"]) for p in pendientes)
    d1.ejecutar_varias(f"UPDATE documentos SET estado = 'enlazado' WHERE id IN ({ids})")
    return len(pendientes)


# ---------------------------------------------------------------- búsqueda

def buscar(consulta, limite=20):
    """Búsqueda de texto completo: [{documento, titulo, fecha, fuente, trozo}]."""
    return d1.consulta(
        "SELECT f.documento, d.titulo, d.fecha, d.fuente, snippet(fragmentos, 2, '«', '»', '…', 24) AS trozo "
        "FROM fragmentos f JOIN documentos d ON d.id = f.documento WHERE fragmentos MATCH ? ORDER BY rank LIMIT ?",
        [consulta, limite])
