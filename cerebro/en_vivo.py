"""Sesiones en vivo: la Relatora sigue las transmisiones de la Asamblea mientras ocurren.

Uso (en la Mac, con ~/.venvs/whisper):
  python cerebro/en_vivo.py vigilar          revisa el canal cada 3 minutos y sigue cada sesión que empiece
  python cerebro/en_vivo.py seguir <id>      sigue una transmisión concreta (o un video ya emitido, para probar)

Por cada sesión: ffmpeg graba el audio en trozos de 2 minutos (el audio se borra al transcribirlo), Whisper transcribe
cada trozo al cerrarse, Gemini revisa cada trozo nuevo (con el anterior, por si una frase quedó partida) y avisa por
Telegram si pasó algo importante (votación, proyecto de impacto, ministro o invitado relevante) con el minuto del video;
antes de mandarlo, la memoria de anuncios (cerebro/anuncios.py) quita lo que ya se había avisado. Al terminar la
transmisión la Relatora escribe el Keylaw. (Andrés, 2026-10-26: de 5 a 2 minutos, para que lo fuerte llegue ya.)
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import re
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import transcribir  # noqa: E402
from db.d1 import consulta as d1_consulta  # noqa: E402

CANAL = "https://www.youtube.com/@AsambleaNacional507/streams"
TROZO = 120                 # segundos de cada trozo de audio
VENTANA = 2                 # trozos que ve cada revisión en caliente: el nuevo y el anterior (4 minutos)
SALIDA = os.path.join(cerebro.CARPETA, "salidas", "transcripciones")
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")

AVISO = """Eres la Relatora de Keyword y sigues EN VIVO una sesión de la Asamblea Nacional de Panamá. Recibes los
últimos minutos transcritos (Whisper), lo dicho antes en resumen y lo que ya avisaste en esta sesión. Decide si pasó algo que un cliente empresarial
deba saber YA: una votación o aprobación, un cambio a un proyecto de impacto, una declaración fuerte de un ministro o
de quien preside, un anuncio de fecha. Si no pasó nada así, o si ya lo avisaste, devuelve importante=false. Si sí,
escribe el aviso en dos o tres oraciones, neutral, sin adjetivos de opinión, con nombres solo si se escuchan con
claridad."""
ESQUEMA_AVISO = {"type": "object", "properties": {
    "importante": {"type": "boolean"}, "aviso": {"type": "string"},
    "momento": {"type": "string", "description": "hh:mm:ss de la transcripción donde empieza lo que se avisa"},
    "resumen": {"type": "string", "description": "Resumen acumulado de la sesión hasta ahora, en 5 a 10 líneas"}},
    "required": ["importante", "aviso", "momento", "resumen"]}


def canal():
    """[(id, estado, título)] de las últimas 8 transmisiones del canal (is_live, is_upcoming, was_live…)."""
    r = subprocess.run([transcribir.UVX, "--python", "3.12", "yt-dlp@latest", "--flat-playlist", "--playlist-end", "8",
                        "--print", "%(id)s\t%(live_status)s\t%(title)s", CANAL], capture_output=True, text=True)
    return [tuple(l.split("\t")) for l in r.stdout.splitlines() if len(l.split("\t")) == 3]


def en_vivo_ahora(lista=None):
    """[(id, título)] de las transmisiones que están en vivo en el canal."""
    return [(v, t) for v, e, t in (canal() if lista is None else lista) if e == "is_live"]


def anotar_canal(lista, previo=[None]):
    """Deja en D1 (config "canal_asamblea") las transmisiones en vivo y programadas, para que la oficina enlace cada
    sesión de hoy con su video (botón «Ver sesión»). Solo escribe cuando cambia."""
    vivas = [{"id": v, "estado": e, "titulo": t} for v, e, t in lista if e in ("is_live", "is_upcoming")]
    if vivas == previo[0]:
        return
    d1_consulta("INSERT OR REPLACE INTO config (clave, valor, actualizado) VALUES ('canal_asamblea', ?, datetime('now'))",
                [json.dumps(vivas, ensure_ascii=False)])
    previo[0] = vivas


telegram = cerebro.telegram


def hls_en_vivo(video):
    """La lista HLS de solo audio si la transmisión está EN VIVO; None si es un video ya emitido."""
    r = subprocess.run([transcribir.UVX, "--python", "3.12", "yt-dlp@latest", "-f", "233/234/bestaudio", "-g", "--", video],
                       capture_output=True, text=True)
    u = (r.stdout.strip().splitlines() or [""])[-1]
    return u if "hls_playlist" in u or ".m3u8" in u else None


def horas_de_trozos(lista):
    """{dirección del trozo: hora (epoch)} según #EXT-X-PROGRAM-DATE-TIME y las duraciones #EXTINF."""
    import datetime
    horas, t, dur = {}, None, 0.0
    for l in lista.splitlines():
        if l.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            t = datetime.datetime.fromisoformat(l.split(":", 1)[1].replace("Z", "+00:00")).timestamp()
        elif l.startswith("#EXTINF:"):
            dur = float(l[8:].split(",")[0] or 0)
        elif l and not l.startswith("#") and t is not None:
            horas[l] = t
            t += dur
    return horas


def alimentar_hls(video, lista, salida, estado=None, inicio=None, desde=None):
    """Baja con urllib los trozos (.ts) nuevos de la lista HLS y se los pasa a ffmpeg. Hace falta porque el ffmpeg de
    la Mac no valida el TLS de YouTube ("certificate verify failed", 2026-10-26: la Relatora no grabó la Línea 3).
    Empieza en el segundo `desde` del video (lo que falta transcribir tras un reinicio; 0 = desde el comienzo) hasta
    donde alcance la hora que YouTube guarda; sin `desde`, por el último minuto. Termina con #EXT-X-ENDLIST, con 3
    minutos sin trozos nuevos o si ffmpeg se cierra.
    estado["desfase"] = en qué segundo del video empieza lo que escuchamos (hora del primer trozo, por
    #EXT-X-PROGRAM-DATE-TIME, menos el comienzo de la transmisión): así los minutos de avisos, chat y Keylaw calzan con
    el video aunque la mesa se haya reiniciado a mitad de la sesión."""
    vistos, primera, quieto = set(), True, 0
    try:
        while True:
            try:
                texto = urllib.request.urlopen(lista, timeout=30).read().decode()
            except urllib.error.HTTPError:  # la dirección vence: se pide otra
                lista = hls_en_vivo(video)
                if not lista:
                    break
                continue
            # cada trozo se reconoce por su número de secuencia (/sq/N/): la dirección cambia al renovar la lista
            trozos = [((re.search(r"/sq/(\d+)/", l) or [None, l])[1], l) for l in texto.splitlines() if l and not l.startswith("#")]
            if primera:
                horas = horas_de_trozos(texto)
                if desde is not None and inicio:
                    # recuperar lo que falta: desde ese segundo del video (o lo más viejo que guarde YouTube)
                    saltar = [n for n, l in trozos if horas.get(l, 0) < inicio + desde - 3]
                    vistos.update(saltar if len(saltar) < len(trozos) else [n for n, _ in trozos[:-12]])
                else:
                    vistos.update(n for n, _ in trozos[:-12])  # ~1 minuto antes de empezar a escuchar
                primera = False
                primero = next((l for n, l in trozos if n not in vistos), None)
                if estado is not None and inicio and primero and horas.get(primero):
                    estado["desfase"] = max(0, round(horas[primero] - inicio))
            nuevos = [(n, l) for n, l in trozos if n not in vistos]
            for n, l in nuevos:
                salida.write(urllib.request.urlopen(l, timeout=60).read())
                salida.flush()
                vistos.add(n)
            if "#EXT-X-ENDLIST" in texto:
                break
            quieto = 0 if nuevos else quieto + 1
            if quieto * 5 > 180:
                break
            time.sleep(5)
    except (BrokenPipeError, OSError) as e:
        print(f"  hls: {e}", flush=True)  # ffmpeg terminó (límite de tiempo) o se cortó la red
    finally:
        try:
            salida.close()
        except OSError:
            pass


def seguir(video, titulo=None, limite=None, keylaw=None, aviso=None, al_terminar=None, anuncio=True):
    """Graba, transcribe y vigila una transmisión hasta que termine (limite: segundos, para pruebas o para escuchar
    solo una franja de un noticiero). Sirve para la Asamblea (por defecto: aviso de la Relatora y Keylaw al terminar)
    y para entrevistas y noticieros (cerebro/entrevistas.py pasa su propio aviso y lo que se hace al terminar)."""
    from cerebro import ia, relatora
    info = transcribir.datos_video(video)
    titulo = titulo or info["titulo"]
    carpeta = os.path.join(SALIDA, f"{video}_vivo")
    os.makedirs(carpeta, exist_ok=True)
    print(f"siguiendo {titulo} ({video})", flush=True)
    avisada = anuncio  # se avisa "En vivo": si después no se graba nada, hay que decirlo
    if anuncio:
        try:  # si la mesa se reinició en medio de la transmisión, el "En vivo" ya salió: no se repite
            ya = d1_consulta("SELECT 1 FROM chat_mensajes WHERE ref = ? AND creado >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-17 hours')",
                             [f"{'entrevista' if al_terminar else 'sesion'}:{video}"])
        except Exception:
            ya = []
        anuncio = not ya
    if anuncio:
        # sesiones de la Asamblea → bot de la Asamblea; entrevistas y noticieros (al_terminar) → grupo de la oficina
        telegram(f"🔴 En vivo: {titulo.title()}\n{'La Relatora está siguiendo la sesión.' if not al_terminar else 'Se está escuchando.'} {info['url']}",
                 destino="general" if al_terminar else "asamblea", ref=f"{'entrevista' if al_terminar else 'sesion'}:{video}",
                 agente="entrevistas" if al_terminar else "relatora")
    # yt-dlp baja el audio (maneja bien TLS y las transmisiones en vivo) y ffmpeg lo corta en trozos de 2 minutos
    # en vivo: Python baja la lista HLS (ver alimentar_hls); video ya emitido: yt-dlp baja el audio directo
    lista = hls_en_vivo(video)
    for viejo in glob.glob(os.path.join(carpeta, "trozo*.m4a")):  # audio de una vuelta anterior (la mesa se reinició)
        os.remove(viejo)
    # lo ya transcrito de esta transmisión antes de un reinicio se conserva, y se sigue desde donde quedó
    previos, ruta_parcial = [], os.path.join(SALIDA, f"{video}.parcial.txt")
    if lista and os.path.exists(ruta_parcial):
        for linea in open(ruta_parcial, encoding="utf-8").read().splitlines():
            m = re.match(r"^\[(\d+):(\d{2}):(\d{2})\] (.*)$", linea)
            if m:
                ini = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
                previos.append({"ini": ini, "fin": ini, "texto": m[4]})
        previos.sort(key=lambda x: x["ini"])
    bajada = None if lista else subprocess.Popen([transcribir.UVX, "--python", "3.12", "yt-dlp@latest", "-q", "--no-part",
                                                  "-f", "bestaudio/best", "-o", "-", "--", video], stdout=subprocess.PIPE)
    orden = [FFMPEG, "-loglevel", "error", "-i", "pipe:0", "-vn", "-c:a", "aac", "-b:a", "64k",
             "-f", "segment", "-segment_time", str(TROZO), os.path.join(carpeta, "trozo%04d.m4a")]
    if limite:
        orden[orden.index("-vn"):orden.index("-vn")] = ["-t", str(limite)]
    grabador = subprocess.Popen(orden, stdin=subprocess.PIPE if lista else bajada.stdout)
    desfase = {"desfase": 0}  # segundo del video donde empieza lo grabado (en vivo; ver alimentar_hls)
    if lista:
        threading.Thread(target=alimentar_hls, args=(video, lista, grabador.stdin, desfase, info.get("inicio"),
                                                     previos[-1]["fin"] + 1 if previos else 0), daemon=True).start()
    else:
        bajada.stdout.close()  # si ffmpeg termina, yt-dlp recibe la señal y también se detiene
    segmentos, hechos, resumen, avisados = previos, set(), "", []

    def pendientes(todos):
        trozos = sorted(glob.glob(os.path.join(carpeta, "trozo*.m4a")))
        listos = trozos if todos else trozos[:-1]  # el último sigue grabándose
        return [t for t in listos if t not in hechos]

    while True:
        terminado = grabador.poll() is not None
        for t in pendientes(terminado):
            n = int(os.path.basename(t)[5:9])
            try:
                partes = transcribir.transcribir(t)
            except Exception as e:  # un trozo dañado se salta: nunca detiene la transmisión (2026-10-26)
                print(f"  trozo {n} dañado, se salta: {str(e)[:120]}", flush=True)
                partes = []
            for s in partes:
                base = n * TROZO + desfase["desfase"]
                segmentos.append({"ini": round(s["ini"] + base, 1), "fin": round(s["fin"] + base, 1),
                                  "texto": s["texto"]})
            hechos.add(t)
            os.remove(t)  # el audio no se guarda
            segmentos.sort(key=lambda x: x["ini"])
            # lo transcrito hasta ahora queda a mano para el chat ("¿qué van diciendo?", cerebro/chat.py)
            open(os.path.join(SALIDA, f"{video}.parcial.txt"), "w", encoding="utf-8").write(
                f"{titulo}\n{info['url']}\n\n" + "\n".join(f"[{transcribir.hhmmss(s['ini'])}] {s['texto']}" for s in segmentos))
            print(f"  trozo {n} transcrito ({len(segmentos)} segmentos)", flush=True)
            desde = max(0, n + 1 - VENTANA) * TROZO + desfase["desfase"]
            nuevo = "\n".join(f"[{transcribir.hhmmss(s['ini'])}] {s['texto']}" for s in segmentos if s["ini"] >= desde)
            # lo atrasado (recuperado de la hora que guarda YouTube) no genera avisos en caliente: ya no es "en caliente"
            atrasado = lista and info.get("inicio") and (time.time() - info["inicio"]) - (desfase["desfase"] + (n + 1) * TROZO) > 360
            if nuevo.strip() and not atrasado:
                try:
                    r = ia.generar_json(aviso or AVISO, f"Transmisión: {titulo}\nResumen previo:\n{resumen or '(inicio)'}\n\n"
                                        f"Ya avisado en esta sesión:\n{chr(10).join(avisados[-8:]) or '(nada)'}\n\n"
                                        f"Últimos minutos:\n{nuevo}", ESQUEMA_AVISO)
                    resumen = r["resumen"]
                    if r["importante"]:
                        from cerebro import anuncios
                        texto_aviso = anuncios.filtrar(r["aviso"], "en_vivo", info["url"])
                        if texto_aviso:
                            avisados.append(texto_aviso)
                            seg = sum(int(x) * 60 ** i for i, x in enumerate(reversed((r["momento"] or "0").split(":"))) if x.isdigit())
                            # lo importante que se dice en vivo va siempre al grupo de la oficina, con el enlace a ese minuto
                            telegram(f"🔴 {titulo.title()} · {r['momento'] or 'min ' + str(desde // 60)}\n{texto_aviso}\n"
                                     f"https://youtu.be/{video}?t={seg}", destino="general",
                                     ref=f"{'entrevista' if al_terminar else 'sesion'}:{video}", agente="entrevistas" if al_terminar else "relatora")
                except Exception as e:
                    print(f"  revisión en caliente: {e}", flush=True)
        if terminado and not pendientes(True):
            break
        time.sleep(20)

    if bajada:
        bajada.terminate()
    parcial = os.path.join(SALIDA, f"{video}.parcial.txt")
    if os.path.exists(parcial):
        os.remove(parcial)
    if not segmentos:
        os.rmdir(carpeta)
        print("  no se grabó audio: no hay nada que reportar", flush=True)
        if avisada:  # se avisó que se estaba siguiendo: hay que decir que falló (aviso del sistema → grupo de la oficina)
            telegram(f"⚠️ No pude grabar el audio de «{titulo.title()}». Revisen la Mac (salidas/logs/mesa.log).", destino="general")
        return
    texto = "\n".join(f"[{transcribir.hhmmss(s['ini'])}] {s['texto']}" for s in segmentos)
    json.dump({**info, "segmentos": segmentos}, open(os.path.join(SALIDA, f"{video}.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    open(os.path.join(SALIDA, f"{video}.txt"), "w", encoding="utf-8").write(texto)
    os.rmdir(carpeta)
    if al_terminar:
        return al_terminar(video, info)
    r = relatora.relatar(video, keylaw)
    if r["pedido"]:
        telegram("📄 Keylaw listo para revisar en la oficina (mesa de la Relatora):\n" +
                 "\n".join("• " + k["asunto"] for k in r["keylaws"]), destino="asamblea", ref=f"sesion:{video}", agente="relatora")
    else:
        telegram(f"🗂 {titulo.title()}: transcrita y guardada en el cerebro, sin Keylaw (no estaba marcada). "
                 "Si lo quieren, respondan a este mensaje («Keylaw») o pídanlo en la oficina.", destino="asamblea",
                 ref=f"sesion:{video}", agente="relatora")


def vigilar():
    siguiendo = {}
    while True:
        try:
            for video, titulo in en_vivo_ahora():
                if video not in siguiendo or not siguiendo[video].is_alive():
                    if video in siguiendo:
                        continue  # ya terminó
                    h = threading.Thread(target=seguir, args=(video, titulo), daemon=True)
                    h.start()
                    siguiendo[video] = h
        except Exception as e:
            print(f"vigilar: {e}", flush=True)
        time.sleep(180)


if __name__ == "__main__":
    cerebro.cargar_env()
    if sys.argv[1] == "vigilar":
        vigilar()
    else:
        seguir(sys.argv[2], limite=int(sys.argv[3]) if len(sys.argv) > 3 else None)
