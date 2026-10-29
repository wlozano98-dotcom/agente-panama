"""Entrevistas y medios (Diego): escucha entrevistas de autoridades y noticieros, avisa lo fuerte mientras ocurre y
escribe la "bola roja" de Keyword (🔴 NUEVA ENTREVISTA AL…).

Uso (en la Mac, con ~/.venvs/whisper):
  python cerebro/entrevistas.py escuchar <enlace o id de YouTube> [--reporte]
  python cerebro/entrevistas.py --bola <id>        (escribe la bola roja de una entrevista ya escuchada)
Escucha con el mismo oído de la Relatora (cerebro/en_vivo.py: audio en trozos, Whisper en la Mac, el audio se borra) y
cada 15 minutos Gemini avisa por Telegram si una autoridad dijo algo fuerte. Al terminar: lo que dijo cada autoridad va
a `declaraciones` (alimenta su perfil, "En entrevistas y medios"), la entrevista a `entrevistas` y, si se pidió, la bola
roja a `productos` (tipo bolaroja) para revisar en la oficina. Los noticieros (tipo "noticiero") solo se guardan si se
dijo algo importante; si no, se borran (Andrés, 2026-10-25: no llenarse de información).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from cerebro.normativa import SECTORES  # noqa: E402
from db import d1  # noqa: E402

SALIDA = os.path.join(cerebro.CARPETA, "salidas", "transcripciones")

AVISO = """Eres Diego, de Keyword (consultora de asuntos públicos en Panamá), y escuchas EN VIVO una entrevista o un
noticiero. Recibes los últimos minutos transcritos, el resumen previo y lo que ya avisaste. Decide si una autoridad (Presidente,
ministro, diputado, director de una entidad) dijo algo que un cliente empresarial deba saber YA: un anuncio, una
cifra, una fecha, una medida, un cambio de postura. Si no, o si ya lo avisaste, importante=false. Si sí, escribe el aviso en una o dos
oraciones, neutral, con el nombre de quien lo dijo solo si se escucha con claridad."""
ESQUEMA_AVISO = {"type": "object", "properties": {
    "importante": {"type": "boolean"}, "aviso": {"type": "string"},
    "resumen": {"type": "string", "description": "Resumen acumulado hasta ahora, en 5 a 10 líneas"}},
    "required": ["importante", "aviso", "resumen"]}

ANALISIS = """Eres Diego, de Keyword. Recibes la transcripción (Whisper, puede tener errores en nombres) de una entrevista
o de un noticiero de Panamá. Devuelve:
- quien: la autoridad entrevistada con su cargo (p. ej. "el ministro de Economía, Felipe Chapman"); vacío si no hay una.
- titulo_bola: el título de la bola roja en mayúsculas, como en los ejemplos ("NUEVA ENTREVISTA AL MINISTRO DE ...").
- importante: si se dijo algo que un cliente empresarial deba saber (anuncios, cifras, medidas, fechas, posturas).
- resumen: 3 a 6 líneas neutrales.
- temas: cada tema relevante con su contenido (lo que dijo, con cifras y, si aporta, una cita textual breve).
- declaraciones: lo que dijo cada autoridad identificable (nombre como se escucha, tema, cita textual corta, postura).
Solo lo que está en la transcripción; nada inventado."""
ESQUEMA = {"type": "object", "properties": {
    "quien": {"type": "string"}, "titulo_bola": {"type": "string"}, "importante": {"type": "boolean"},
    "resumen": {"type": "string"},
    "sectores": {"type": "array", "items": {"type": "string", "enum": SECTORES}},
    "temas": {"type": "array", "items": {"type": "object", "properties": {
        "tema": {"type": "string"}, "contenido": {"type": "string"}}, "required": ["tema", "contenido"]}},
    "declaraciones": {"type": "array", "items": {"type": "object", "properties": {
        "nombre": {"type": "string"}, "tema": {"type": "string"}, "cita": {"type": "string"},
        "postura": {"type": "string", "enum": ["a favor", "en contra", "neutral"]}},
        "required": ["nombre", "tema", "cita", "postura"]}}},
    "required": ["quien", "titulo_bola", "importante", "resumen", "sectores", "temas", "declaraciones"]}

BOLA = """Eres Diego, de Keyword, consultora de asuntos públicos en Panamá. Escribe la "bola roja": el correo corto que
Keyword manda a sus clientes apenas una autoridad da una entrevista. Forma exacta de los ejemplos reales que siguen:
primera línea "🔴 " + título en mayúsculas; luego, por cada tema relevante, una viñeta "•  <Tema>: <qué dijo>", con
cifras, fechas y, cuando aporta, una cita textual entre comillas; al final "Saludos cordiales." Registro ejecutivo,
neutral, tercera persona, sin adjetivos de opinión. Solo lo que está en la transcripción; si un nombre no se entiende
bien, usa el cargo. Devuelve el asunto (el título sin el emoji) y el cuerpo completo."""
ESQUEMA_BOLA = {"type": "object", "properties": {"asunto": {"type": "string"}, "cuerpo": {"type": "string"}},
                "required": ["asunto", "cuerpo"]}


# Noticieros que transmiten en vivo por YouTube (investigación de ChatGPT, Invesitgacion/…report-3 6.md; confianza
# alta). (medio, canal /streams, [(días 0=lunes, hora inicio, hora fin)]). Se escucha solo la franja; si no se dijo
# nada importante, no queda nada guardado.
LV = range(0, 5)
NOTICIEROS = [
    ("TVN Noticias", "https://www.youtube.com/@TVNNoticiasYT/streams", [(LV, "06:00", "08:00"), (LV, "12:00", "13:00"), (LV, "18:00", "20:00")]),
    ("Telemetro Reporta", "https://www.youtube.com/@telemetropa/streams", [(LV, "06:00", "08:00"), (LV, "12:00", "13:10"), (LV, "18:00", "20:00")]),
    ("SERTV Noticias", "https://www.youtube.com/@SertvNoticias/streams", [(LV, "06:05", "08:00"), (LV, "18:00", "20:00")]),
    ("Radio Panamá · Panamá Hoy", "https://www.youtube.com/@RadioPanama945/streams", [(LV, "06:00", "09:00")]),
]


def en_vivo_en(canal):
    """El primer video en vivo de un canal (id, título) o None."""
    import subprocess
    from cerebro import transcribir
    r = subprocess.run([transcribir.UVX, "--python", "3.12", "yt-dlp@latest", "--flat-playlist", "--playlist-end", "5",
                        "--print", "%(id)s\t%(live_status)s\t%(title)s", canal], capture_output=True, text=True)
    for linea in r.stdout.splitlines():
        partes = linea.split("\t")
        if len(partes) == 3 and partes[1] == "is_live":
            return partes[0], partes[2]
    return None


def franjas_abiertas(ahora):
    """[(medio, canal, segundos que quedan, clave)] de los noticieros cuya franja está en curso (hora de la Mac)."""
    out = []
    for medio, canal, franjas in NOTICIEROS:
        for dias, ini, fin in franjas:
            h0, m0 = map(int, ini.split(":")); h1, m1 = map(int, fin.split(":"))
            desde, hasta, minuto = h0 * 60 + m0, h1 * 60 + m1, ahora.tm_hour * 60 + ahora.tm_min
            if ahora.tm_wday in dias and desde <= minuto < hasta - 10:
                out.append((medio, canal, (hasta - minuto) * 60, f"{medio}|{ini}|{ahora.tm_year}-{ahora.tm_yday}"))
    return out


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS entrevistas (id TEXT PRIMARY KEY, tipo TEXT, titulo TEXT, medio TEXT, url TEXT, "
                "fecha TEXT, quien TEXT, resumen TEXT, temas TEXT, sectores TEXT, importante INTEGER, producto TEXT, "
                "documento TEXT, creado TEXT)")


def escuchar(video, titulo=None, reporte=False, tipo="entrevista", limite=None, medio=None):
    """Escucha (en vivo o ya emitido) y al terminar analiza; devuelve un texto para la tarea de la oficina."""
    from cerebro import en_vivo
    r = en_vivo.seguir(video, titulo, limite=limite, aviso=AVISO, anuncio=(tipo == "entrevista"),
                       al_terminar=lambda v, info: cerrar(v, info, reporte, tipo, medio))
    return r or "No se grabó audio"


def cerrar(video, info, reporte, tipo, medio):
    crear_tabla()
    ruta = os.path.join(SALIDA, f"{video}.txt")
    texto = open(ruta, encoding="utf-8").read()
    r = ia.generar_json(ANALISIS, f"{info['titulo']} ({info.get('fecha') or ''})\n\n{texto[:120000]}", ESQUEMA)
    if tipo == "noticiero" and not r["importante"]:
        # no se dijo nada importante: no se guarda nada (ni la transcripción)
        for ext in (".txt", ".json"):
            if os.path.exists(os.path.join(SALIDA, video + ext)):
                os.remove(os.path.join(SALIDA, video + ext))
        return f"{info['titulo']}: sin nada importante, no se guardó"
    doc, _ = cerebro.guardar_documento("entrevista", video, texto, tipo=tipo, titulo=info["titulo"], url=info["url"],
                                       fecha=info.get("fecha"), resumen=r["resumen"])
    cerebro.enlazar()
    # lo que dijo cada autoridad, a su perfil (como las declaraciones de la Asamblea)
    alias = cerebro.cargar_alias()
    filas = []
    for x in r["declaraciones"]:
        actores = [e for e in cerebro.menciones_en(x["nombre"], alias) if e.startswith("persona:")]
        if len(actores) == 1:
            filas.append([cerebro.huella(doc, actores[0], x["cita"]), actores[0], doc, info.get("fecha") or cerebro.ahora()[:10],
                          x["tema"], x["cita"], x["postura"], cerebro.ahora()])
    d1.insertar_muchas("declaraciones", ["id", "entidad", "documento", "fecha", "tema", "cita", "postura", "creado"], filas)
    d1.insertar_muchas("entrevistas", ["id", "tipo", "titulo", "medio", "url", "fecha", "quien", "resumen", "temas", "sectores",
                                       "importante", "documento", "creado"],
                       [[video, tipo, info["titulo"], medio or info.get("canal") or "", info["url"], info.get("fecha"),
                         r["quien"], r["resumen"], json.dumps(r["temas"], ensure_ascii=False),
                         json.dumps(r["sectores"], ensure_ascii=False), 1 if r["importante"] else 0, doc, cerebro.ahora()]])
    hecho = f"{info['titulo']}: {len(r['temas'])} temas, {len(filas)} declaraciones a perfiles"
    if reporte:
        hecho += " · " + bola(video)
    elif tipo == "entrevista":
        cerebro.telegram(f"🗂 Entrevista escuchada: {info['titulo']}\n{r['resumen'][:600]}\n"
                         "Si quieren la bola roja, respondan a este mensaje («bola roja»).", destino="general",
                         ref=f"entrevista:{video}", agente="entrevistas")
    return hecho


def bola(video):
    """Escribe la bola roja de una entrevista ya escuchada y la manda DIRECTO al chat (Andrés, 2026-10-25); queda en la
    oficina como enviada, por si hay que corregirla."""
    crear_tabla()
    e = d1.consulta("SELECT * FROM entrevistas WHERE id = ?", [video])
    if not e:
        raise SystemExit("Esa entrevista no está escuchada todavía")
    e = e[0]
    from cerebro import anuncios
    texto = cerebro.texto_documento(e["documento"])
    previos = anuncios.como_texto(anuncios.de_actor(e["quien"] or e["titulo"]))
    r = ia.generar_json(BOLA + cerebro.ejemplos("BolaRoja", 4) +
                        "\nSi algo ya estaba en los ANUNCIOS PREVIOS, puedes marcarlo \"(ya anunciado el <día>)\".",
                        f"Entrevistado: {e['quien'] or '(identificar en la transcripción)'}\nTítulo sugerido: {e['titulo']}\n"
                        f"Temas detectados: {e['temas']}\n\nANUNCIOS PREVIOS:\n{previos}\n\nTranscripción:\n{texto[:100000]}", ESQUEMA_BOLA)
    pid = cerebro.huella("bolaroja", video)
    asunto = re.sub(r"^🔴\s*", "", r["asunto"]).strip()
    # sale directo al chat: antes Kiwi la revisa contra la transcripción (quita lo que no está y arregla el formato)
    cuerpo = editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente", "fuentes",
                              "creado", "actualizado"],
                             [[pid, "bolaroja", "🔴 " + asunto, None, r["cuerpo"], e["url"], "enviado", "entrevistas",
                               json.dumps([e["documento"]]), cerebro.ahora(), cerebro.ahora()]])[pid]
    d1.consulta("UPDATE entrevistas SET producto = ? WHERE id = ?", [pid, video])
    titulo_bola = "" if cuerpo.lstrip().startswith("🔴") else f"🔴 {asunto}\n\n"
    cerebro.telegram(f"{titulo_bola}{cuerpo}\n\n{e['url']}", destino="general", ref=f"entrevista:{video}", agente="entrevistas")
    return "bola roja enviada al chat"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "escuchar":
        from cerebro.mesa import id_youtube
        print(escuchar(id_youtube(sys.argv[2]) or sys.argv[2], reporte="--reporte" in sys.argv))
    elif len(sys.argv) > 2 and sys.argv[1] == "--bola":
        print(bola(sys.argv[2]))
