"""Despliega el vigía externo (bot/vigia.js) como Worker aparte `vigia-panama` con cron cada 5 minutos.

Usa del .env: CLOUDFLARE_TOKEN, CLOUDFLARE_ACCOUNT_ID y el bot del grupo de la oficina (TELEGRAM_GENERAL_TOKEN /
TELEGRAM_GENERAL_CHAT; si faltan, TELEGRAM_TOKEN / TELEGRAM_CHAT_ID). Estado: https://vigia-panama.agentemonitoreopa.workers.dev
  python3 bot/desplegar_vigia.py           todo (código, claves, cron)
  python3 bot/desplegar_vigia.py --codigo  solo el código
"""
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desplegar as dp  # noqa: E402  (cf(), .env y la base)
from db import d1  # noqa: E402

NOMBRE = "vigia-panama"


def subir_codigo():
    limite = uuid.uuid4().hex
    codigo = open(os.path.join(dp.CARPETA, "vigia.js"), encoding="utf-8").read().encode()
    meta = json.dumps({"main_module": "vigia.js", "compatibility_date": "2026-09-01",
                       "bindings": [{"type": "d1", "name": "DB", "id": d1.id_base()}],
                       "keep_bindings": ["secret_text"]})
    cuerpo = (f"--{limite}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n"
              f"Content-Type: application/json\r\n\r\n{meta}\r\n"
              f"--{limite}\r\nContent-Disposition: form-data; name=\"vigia.js\"; filename=\"vigia.js\"\r\n"
              f"Content-Type: application/javascript+module\r\n\r\n").encode() + codigo + f"\r\n--{limite}--\r\n".encode()
    dp.cf("PUT", f"/scripts/{NOMBRE}", cuerpo, f"multipart/form-data; boundary={limite}")
    print("código subido")


def subir_resto():
    token = os.environ.get("TELEGRAM_GENERAL_TOKEN") or os.environ["TELEGRAM_TOKEN"]
    chat = os.environ.get("TELEGRAM_GENERAL_CHAT") or os.environ["TELEGRAM_CHAT_ID"]
    for nombre, valor in (("TELEGRAM_TOKEN", token), ("TELEGRAM_CHAT", chat)):
        dp.cf("PUT", f"/scripts/{NOMBRE}/secrets", {"name": nombre, "text": valor, "type": "secret_text"})
    dp.cf("PUT", f"/scripts/{NOMBRE}/schedules", [{"cron": "*/5 * * * *"}])
    dp.cf("POST", f"/scripts/{NOMBRE}/subdomain", {"enabled": True})
    print("claves, cron (*/5) y subdominio listos")


if __name__ == "__main__":
    subir_codigo()
    if "--codigo" not in sys.argv:
        subir_resto()
