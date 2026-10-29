"""La mesa de tareas de la Mac de la oficina: hace lo que alguien pide desde la oficina virtual.

Uso (en la Mac, con ~/.venvs/whisper): python cerebro/mesa.py
Cada 20 segundos deja un latido en la base (la oficina muestra "la Mac está encendida") y toma las tareas pendientes:
- relatora/transcribir <enlace o id de YouTube>: sigue la transmisión (en vivo o ya emitida) y escribe el Keylaw.
- perfilador/keyperfil <id de entidad>: arma el expediente y el Keyperfil en PDF.
- vigia/gaceta: la hace Claude con el Chrome de la oficina (la web pide captcha); aquí solo se anota que espera.
Además vigila el canal de la Asamblea y sigue sola cada transmisión en vivo que empiece, y pasa cada edición nueva de
la Gaceta a la Analista normativa (índice de normas y Keymonitor).
"""
import json
import os
import re
import socket
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

EQUIPO = socket.gethostname().split(".")[0]
siguiendo = {}  # video → hilo
titulos = {}    # video → título de la transmisión (la oficina lo muestra)


def latido(detalle):
    d1.ejecutar_varias("CREATE TABLE IF NOT EXISTS latidos (equipo TEXT PRIMARY KEY, momento TEXT, detalle TEXT)")
    d1.consulta("INSERT OR REPLACE INTO latidos (equipo, momento, detalle) VALUES (?, ?, ?)",
                [EQUIPO, time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), detalle])


def marcar(tarea, estado, detalle=None):
    d1.consulta("UPDATE tareas SET estado = ?, detalle = COALESCE(?, detalle), hecho = ? WHERE id = ?",
                [estado, detalle, time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) if estado in ("hecha", "error") else None,
                 tarea])


def id_youtube(ref):
    m = re.search(r"(?:v=|youtu\.be/|live/|shorts/)([\w-]{11})", ref) or re.match(r"^([\w-]{11})$", ref.strip())
    return m.group(1) if m else None


def en_hilo(tarea, funcion, *args):
    def correr():
        try:
            detalle = funcion(*args)
            marcar(tarea["id"], "hecha", detalle or "Listo")
        except SystemExit as e:
            marcar(tarea["id"], "error", str(e)[:300])
        except Exception as e:
            traceback.print_exc()
            marcar(tarea["id"], "error", str(e)[:300])
    h = threading.Thread(target=correr, daemon=True)
    h.start()
    return h


def transcribir(video, keylaw=None):
    from cerebro import en_vivo
    en_vivo.seguir(video, keylaw=keylaw)
    return "Transcripción y Keylaw listos"


def keylaw_pedido(video):
    """Keylaw pedido a mano (oficina o chat): se escribe y el chat de la Asamblea solo avisa que está para revisión."""
    from cerebro import relatora
    r = relatora.relatar(video, True)
    if r and r.get("keylaws"):
        cerebro.telegram("📄 Keylaw listo para revisar en la oficina (mesa de Fernando):\n" +
                         "\n".join("• " + k["asunto"] for k in r["keylaws"]), destino="asamblea", ref=f"sesion:{video}", agente="relatora")
    return "Keylaw listo en borrador"


def keyperfil(entidad):
    from cerebro import perfilador
    e, exp = perfilador.perfilar(entidad)  # solo los datos: el PDF se arma en la oficina al descargarlo
    return f"Keyperfil listo: {exp['nombre']}"


def perfil_nuevo(datos):
    """Perfil pedido a mano desde la oficina: {nombre, cargo, institucion, notas}. Si la persona ya está en el
    directorio se usa esa; si no, se crea. Las notas entran como perfil investigado (lo que el equipo sabe)."""
    nombre = " ".join((datos.get("nombre") or "").split())
    if not nombre:
        raise SystemExit("Falta el nombre")
    personas = d1.consulta("SELECT id, nombre FROM entidades WHERE tipo = 'persona'")
    ids = cerebro.fichas_de_personas(nombre, personas)
    if len(ids) == 1:
        eid = ids[0]
    else:
        eid = "persona:" + cerebro.slug(nombre)
        cargo = ", ".join(x for x in [datos.get("cargo"), datos.get("institucion")] if x)
        cerebro.guardar_entidades([{"id": eid, "tipo": "persona", "subtipo": "otro", "nombre": nombre, "cargo": cargo or None,
                                    "datos": {"institucion": datos.get("institucion")}, "fuente": "manual (oficina)",
                                    "alias": cerebro.alias_de_persona(nombre)}])
        inst = d1.consulta("SELECT id FROM entidades WHERE tipo IN ('institucion', 'comision', 'partido') AND nombre LIKE ? LIMIT 2",
                           [f"%{datos.get('institucion') or '#'}%"])
        if len(inst) == 1:
            cerebro.relacionar([(eid, "pertenece_a", inst[0]["id"], None, cerebro.ahora()[:10], datos.get("cargo"))])
    if (datos.get("notas") or "").strip():
        cerebro.guardar_documento("investigacion_perfil", eid + "|" + cerebro.huella(datos["notas"]),
                                  f"## {nombre}\n\n{datos['notas']}", titulo=f"Perfil de {nombre}", fecha=cerebro.ahora()[:10])
    return keyperfil(eid)


def gaceta_subida(subida, numero):
    """Gaceta subida a mano desde la oficina (por si el Chrome de la oficina no puede traerla): se arma el PDF con sus
    trozos, entra igual que si la hubiera traído el Vigía y se borran los trozos."""
    import base64
    from cerebro import receptor_gaceta
    trozos = d1.consulta("SELECT datos FROM subidas WHERE id = ? ORDER BY n", [subida])
    datos = base64.b64decode("".join(t["datos"] for t in trozos))
    if not datos.startswith(b"%PDF"):
        raise SystemExit("El archivo subido no es un PDF")
    r = receptor_gaceta.guardar(numero, "", datos)
    d1.consulta("DELETE FROM subidas WHERE id = ?", [subida])
    return f"Gaceta {numero.replace('_', '-')} subida: {r}"


def atender():
    for t in d1.consulta("SELECT * FROM tareas WHERE estado = 'pendiente' ORDER BY creado"):
        if t["agente"] == "relatora" and t["tipo"] == "transcribir":
            video = id_youtube(t["ref"] or "")
            if not video:
                marcar(t["id"], "error", "No reconozco ese enlace de YouTube")
            elif video in siguiendo and siguiendo[video].is_alive():
                marcar(t["id"], "hecha", "La Relatora ya está siguiendo esa transmisión")
            else:
                marcar(t["id"], "en curso", "La Relatora está escuchando y transcribiendo")
                siguiendo[video] = en_hilo(t, transcribir, video, {"keylaw": True, "guardar": False}.get(t["detalle"]))
                titulos[video] = video
        elif t["agente"] == "perfilador" and t["tipo"] == "keyperfil":
            marcar(t["id"], "en curso", "El Perfilador está armando la ficha y la Diseñadora el PDF")
            en_hilo(t, keyperfil, t["ref"])
        elif t["agente"] == "relatora" and t["tipo"] == "keylaw":
            from cerebro import relatora
            marcar(t["id"], "en curso", "La Relatora está escribiendo el Keylaw")
            en_hilo(t, keylaw_pedido, t["ref"])
        elif t["agente"] == "vigia" and t["tipo"] == "subida":
            marcar(t["id"], "en curso", "Inés está leyendo la Gaceta subida")
            en_hilo(t, gaceta_subida, t["ref"], t["detalle"])
        elif t["tipo"] in ("keyeconomics_norma", "bola_norma"):  # pases entre agentes (cerebro/pases.py)
            from cerebro import pases
            marcar(t["id"], "en curso", "Tomás está escribiendo el Keyeconomics" if t["agente"] == "cifras"
                   else "Diego está escribiendo la bola roja")
            en_hilo(t, pases.hacer, t["ref"])
        elif t["agente"] == "entrevistas":
            from cerebro import entrevistas
            if t["tipo"] == "bola":
                marcar(t["id"], "en curso", "Diego está escribiendo la bola roja")
                en_hilo(t, entrevistas.bola, t["ref"])
            else:
                video = id_youtube(t["ref"] or "")
                if not video:
                    marcar(t["id"], "error", "No reconozco ese enlace de YouTube")
                elif video in siguiendo and siguiendo[video].is_alive():
                    marcar(t["id"], "hecha", "Ya se está escuchando")
                else:
                    marcar(t["id"], "en curso", "Diego está escuchando la entrevista")
                    siguiendo[video] = en_hilo(t, entrevistas.escuchar, video, None, t["detalle"] == "reporte")
                    titulos[video] = video
        elif t["agente"] == "judicial":
            from cerebro import judicial
            if t["tipo"] == "keymonitor":
                marcar(t["id"], "en curso", "Se están escribiendo los Keymonitor judiciales")
                en_hilo(t, judicial.redactar, [x for x in (t["ref"] or "").split(",") if x])
            else:
                marcar(t["id"], "en curso", "Analizando lo que trajo el Chrome de la oficina")
                en_hilo(t, judicial.procesar)
        elif t["agente"] == "regulatoria":
            from cerebro import reguladores
            if t["tipo"] == "keymonitor":
                marcar(t["id"], "en curso", "Se están escribiendo los Keymonitor de reguladores")
                en_hilo(t, reguladores.redactar, [x for x in (t["ref"] or "").split(",") if x])
            else:
                marcar(t["id"], "en curso", "Revisando los reguladores")
                en_hilo(t, lambda: f"{reguladores.revisar()} publicaciones nuevas")
        elif t["agente"] == "cifras":
            from cerebro import cifras
            if t["tipo"] == "keyeconomics":
                marcar(t["id"], "en curso", "Tomás está escribiendo el Keyeconomics")
                en_hilo(t, cifras.redactar_id, t["ref"])
            else:
                marcar(t["id"], "en curso", "Revisando el INEC")
                en_hilo(t, cifras.revisar)
        elif t["agente"] == "perfilador" and t["tipo"] == "nuevo":
            datos = json.loads(t["detalle"] or "{}")
            marcar(t["id"], "en curso", f"El Perfilador está armando el perfil de {datos.get('nombre', '')}")
            en_hilo(t, perfil_nuevo, datos)
        elif t["agente"] == "normativa" and t["tipo"] == "keymonitor":
            from cerebro import normativa
            marcar(t["id"], "en curso", "La Analista está escribiendo los Keymonitor elegidos")
            en_hilo(t, normativa.redactar, [x for x in (t["ref"] or "").split(",") if x])
        elif t["agente"] == "vigia" and t["tipo"] == "gaceta":
            marcar(t["id"], "en espera", "La traerá la próxima revisión con el Chrome de la oficina")


def leer_gacetas():
    from cerebro import normativa
    while True:
        try:
            for numero, doc in normativa.pendientes():
                latido(f"La Analista normativa está leyendo la Gaceta {numero.replace('_', '-')}")
                normativa.leer(numero, doc)
        except Exception as e:
            traceback.print_exc()
            print(f"leer gacetas: {e}", flush=True)
        time.sleep(300)


def revisar_reguladores():
    """Entes Reguladores: cada 3 horas, de 7:00 a 21:00 (hora de la Mac)."""
    from cerebro import reguladores
    while True:
        if 7 <= time.localtime().tm_hour < 21:
            try:
                latido("Revisando los reguladores")
                print(f"reguladores: {reguladores.revisar()} nuevos", flush=True)
            except Exception as e:
                print(f"reguladores: {e}", flush=True)
        time.sleep(3 * 3600)


def revisar_cifras():
    """Tomás · Cifras: cada hora, de lunes a viernes de 8:00 a 18:00 (el INEC y la Secretaría de Energía publican en
    horario de oficina)."""
    from cerebro import cifras, combustibles
    while True:
        h = time.localtime()
        if h.tm_wday < 5 and 8 <= h.tm_hour < 18:
            try:
                latido("Revisando el INEC")
                print(f"cifras: {cifras.revisar()}", flush=True)
            except Exception as e:
                print(f"cifras: {e}", flush=True)
            try:
                print(f"combustibles: {combustibles.revisar()}", flush=True)
            except Exception as e:
                print(f"combustibles: {e}", flush=True)
        time.sleep(3600)


def revisar_judicial():
    """Órgano Judicial: cada 5 minutos analiza lo que la extensión del Chrome de la oficina trajo de la web de la Corte
    (edictos del Pleno y comunicados) y avisa por Telegram las decisiones importantes."""
    from cerebro import judicial
    while True:
        try:
            if d1.consulta("SELECT 1 FROM documentos WHERE fuente IN ('oj_edicto', 'oj_comunicado') AND id NOT IN "
                           "(SELECT documento FROM judicial_procesados) LIMIT 1"):
                print(f"judicial: {judicial.procesar()}", flush=True)
        except Exception as e:
            print(f"judicial: {e}", flush=True)
        time.sleep(300)


def escuchar_noticieros():
    """Diego: durante cada franja de los noticieros (TVN, Telemetro, SERTV, Radio Panamá) busca su transmisión en vivo
    y la escucha hasta el fin de la franja; si no se dijo nada importante, no queda nada guardado."""
    from cerebro import entrevistas
    escuchados = set()
    while True:
        try:
            for medio, canal, segundos, clave in entrevistas.franjas_abiertas(time.localtime()):
                if clave in escuchados:
                    continue
                vivo = entrevistas.en_vivo_en(canal)
                if not vivo or vivo[0] in siguiendo:
                    continue
                escuchados.add(clave)
                video, titulo = vivo
                print(f"noticiero: {medio} · {titulo} ({video}), {segundos // 60} min", flush=True)
                h = threading.Thread(target=entrevistas.escuchar, args=(video, titulo, False, "noticiero", segundos, medio), daemon=True)
                h.start()
                siguiendo[video] = h
                titulos[video] = medio
        except Exception as e:
            print(f"noticieros: {e}", flush=True)
        time.sleep(180)


def escuchar_anunciadas():
    """Diego: las entrevistas anunciadas en X que hay que seguir (las de quienes seguimos, solas; las demás, si alguien
    marcó "Seguir" en la oficina). Cada 3 minutos, hasta 6 horas después del anuncio, busca la transmisión en vivo en
    el canal de YouTube del medio y la escucha (máximo 90 minutos)."""
    from cerebro import entrevistas, redes
    while True:
        try:
            redes.crear_tabla()
            for f in d1.consulta("SELECT * FROM medios_agenda WHERE seguir = 1 AND fecha >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-11 hours')"):
                canal = redes.canal_de(f)
                vivo = entrevistas.en_vivo_en(canal) if canal else None
                if not vivo:
                    continue
                video, titulo = vivo
                d1.consulta("UPDATE medios_agenda SET seguir = 2, video = ? WHERE id = ?", [video, f["id"]])
                if video in siguiendo:  # ya lo escucha otro (p. ej. el noticiero de la franja)
                    continue
                nombre = f"{f['quien']} · {f['programa'] or f['medio']}"
                print(f"entrevista anunciada: {nombre} ({video})", flush=True)
                h = threading.Thread(target=entrevistas.escuchar, args=(video, f"{nombre}: {titulo}", False, "entrevista", 90 * 60,
                                                                       f["medio"]), daemon=True)
                h.start()
                siguiendo[video] = h
                titulos[video] = nombre
            d1.consulta("UPDATE medios_agenda SET seguir = 3 WHERE seguir = 1 AND fecha < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-11 hours')")
        except Exception as e:
            print(f"anunciadas: {e}", flush=True)
        time.sleep(180)


def agenda_de_x():
    """La agenda del día que la Asamblea publica en X (imágenes): cada 5 minutos lee lo nuevo y vuelve a poner en la
    agenda lo que la web no trae (prensa.py reescribe cada hora las filas de la web). Ver cerebro/agenda_x.py."""
    from cerebro import agenda_x
    while True:
        try:
            r = agenda_x.revisar()
            if not r.startswith("0 sesiones leídas, 0"):
                print(f"agenda x: {r}", flush=True)
        except Exception as e:
            print(f"agenda x: {e}", flush=True)
        time.sleep(300)


def pasar_vectores():
    """Búsqueda por significado: cada 10 minutos los trozos nuevos del cerebro van a Vectorize (cerebro/vectores.py)."""
    from cerebro import vectores
    while True:
        try:
            r = vectores.pasar()
            if not r.startswith("0 "):
                print(f"vectores: {r}", flush=True)
        except Exception as e:
            print(f"vectores: {e}", flush=True)
        time.sleep(600)


def monitorear_medios():
    """Paula: cada 15 minutos, de 6:00 a 22:00, manda al chat el enlace de las noticias importantes."""
    from cerebro import monitor
    while True:
        if 6 <= time.localtime().tm_hour < 22:
            try:
                r = monitor.revisar()
                if not r.endswith(" 0 enviados al chat"):
                    print(f"monitor: {r}", flush=True)
            except Exception as e:
                print(f"monitor: {e}", flush=True)
        time.sleep(900)


def limpiar_pdf():
    """Los PDF son de paso (Andrés, 2026-10-25): las normas partidas, las ediciones de la Gaceta y los Keyperfil se
    borran a los 7 días, en la Mac y en Drive (Drive los deja en su papelera). Quedan los textos en el cerebro."""
    import agente
    while True:
        try:
            limite = time.time() - 7 * 86400
            for base in ("gaceta", "keyperfil"):
                for raiz, _, archivos in os.walk(os.path.join(cerebro.CARPETA, "salidas", base)):
                    for f in archivos:
                        ruta = os.path.join(raiz, f)
                        if f.endswith((".pdf", ".html")) and os.path.getmtime(ruta) < limite:
                            os.remove(ruta)
            if agente.drive_disponible():
                for carpeta in ("Gaceta Oficial", "Keyperfil"):
                    agente.rclone("delete", "--min-age", "7d", agente.drive_ruta(carpeta))
                    agente.rclone("rmdirs", "--leave-root", agente.drive_ruta(carpeta))
            d1.consulta("UPDATE normas SET pdf = NULL WHERE pdf IS NOT NULL AND fecha < date('now', '-7 days')")
        except Exception as e:
            print(f"limpiar pdf: {e}", flush=True)
        time.sleep(86400)


def vigilar_canal():
    from cerebro import en_vivo
    while True:
        try:
            lista = en_vivo.canal()
            if lista:
                en_vivo.anotar_canal(lista)
            for video, titulo in en_vivo.en_vivo_ahora(lista):
                if video not in siguiendo:
                    print(f"en vivo: {titulo} ({video})", flush=True)
                    h = threading.Thread(target=en_vivo.seguir, args=(video, titulo), daemon=True)
                    h.start()
                    siguiendo[video] = h
                    titulos[video] = titulo
        except Exception as e:
            print(f"vigilar canal: {e}", flush=True)
        time.sleep(180)


if __name__ == "__main__":
    cerebro.cargar_env()
    print(f"Mesa de tareas en {EQUIPO}", flush=True)
    threading.Thread(target=vigilar_canal, daemon=True).start()
    threading.Thread(target=leer_gacetas, daemon=True).start()
    threading.Thread(target=limpiar_pdf, daemon=True).start()
    threading.Thread(target=revisar_reguladores, daemon=True).start()
    threading.Thread(target=revisar_judicial, daemon=True).start()
    threading.Thread(target=revisar_cifras, daemon=True).start()
    threading.Thread(target=monitorear_medios, daemon=True).start()
    threading.Thread(target=escuchar_noticieros, daemon=True).start()
    threading.Thread(target=escuchar_anunciadas, daemon=True).start()
    threading.Thread(target=pasar_vectores, daemon=True).start()
    threading.Thread(target=agenda_de_x, daemon=True).start()
    from cerebro import chat
    threading.Thread(target=chat.escuchar, daemon=True).start()  # chat de doble vía en los grupos de Telegram
    while True:
        try:
            activos = [v for v, h in siguiendo.items() if h.is_alive()]
            latido("En vivo: " + " · ".join(titulos.get(v, v).title() for v in activos) if activos
                   else "Atenta a la oficina y al canal de la Asamblea")
            atender()
        except Exception as e:
            print(f"mesa: {e}", flush=True)
        time.sleep(20)
