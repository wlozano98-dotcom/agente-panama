"""Las ilustraciones de la oficina (fondos, personajes y Kiwi) → imágenes livianas en D1 (tabla `imagenes`).

Uso: python3 bot/imagenes.py
Las piezas originales las hizo ChatGPT y están en ejemplos/diseno/piezas/ (no se suben al repo). Aquí se recortan y se
achican a WebP: cada fondo (día y noche) y, por personaje, una tira con sus poses en celdas del mismo ancho (la oficina
cambia de pose moviendo la tira). La oficina las pide a /oficina/img?n=<nombre>.
"""
import base64
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from db import d1  # noqa: E402

PIEZAS = os.path.join(cerebro.CARPETA, "ejemplos", "diseno", "piezas")
ALTO_PERSONA = 640

# poses de cada agente: (archivo, [(x0, x1), …]) en px del original; la primera es la de trabajo y la última la que
# mira al usuario. Las piezas traen figuras que se tocan: los cortes se eligieron a ojo sobre cada archivo.
POSES = {
    "relatora": ("p_keylaw.png", [(0, 500), (500, 1010), (1010, 1536)]),
    "normativa": ("p_keymonitor.png", [(25, 495), (470, 930)]),
    "judicial": ("p_judicial.png", [(20, 500), (500, 985), (985, 1500)]),
    "regulatoria": ("p_reguladores.png", [(0, 520), (520, 985), (985, 1536)]),
    "agenda": ("p_agenda.png", [(40, 520), (520, 960), (960, 1500)]),
    "entrevistas": ("p_entrevistas.png", [(40, 560), (560, 1030), (1030, 1536)]),
    "medios": ("p_medios.png", [(10, 480), (480, 880), (880, 1290)]),
    "politico": ("p_politico.png", [(180, 640), (640, 1150)]),
    "perfilador": ("p_perfilador.png", [(110, 520)]),
    "cifras": ("p_cifras.png", [(380, 880)]),
    "economico": ("p_cifras.png", [(690, 1120)]),
}


def webp(im, calidad=82):
    salida = io.BytesIO()
    im.save(salida, "WEBP", quality=calidad, method=6)
    return salida.getvalue()


def tira(archivo, cortes):
    im = Image.open(os.path.join(PIEZAS, archivo)).convert("RGBA")
    poses = [im.crop((x0, 0, x1, im.height)) for x0, x1 in cortes]
    cajas = [p.getchannel("A").getbbox() for p in poses]
    arriba, abajo = min(c[1] for c in cajas), max(c[3] for c in cajas)
    ancho = max(x1 - x0 for x0, x1 in cortes)
    escala = ALTO_PERSONA / (abajo - arriba)
    celda = round(ancho * escala)
    hoja = Image.new("RGBA", (celda * len(poses), ALTO_PERSONA), (0, 0, 0, 0))
    for i, p in enumerate(poses):
        p = p.crop((0, arriba, p.width, abajo)).resize((round(p.width * escala), ALTO_PERSONA), Image.LANCZOS)
        hoja.alpha_composite(p, (i * celda + (celda - p.width) // 2, 0))
    return hoja, {"poses": len(poses), "ancho": celda, "alto": ALTO_PERSONA}


def main():
    cerebro.cargar_env()
    d1.consulta("CREATE TABLE IF NOT EXISTS imagenes (nombre TEXT PRIMARY KEY, tipo TEXT, datos TEXT, info TEXT)")
    filas = []
    for zona in ("legal", "politica", "economica"):
        for sufijo in ("", "_noche"):
            im = Image.open(os.path.join(PIEZAS, f"fondo_{zona}{sufijo}.png")).convert("RGB")
            filas.append([f"fondo_{zona}{sufijo}", "image/webp", base64.b64encode(webp(im, 78)).decode(), "{}"])
    for agente, (archivo, cortes) in POSES.items():
        hoja, info = tira(archivo, cortes)
        filas.append([f"p_{agente}", "image/webp", base64.b64encode(webp(hoja)).decode(), json.dumps(info)])
    kiwi = Image.open(os.path.join(PIEZAS, "kiwi.png")).convert("RGBA").resize((256, 256), Image.LANCZOS)
    filas.append(["kiwi", "image/webp", base64.b64encode(webp(kiwi, 85)).decode(), "{}"])
    for f in filas:  # de a una y con parámetros: una sentencia de D1 no admite más de 100 KB de texto
        d1.consulta("INSERT OR REPLACE INTO imagenes (nombre, tipo, datos, info) VALUES (?, ?, ?, ?)", f)
        print(f"{f[0]}: {len(f[2]) * 3 // 4 // 1024} KB {f[3] if f[3] != '{}' else ''}", flush=True)


if __name__ == "__main__":
    main()
