"""El vigilante (2026-10-26): si la mesa o el receptor se caen, los vuelve a levantar y avisa al grupo de la oficina.

El lunes 26/10 la mesa se cayó en silencio (Whisper con dos transmisiones a la vez) y se perdieron minutos de la
Línea 3 del Metro y de un noticiero. El vigilante revisa cada 30 segundos que los dos procesos estén vivos.
Uso (en la Mac, una sola vez; queda corriendo):
  nohup python3 cerebro/vigilante.py >> salidas/logs/vigilante.log 2>&1 &
Él mismo arranca la mesa y el receptor si no están. Reinicio A PROPÓSITO (sin alarma en el chat):
  python3 cerebro/vigilante.py --reiniciar mesa
Si la Mac se reinicia, hay que volver a lanzarlo (en la PC con Linux de la oficina esto será un servicio de systemd
que arranca solo).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402

LOGS = os.path.join(cerebro.CARPETA, "salidas", "logs")
A_PROPOSITO = os.path.join(LOGS, "reinicio_a_proposito")  # lo deja --reiniciar: esa caída no se avisa
WHISPER = os.path.expanduser("~/.venvs/whisper/bin/python")
PROCESOS = {
    # nombre: (script, python, log)
    "mesa": ("cerebro/mesa.py", WHISPER, "mesa.log"),
    "receptor": ("cerebro/receptor_gaceta.py", sys.executable, "receptor.log"),
}
ARTICULO = {"mesa": "La mesa", "receptor": "El receptor"}
PUERTOS = {"receptor": 8765}  # el 29/10 otra sesión de Claude ocupó el 8765 con su propio servidor web


def ocupante(nombre):
    """Si el puerto del proceso lo tiene OTRO programa, devuelve su comando (si no, "")."""
    puerto = PUERTOS.get(nombre)
    if not puerto:
        return ""
    pids = subprocess.run(["lsof", "-t", "-nP", f"-iTCP:{puerto}", "-sTCP:LISTEN"],
                          capture_output=True, text=True).stdout.split()
    if not pids:
        return ""
    return subprocess.run(["ps", "-o", "command=", "-p", pids[0]], capture_output=True, text=True).stdout.strip()[:200]


def vivo(script):
    return subprocess.run(["pgrep", "-f", script], capture_output=True).returncode == 0


def levantar(nombre):
    script, python, log = PROCESOS[nombre]
    entorno = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}
    subprocess.Popen([python, script], cwd=cerebro.CARPETA, env=entorno, start_new_session=True,
                     stdout=open(os.path.join(LOGS, log), "a"), stderr=subprocess.STDOUT)


def ultimo_error(log, lineas=40):
    """Las últimas líneas con error del registro, para decir en el aviso por qué se cayó."""
    try:
        texto = open(os.path.join(LOGS, log), encoding="utf-8", errors="ignore").read().splitlines()[-lineas:]
    except OSError:
        return ""
    malas = [l.strip() for l in texto if any(p in l for p in ("Error", "error", "assertion", "Traceback", "Killed"))]
    return malas[-1][:200] if malas else ""


def vigilar():
    caidas = {}
    avisado_ocupado = {}
    while True:
        for nombre, (script, _, log) in PROCESOS.items():
            if not vivo(script):
                ajeno = ocupante(nombre)
                if ajeno:
                    # Levantarlo daría "Address already in use" cada 30 s: se avisa una vez y se espera.
                    if avisado_ocupado.get(nombre) != ajeno:
                        avisado_ocupado[nombre] = ajeno
                        print(time.strftime("%Y-%m-%d %H:%M:%S"), f"{nombre}: puerto ocupado por {ajeno}", flush=True)
                        try:
                            cerebro.telegram(f"⚠️ {ARTICULO[nombre]} de la Mac no puede arrancar: otro programa ocupa "
                                             f"el puerto {PUERTOS[nombre]} ({ajeno}). Hay que cerrarlo.", destino="general")
                        except Exception as e:
                            print(f"  telegram: {e}", flush=True)
                    continue
                avisado_ocupado.pop(nombre, None)
                if os.path.exists(A_PROPOSITO):
                    os.remove(A_PROPOSITO)
                    print(time.strftime("%Y-%m-%d %H:%M:%S"), f"{nombre}: reinicio a propósito", flush=True)
                    levantar(nombre)
                    continue
                motivo = ultimo_error(log)
                print(time.strftime("%Y-%m-%d %H:%M:%S"), f"{nombre} caído; lo levanto. {motivo}", flush=True)
                levantar(nombre)
                caidas.setdefault(nombre, []).append(time.time())
                recientes = [t for t in caidas[nombre] if t > time.time() - 3600]
                caidas[nombre] = recientes
                try:
                    cerebro.telegram(f"⚠️ {ARTICULO[nombre]} de la Mac se cayó y ya volvió a arrancar"
                                     + (f" ({len(recientes)} veces en la última hora: revisen la Mac)" if len(recientes) > 2 else "")
                                     + (f".\nÚltimo error: {motivo}" if motivo else "."), destino="general")
                except Exception as e:
                    print(f"  telegram: {e}", flush=True)
        time.sleep(30)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--reiniciar":
        open(A_PROPOSITO, "w").close()
        subprocess.run(["pkill", "-f", PROCESOS[sys.argv[2]][0]])
        print(f"{sys.argv[2]}: el vigilante la levanta en menos de 30 segundos")
        sys.exit()
    cerebro.cargar_env()
    os.makedirs(LOGS, exist_ok=True)
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "vigilante encendido", flush=True)
    vigilar()
