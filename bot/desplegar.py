"""Sube a Kiwi (bot y oficina) a Cloudflare Workers y lo conecta con Telegram.

Uso: python3 bot/desplegar.py            # sube el código, las claves y el webhook
     python3 bot/desplegar.py --codigo   # solo el código (tras un cambio en worker.js u oficina.html)

Lee de .env: CLOUDFLARE_TOKEN, CLOUDFLARE_ACCOUNT_ID, TELEGRAM_TOKEN, GEMINI_KEY, GOOGLE_CLIENT_ID,
GOOGLE_CLIENT_SECRET, DRIVE_TOKEN (su refresh_token) y BOT_AUTORIZADOS (IDs de Telegram separados por coma; si no
está, solo TELEGRAM_CHAT_ID). BOT_WEBHOOK_SECRET y OFICINA_CLAVE se generan la primera vez y quedan en .env.
"""
import base64
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
import uuid

CARPETA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(CARPETA)
sys.path.insert(0, RAIZ)
import agente  # noqa: E402  (para leer .env igual que el agente)
from db import d1  # noqa: E402

NOMBRE = "agente-panama"

agente.cargar_env()
API = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/workers"


def cf(metodo, ruta, datos=None, tipo="application/json"):
    if isinstance(datos, (dict, list)):
        datos = json.dumps(datos).encode()
    req = urllib.request.Request(API + ruta, data=datos, method=metodo, headers={
        "Authorization": "Bearer " + os.environ["CLOUDFLARE_TOKEN"], "Content-Type": tipo})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Cloudflare {metodo} {ruta}: {e.code} {e.read().decode()[:500]}")


def guardar_env(clave, valor):
    ruta = os.path.join(RAIZ, ".env")
    lineas = [l for l in open(ruta).read().splitlines() if not l.startswith(clave + "=")]
    open(ruta, "w").write("\n".join(lineas + [f"{clave}={valor}"]) + "\n")
    os.chmod(ruta, 0o600)


def subir_codigo():
    limite = uuid.uuid4().hex
    codigo = open(os.path.join(CARPETA, "worker.js"), encoding="utf-8").read()
    pagina = open(os.path.join(CARPETA, "oficina.html"), encoding="utf-8").read()
    for nombre in ("keyword-negro", "keyword-blanco"):  # logos de Keyword dentro de la página
        datos = base64.b64encode(open(os.path.join(CARPETA, "img", nombre + ".png"), "rb").read()).decode()
        pagina = pagina.replace(f"__LOGO_{nombre.split('-')[1].upper()}__", "data:image/png;base64," + datos)
    # la escena dibujada: la oficina de siempre + bot/escena_entrada.css y .js (Andrés, 2026-10-26: la publicada, con
    # la entrada en el medio, Kiwi con el logo y la pantalla con el cerebro; reemplaza a escena_nueva)
    previa = ""
    if os.path.exists(os.path.join(CARPETA, "escena_entrada.js")):
        css = open(os.path.join(CARPETA, "escena_entrada.css"), encoding="utf-8").read()
        js = open(os.path.join(CARPETA, "escena_entrada.js"), encoding="utf-8").read()
        pagina = pagina.replace("Math.min(2, base", "Math.min(3, base")  # cuatro zonas: al arrastrar se llega a la económica
        fin = pagina.rindex("})();")
        previa = (pagina[:fin] + js + "\n" + pagina[fin:]).replace("</style>", css + "\n</style>", 1).replace(
            "<title>", '<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet"><title>', 1)
        pagina = previa  # la escena dibujada es la oficina publicada
    # íconos y logo del modelo de Keyperfil de Keyword (ejemplos/ y el sistema de diseño no se suben al repo)
    activos = {}
    carpeta_kp = os.path.join(os.path.dirname(CARPETA), "ejemplos", "keyword", "keyperfil")
    for n in ("birrete", "foco", "info"):
        if os.path.exists(os.path.join(carpeta_kp, n + ".png")):
            activos[n] = "data:image/png;base64," + base64.b64encode(open(os.path.join(carpeta_kp, n + ".png"), "rb").read()).decode()
    # logo en azul marino como en el modelo (PNG: el conversor a PDF del navegador dibuja mal los SVG)
    import io
    from PIL import Image
    negro = Image.open(os.path.join(CARPETA, "img", "keyword-negro.png")).convert("RGBA")
    marino = Image.new("RGBA", negro.size, (46, 53, 102, 255))
    marino.putalpha(negro.getchannel("A"))
    salida = io.BytesIO(); marino.save(salida, "PNG")
    activos["logo"] = "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode()
    codigo = codigo.replace("__KP_ACTIVOS__", json.dumps(activos))
    mapa = open(os.path.join(os.path.dirname(CARPETA), "diseno", "mapa.html"), encoding="utf-8").read()
    aprendizaje = open(os.path.join(os.path.dirname(CARPETA), "diseno", "aprendizaje.html"), encoding="utf-8").read()
    codigo = codigo.replace("__PAGINA_APRENDIZAJE__", json.dumps(aprendizaje))
    codigo = codigo.replace("__PAGINA_MAPA__", json.dumps(mapa)).replace("__PAGINA_OFICINA__", json.dumps(pagina)).replace("__PAGINA_PREVIA__", json.dumps(previa)).encode()
    meta = json.dumps({"main_module": "worker.js", "compatibility_date": "2026-09-01",
                       "bindings": [{"type": "d1", "name": "DB", "id": d1.id_base()},
                                    {"type": "vectorize", "name": "VECTORES", "index_name": "cerebro-panama"}],
                       "keep_bindings": ["secret_text"]})
    cuerpo = (
        f"--{limite}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n"
        f"Content-Type: application/json\r\n\r\n{meta}\r\n"
        f"--{limite}\r\nContent-Disposition: form-data; name=\"worker.js\"; filename=\"worker.js\"\r\n"
        f"Content-Type: application/javascript+module\r\n\r\n"
    ).encode() + codigo + f"\r\n--{limite}--\r\n".encode()
    cf("PUT", f"/scripts/{NOMBRE}", cuerpo, f"multipart/form-data; boundary={limite}")
    print("código subido")


def subir_secretos():
    for clave in ("BOT_WEBHOOK_SECRET", "OFICINA_CLAVE"):
        if not os.environ.get(clave):
            os.environ[clave] = secrets.token_urlsafe(18)
            guardar_env(clave, os.environ[clave])
    estado = agente.cargar_estado()
    valores = {
        "TELEGRAM_TOKEN": os.environ["TELEGRAM_TOKEN"],
        "WEBHOOK_SECRET": os.environ["BOT_WEBHOOK_SECRET"],
        "AUTORIZADOS": os.environ.get("BOT_AUTORIZADOS") or os.environ["TELEGRAM_CHAT_ID"],
        "GEMINI_KEY": os.environ["GEMINI_KEY"],
        "GOOGLE_CLIENT_ID": os.environ["GOOGLE_CLIENT_ID"],
        "GOOGLE_CLIENT_SECRET": os.environ["GOOGLE_CLIENT_SECRET"],
        "GOOGLE_REFRESH_TOKEN": json.loads(os.environ["DRIVE_TOKEN"])["refresh_token"],
        "OFICINA_CLAVE": os.environ["OFICINA_CLAVE"],
        "MATRIZ_ID": estado.get("matriz_id", ""),
    }
    for nombre, valor in valores.items():
        if valor:
            cf("PUT", f"/scripts/{NOMBRE}/secrets", {"name": nombre, "text": valor, "type": "secret_text"})
    print(f"{len(valores)} claves guardadas en Cloudflare")


def conectar_telegram():
    cf("POST", f"/scripts/{NOMBRE}/subdomain", {"enabled": True, "previews_enabled": False})
    subdominio = cf("GET", "/subdomain")["result"]["subdomain"]
    url = f"https://{NOMBRE}.{subdominio}.workers.dev"
    datos = json.dumps({"url": url, "secret_token": os.environ["BOT_WEBHOOK_SECRET"],
                        "allowed_updates": ["message"], "drop_pending_updates": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/setWebhook",
                                 data=datos, headers={"Content-Type": "application/json"})
    print("Telegram:", json.load(urllib.request.urlopen(req, timeout=30)).get("description"))
    print("bot en", url)
    print("oficina en", f"{url}/oficina?k=<OFICINA_CLAVE del .env>")


if __name__ == "__main__":
    subir_codigo()
    if "--codigo" not in sys.argv:
        subir_secretos()
        conectar_telegram()
