"""Estudio de grabación: video público de YouTube → transcripción (Whisper local) → cerebro. El audio se borra.

Uso (en la Mac): ~/.venvs/whisper/bin/python cerebro/transcribir.py <id de YouTube> [fuente]
Necesita uv (yt-dlp reciente con Python 3.12) y el entorno ~/.venvs/whisper con mlx-whisper.
Deja la transcripción en salidas/transcripciones/<id>.json (segmentos con tiempos) y .txt.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

CARPETA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = "mlx-community/whisper-large-v3-turbo"
UVX = os.path.expanduser("~/.local/bin/uvx")


def datos_video(video):
    r = subprocess.run([UVX, "--python", "3.12", "yt-dlp@latest", "--skip-download", "-J", "--", video],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    fecha = d.get("upload_date") or ""
    return {"id": video, "titulo": d.get("title"), "fecha": f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:]}" if fecha else None,
            "duracion": d.get("duration"), "canal": d.get("channel"), "url": f"https://www.youtube.com/watch?v={video}",
            "inicio": d.get("release_timestamp") or d.get("timestamp")}  # en vivo: cuándo empezó la transmisión


def bajar_audio(video, carpeta):
    destino = os.path.join(carpeta, f"{video}.%(ext)s")
    subprocess.run([UVX, "--python", "3.12", "yt-dlp@latest", "-q", "-f", "bestaudio[ext=m4a]/bestaudio",
                    "-o", destino, "--", video], check=True)
    return next(os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.startswith(video))


# Whisper (MLX, GPU de la Mac) NO aguanta dos transcripciones a la vez en el mismo proceso: el 2026-10-26 la Línea 3 y
# un noticiero se transcribían en paralelo y Metal tumbó la mesa ("failed assertion ... after commit call"). De a una.
_GPU = threading.Lock()


def transcribir(ruta_audio):
    import mlx_whisper
    with _GPU:
        r = mlx_whisper.transcribe(ruta_audio, path_or_hf_repo=MODELO, language="es", condition_on_previous_text=False,
                                   initial_prompt="Sesión de la Asamblea Nacional de Panamá. Honorable diputado, "
                                                  "señora presidenta, proyecto de ley, primer debate.")
    return [{"ini": round(s["start"], 1), "fin": round(s["end"], 1), "texto": s["text"].strip()} for s in r["segments"]]


def hhmmss(seg):
    seg = int(seg)
    return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


def main(video):
    salida = os.path.join(CARPETA, "salidas", "transcripciones")
    os.makedirs(salida, exist_ok=True)
    info = datos_video(video)
    print(f"{info['fecha']} · {info['titulo']} · {hhmmss(info['duracion'] or 0)}", flush=True)
    with tempfile.TemporaryDirectory() as tmp:  # el audio no se guarda
        inicio = time.time()
        audio = bajar_audio(video, tmp)
        print(f"audio bajado en {time.time() - inicio:.0f} s", flush=True)
        inicio = time.time()
        segmentos = transcribir(audio)
        print(f"transcrito en {time.time() - inicio:.0f} s: {len(segmentos)} segmentos", flush=True)
    texto = "\n".join(f"[{hhmmss(s['ini'])}] {s['texto']}" for s in segmentos)
    json.dump({**info, "segmentos": segmentos}, open(os.path.join(salida, f"{video}.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    open(os.path.join(salida, f"{video}.txt"), "w", encoding="utf-8").write(texto)
    print(os.path.join(salida, f"{video}.txt"))


if __name__ == "__main__":
    main(sys.argv[1])
