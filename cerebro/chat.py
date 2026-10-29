"""Chat de doble vía en los grupos de Telegram (Andrés, 2026-10-25: "un chat un poquito más inteligente").

La mesa de la Mac lo corre en un hilo (escuchar()). Se le habla a un agente:
- por su nombre al comienzo: "Fernando, ¿dónde dijo esto?", "Kiwi: ¿cuánto suele tardar un segundo debate?";
- respondiendo a un mensaje de un agente (contesta el que lo escribió: chat_mensajes guarda quién y de qué era);
- o nombrando al bot (@keyword_panama_oficina_bot).
Lo demás que se conversa en el grupo no se toca.

Qué se puede pedir:
- "bola roja" → Diego la arma con ESE mensaje (entrevista, norma, resolución, fallo, nota de prensa) y la manda al chat;
  es lo ÚNICO que llega completo al chat (Andrés, 2026-10-26);
- "Keyeconomics" → Tomás lo deja en la oficina y el chat solo avisa que está para revisión;
- "Keylaw" (respondiendo a una sesión) → la Relatora lo escribe y avisa cuando está en la oficina;
- "transcripción" → se avisa dónde está en la oficina (mesa de Fernando o de Diego), no se manda el archivo;
- cualquier pregunta → el cerebro de Kiwi (Worker, /oficina/kiwi), que contesta como el agente nombrado, con el mensaje
  citado como contexto: citas con minuto y enlace al video en ese minuto, cuánto suele tardar un proyecto, etc.
Bots: el de la oficina y el de la Gaceta se leen con getUpdates (no tienen webhook); el de la Asamblea tiene el webhook
del Worker, que deja los mensajes dirigidos a los agentes en la tabla chat_entrada. Solo se atienden los chats del
.env (TELEGRAM_<DESTINO>_CHAT y TELEGRAM_CHAT_ID).
"""
import html
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

WORKER = "https://agente-panama.agentemonitoreopa.workers.dev"
NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TRANSCRIPCIONES = os.path.join(cerebro.CARPETA, "salidas", "transcripciones")

# nombre en el chat → (nombre, función, código del agente)
AGENTES = {
    "kiwi": ("Kiwi", "jefe de redacción de la oficina", "kiwi"),
    "fernando": ("Fernando", "Asamblea Nacional: proyectos, sesiones y Keylaw", "relatora"),
    "ines": ("Inés", "Gaceta Oficial y Keymonitor", "normativa"),
    "elena": ("Elena", "Órgano Judicial", "judicial"),
    "mateo": ("Mateo", "Entes Reguladores", "regulatoria"),
    "sofia": ("Sofía", "Perfiladora de actores", "perfilador"),
    "diego": ("Diego", "entrevistas, medios y bolas rojas", "entrevistas"),
    "paula": ("Paula", "monitora de medios", "monitor"),
    "tomas": ("Tomás", "cifras y Keyeconomics", "cifras"),
}
POR_CODIGO = {v[2]: k for k, v in AGENTES.items()}
POR_BOT = {"general": "kiwi", "gaceta": "ines", "asamblea": "fernando"}  # quién contesta si no se nombra a nadie


def _api(token, metodo, datos=None, timeout=40):
    cuerpo = urllib.parse.urlencode(datos or {}).encode()
    return json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{metodo}", data=cuerpo, timeout=timeout))


def token_de(destino):
    return os.environ.get(f"TELEGRAM_{destino.upper()}_TOKEN") or os.environ.get("TELEGRAM_TOKEN")


def chats_permitidos():
    out = set()
    for clave in ("TELEGRAM_GENERAL_CHAT", "TELEGRAM_GACETA_CHAT", "TELEGRAM_ASAMBLEA_CHAT", "TELEGRAM_CHAT_ID"):
        out |= {c.strip() for c in os.environ.get(clave, "").split(",") if c.strip()}
    return out


def responder_en(destino, chat, texto, a_mensaje=None, agente=None, ref=None):
    for i in range(0, len(texto), 4000):
        r = _api(token_de(destino), "sendMessage", {"chat_id": chat, "text": texto[i:i + 4000], "disable_web_page_preview": "true",
                                                    **({"reply_to_message_id": a_mensaje} if a_mensaje and i == 0 else {})})
        if agente:  # así, si le responden a esta respuesta, se sabe quién habló y de qué
            cerebro.anotar_mensaje(chat, r["result"]["message_id"], destino, agente, ref, texto[i:i + 4000])


def escribiendo(destino, chat):
    try:
        _api(token_de(destino), "sendChatAction", {"chat_id": chat, "action": "typing"}, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------- a quién y de qué

def sin_tildes(t):
    return cerebro.normal(t).lower()


def dirigido(texto, citado_es_bot, usuario_bot):
    """(clave del agente, pregunta sin el nombre) si el mensaje es para un agente; None si es conversación del equipo."""
    t = texto.strip()
    m = re.match(r"^\s*@?(\w+)[\s,:;.!¡¿?-]+(.*)$", t, re.S)
    if m and sin_tildes(m.group(1)) in AGENTES:
        return sin_tildes(m.group(1)), m.group(2).strip() or t
    if usuario_bot and f"@{usuario_bot}".lower() in t.lower():
        return "", re.sub(rf"@{usuario_bot}", "", t, flags=re.I).strip()
    if citado_es_bot:
        return "", t
    return None


def anotado(chat, mensaje):
    try:
        f = d1.consulta("SELECT agente, ref, texto FROM chat_mensajes WHERE chat = ? AND mensaje = ?", [str(chat), mensaje])
        return f[0] if f else None
    except Exception:
        return None  # la tabla aún no existe


def texto_de_pagina(url, largo=20000):
    """El texto de una nota de prensa enlazada (los párrafos <p>), para la bola roja o el Keyeconomics."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
        h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:
        h = ""
    titulo = (re.findall(r"<title[^>]*>(.*?)</title>", h, re.S) or [""])[0]
    parrafos = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p))).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", h, re.S)]
    cuerpo = "\n".join(p for p in parrafos if len(p) > 40)
    if not cuerpo:  # X u otra página sin párrafos: lo que Paula ya vio (titular o publicación)
        f = d1.consulta("SELECT medio, titulo FROM monitor_vistos WHERE url = ?", [url])
        cuerpo = f"[{f[0]['medio']}] {f[0]['titulo']}" if f else ""
    return f"{html.unescape(titulo).strip()}\n{url}\n\n{cuerpo}"[:largo]


def material(ref, citado):
    """Todo el texto que hay detrás del mensaje al que responden (para armar una bola roja o un Keyeconomics)."""
    tipo, _, valor = (ref or "").partition(":")
    partes = [f"MENSAJE DEL CHAT:\n{citado}"] if citado else []
    if tipo == "url":
        partes.append("NOTA ENLAZADA:\n" + texto_de_pagina(valor))
    elif tipo in ("sesion", "entrevista"):
        ruta = os.path.join(TRANSCRIPCIONES, f"{valor}.txt")
        if os.path.exists(ruta):
            partes.append("TRANSCRIPCIÓN:\n" + open(ruta, encoding="utf-8").read()[:80000])
    elif tipo == "gaceta":
        for n in d1.consulta("SELECT tipo, numero, entidad, titulo, resumen FROM normas WHERE edicion = ? AND impacto IN ('alto', 'medio')", [valor]):
            partes.append(f"NORMA: {n['tipo']} {n['numero']} ({n['entidad']}): {n['titulo']}\n{n['resumen'] or ''}")
    elif tipo in ("regulatorias", "judiciales"):
        ids = [x for x in valor.split(",") if x]
        if ids:
            for x in d1.consulta(f"SELECT * FROM {tipo} WHERE id IN ({','.join('?' * len(ids))})", ids):
                partes.append(f"{x.get('ente') or x.get('tribunal') or ''}: {x['nombre']} · {x['fecha']}\n{x['resumen']}\n{x['url']}")
    return "\n\n-----\n\n".join(partes)


def kiwi(pregunta, agente, citado):
    """El cerebro de Kiwi en el Worker, contestando como el agente nombrado."""
    nombre, funcion, _ = AGENTES[agente]
    datos = json.dumps({"mensaje": pregunta[:1000], "historial": [], "persona": {"nombre": nombre, "funcion": funcion},
                        "citado": (citado or "")[:2500]}).encode()
    req = urllib.request.Request(f"{WORKER}/oficina/kiwi?k={os.environ['OFICINA_CLAVE']}", data=datos, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": NAVEGADOR})
    return json.load(urllib.request.urlopen(req, timeout=240))["respuesta"]


VIVO = """Eres {nombre}, de Keyword (consultora de asuntos públicos en Panamá), y estás siguiendo una transmisión
{estado}. Un colega te pregunta en el chat del equipo. Recibes lo transcrito (Whisper: puede escribir mal los nombres),
con marcas [hh:mm:ss] y los segundos después de "|". Responde en pocas líneas, como un colega, sin saludos: lo
importante primero (anuncios, cifras, fechas, quién lo dijo), con el minuto y el enlace al video en ese momento
(https://youtu.be/{video}?t=<segundos>). Usa SOLO lo transcrito; si no se ha dicho, dilo. Texto plano, sin asteriscos."""


def de_la_transmision(video, agente, pregunta):
    """Respuesta con la transcripción de una sesión o entrevista (la parcial, si sigue en vivo). None si no hay."""
    from cerebro import ia
    parcial, final = (os.path.join(TRANSCRIPCIONES, f"{video}{x}") for x in (".parcial.txt", ".txt"))
    ruta = parcial if os.path.exists(parcial) else final if os.path.exists(final) else None
    if not ruta:
        return None
    texto = re.sub(r"\[(\d{2}):(\d{2}):(\d{2})\]", lambda m: f"[{m.group(0)[1:-1]}|{int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])}]",
                   open(ruta, encoding="utf-8").read())
    if len(texto) > 90000:  # en vivo lo último importa más: el comienzo y lo más reciente
        texto = texto[:15000] + "\n[…]\n" + texto[-75000:]
    r = ia.generar_json(VIVO.format(nombre=AGENTES[agente][0], video=video,
                                    estado="EN VIVO (lo transcrito llega con unos minutos de atraso)" if ruta == parcial else "ya terminada"),
                        f"TRANSCRIPCIÓN:\n{texto}\n\nPREGUNTA: {pregunta}",
                        {"type": "object", "properties": {"respuesta": {"type": "string"}}, "required": ["respuesta"]})
    return r["respuesta"]


# ---------------------------------------------------------------- atender un mensaje

def atender(destino, chat, mensaje, texto, citado_id=None, citado_texto="", citado_es_bot=False, usuario_bot=None):
    d = dirigido(texto, citado_es_bot, usuario_bot)
    if not d:
        return
    agente, pregunta = d
    nota = anotado(chat, citado_id) if citado_id else None
    ref = nota["ref"] if nota else None
    citado = (nota["texto"] if nota else "") or citado_texto
    if not agente:
        agente = POR_CODIGO.get(nota["agente"]) if nota and nota.get("agente") else POR_BOT.get(destino, "kiwi")
    nombre = AGENTES[agente][0]
    p = sin_tildes(pregunta)
    tipo, _, valor = (ref or "").partition(":")
    escribiendo(destino, chat)
    try:
        if "bola roja" in p or "keyeconomics" in p or "key economics" in p:
            from cerebro import entrevistas, pases
            bola = "bola roja" in p
            if bola and tipo == "entrevista" and d1.consulta("SELECT 1 FROM entrevistas WHERE id = ?", [valor]):
                responder_en(destino, chat, "Diego: la armo con la entrevista completa y se las mando aquí.", mensaje)
                entrevistas.bola(valor)
                return
            fuente = material(ref, citado)
            if not fuente.strip():
                responder_en(destino, chat, f"{nombre}: respóndeme sobre el mensaje del que la quieres (la nota, la norma o la entrevista).", mensaje)
                return
            quien = "Diego" if bola else "Tomás"
            responder_en(destino, chat, f"{quien}: la armo{' y se la mando aquí' if bola else ''}; un minuto.", mensaje)
            titulo = (citado or pregunta).strip().splitlines()[0][:200]
            pases.del_chat("bolaroja" if bola else "keyeconomics", f"PEDIDO DEL EQUIPO: {pregunta}\n\n{fuente}", titulo)
        elif "keylaw" in p and tipo == "sesion":
            import uuid
            d1.consulta("INSERT INTO tareas (id, agente, tipo, ref, estado, detalle, creado) VALUES (?, 'relatora', 'keylaw', ?, "
                        "'pendiente', 'Pedido desde el chat', ?)", [str(uuid.uuid4()), valor, cerebro.ahora()])
            responder_en(destino, chat, "Fernando: lo escribo con la transcripción y aviso aquí cuando esté para revisión.", mensaje)
        elif "transcripci" in p and tipo in ("sesion", "entrevista"):
            donde = "la mesa de Fernando → Historial de sesiones" if tipo == "sesion" else "la mesa de Diego"
            listo = os.path.exists(os.path.join(TRANSCRIPCIONES, f"{valor}.txt"))
            responder_en(destino, chat, f"{nombre}: " + (f"la transcripción está en la oficina, en {donde} (ahí se lee, se copia o se baja)."
                                                       if listo else "esa transcripción todavía no está lista; aviso cuando termine."), mensaje)
        else:
            # sobre una sesión o entrevista (aunque siga en vivo): contesta con su transcripción, que todavía no está
            # en el cerebro de Kiwi mientras dura la transmisión
            respuesta = de_la_transmision(valor, agente, pregunta) if tipo in ("sesion", "entrevista") else None
            if respuesta is None and tipo in ("sesion", "entrevista"):
                respuesta = "todavía no tengo nada transcrito de esa transmisión: el primer trozo llega a los 2 o 3 minutos de empezar."
            if respuesta is None:
                respuesta = kiwi(pregunta, agente, citado)
            responder_en(destino, chat, f"{nombre}: {respuesta}", mensaje, AGENTES[agente][2], ref)
    except Exception as e:
        print(f"chat: {e}", flush=True)
        responder_en(destino, chat, f"{nombre}: no pude responder ahora (la IA puede estar saturada). Prueba en un minuto.", mensaje)


# ---------------------------------------------------------------- escuchar

# ---------------------------------------------------------------- 👍 / 👎

POSITIVAS, NEGATIVAS = {"👍", "❤", "❤️", "🔥", "👏"}, {"👎"}


def reaccion(destino, r, permitidos):
    """El equipo reacciona a un mensaje de un agente (Andrés, 2026-10-26): 👍 (o ❤️ 🔥 👏) = sirvió, 👎 = no lo manden.
    Se guarda en `reacciones` con lo que decía el mensaje (para Paula: medio y titular); quitar la reacción la borra.
    Telegram solo manda las reacciones si el bot es ADMINISTRADOR del grupo."""
    chat = str(r.get("chat", {}).get("id"))
    if chat not in permitidos:
        return
    usuario = str((r.get("user") or {}).get("id") or (r.get("actor_chat") or {}).get("id") or "")
    emojis = {x.get("emoji") for x in r.get("new_reaction") or [] if x.get("type") == "emoji"}
    valor = 1 if emojis & POSITIVAS else -1 if emojis & NEGATIVAS else 0
    try:
        d1.consulta("CREATE TABLE IF NOT EXISTS reacciones (chat TEXT, mensaje INTEGER, usuario TEXT, valor INTEGER, agente TEXT, "
                    "ref TEXT, texto TEXT, creado TEXT, PRIMARY KEY (chat, mensaje, usuario))")
        if not valor:
            d1.consulta("DELETE FROM reacciones WHERE chat = ? AND mensaje = ? AND usuario = ?", [chat, r["message_id"], usuario])
            return
        nota = anotado(chat, r["message_id"]) or {}
        texto = nota.get("texto") or ""
        if (nota.get("ref") or "").startswith("url:"):  # Paula manda solo el enlace: se guarda también medio y titular
            f = d1.consulta("SELECT medio, titulo FROM monitor_vistos WHERE url = ?", [nota["ref"][4:]])
            if f:
                texto = f"[{f[0]['medio']}] {f[0]['titulo']}"
        d1.consulta("INSERT OR REPLACE INTO reacciones VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [chat, r["message_id"], usuario, valor, nota.get("agente"), nota.get("ref"), texto[:1000], cerebro.ahora()])
        print(f"chat {destino}: reacción {'👍' if valor > 0 else '👎'} a {nota.get('agente') or '?'}: {texto[:60]}", flush=True)
    except Exception as e:
        print(f"chat reacción: {e}", flush=True)


def escuchar_bot(destino):
    """getUpdates en espera larga para un bot sin webhook (oficina, Gaceta)."""
    token = token_de(destino)
    bot = _api(token, "getMe")["result"]
    usuario, yo = bot["username"], bot["id"]
    permitidos, offset = chats_permitidos(), None
    while True:
        try:
            r = _api(token, "getUpdates", {"timeout": 30, **({"offset": offset} if offset else {}),
                                           "allowed_updates": json.dumps(["message", "message_reaction"])}, timeout=45)
            for u in r["result"]:
                offset = u["update_id"] + 1
                if u.get("message_reaction"):
                    reaccion(destino, u["message_reaction"], permitidos)
                    continue
                m = u.get("message") or {}
                if str(m.get("chat", {}).get("id")) not in permitidos or not m.get("text") or time.time() - m.get("date", 0) > 600:
                    continue
                c = m.get("reply_to_message") or {}
                threading.Thread(target=atender, daemon=True, args=(
                    destino, m["chat"]["id"], m["message_id"], m["text"], c.get("message_id"), c.get("text") or c.get("caption") or "",
                    (c.get("from") or {}).get("id") == yo, usuario)).start()
        except Exception as e:
            print(f"chat {destino}: {e}", flush=True)
            time.sleep(15)


def escuchar_worker():
    """El bot de la Asamblea tiene el webhook del Worker: lo dirigido a los agentes llega a chat_entrada."""
    permitidos = chats_permitidos()
    while True:
        try:
            for f in d1.consulta("SELECT * FROM chat_entrada WHERE estado = 'nuevo' ORDER BY creado LIMIT 10"):
                d1.consulta("UPDATE chat_entrada SET estado = 'visto' WHERE id = ?", [f["id"]])
                if str(f["chat"]) in permitidos:
                    threading.Thread(target=atender, daemon=True, args=(
                        "asamblea", f["chat"], f["mensaje"], f["texto"], f["citado_id"], f["citado_texto"] or "",
                        bool(f["citado_bot"]), None)).start()
        except Exception as e:
            if "no such table" not in str(e):
                print(f"chat asamblea: {e}", flush=True)
        time.sleep(8)


def escuchar():
    for destino in ("general", "gaceta"):
        if os.environ.get(f"TELEGRAM_{destino.upper()}_TOKEN"):
            threading.Thread(target=escuchar_bot, args=(destino,), daemon=True).start()
    escuchar_worker()


if __name__ == "__main__":
    cerebro.cargar_env()
    print("Escuchando los grupos de Telegram…", flush=True)
    escuchar()
