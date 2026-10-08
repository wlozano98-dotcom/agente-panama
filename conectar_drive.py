"""Conecta Google Drive y Sheets de la cuenta de Panamá (se corre una sola vez).

Abre el navegador para que Andrés autorice con agentemonitoreopa@gmail.com y guarda el
permiso en .env como DRIVE_TOKEN, sin mostrarlo en pantalla.

Uso:
    python3 conectar_drive.py
"""
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(AQUI, ".env")


def main():
    env = open(ENV).read()
    cid = re.search(r"(?m)^GOOGLE_CLIENT_ID=(.*)$", env).group(1)
    secreto = re.search(r"(?m)^GOOGLE_CLIENT_SECRET=(.*)$", env).group(1)
    print("Se abrirá el navegador: entra con agentemonitoreopa@gmail.com.")
    print('Si aparece "Google no ha verificado esta app": Avanzado → Ir a Agente Panama.\n')
    # El token sale por stdout; los mensajes de rclone (enlace, avisos) van por stderr.
    salida = subprocess.run(
        [os.path.join(AQUI, "bin", "rclone"), "authorize", "drive", cid, secreto],
        stdout=subprocess.PIPE, text=True,
    ).stdout
    m = re.search(r"\{.*\}", salida, re.S)
    if not m:
        sys.exit("No llegó el permiso de Google. Vuelve a intentarlo.")
    token = json.loads(m.group(0))
    if "refresh_token" not in token:
        sys.exit("Google no entregó un permiso permanente (falta refresh_token).")
    linea = "DRIVE_TOKEN=" + json.dumps(token, separators=(",", ":"))
    if re.search(r"(?m)^DRIVE_TOKEN=", env):
        env = re.sub(r"(?m)^DRIVE_TOKEN=.*$", lambda _: linea, env)
    else:
        env = env.rstrip("\n") + "\n\n# Google Drive y Sheets (lo escribe conectar_drive.py)\n" + linea + "\n"
    open(ENV, "w").write(env)
    print("\nListo: permiso de Drive guardado en .env (DRIVE_TOKEN).")


if __name__ == "__main__":
    main()
