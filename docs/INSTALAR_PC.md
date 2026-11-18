# Instalación en la PC de la oficina (guía para las IA)

Uso interno de Claude u otra IA que haga la mudanza; Andrés no la lee. Ejecutar en orden, verificar cada paso
(columna «Comprobar») antes de seguir y anotar en CLAUDE.md lo que cambie. Nada de esto va con claves en el chat.

PC: Windows 11 Pro, Core Ultra 7 265K, 64 GB, RTX 5080 16 GB. Decisión (PLAN.md): el second brain en **WSL2 (Ubuntu)**,
no Hyper-V (no pasa la NVIDIA a la VM). Chrome + extensión de la oficina en **Windows**. Sistemas de la oficina: Gijar
(evalúa el acceso remoto; si propone otra herramienta, adaptar el paso 3).

## 0. Antes de tocar la PC (en la Mac)

1. Anotar qué corre: `pgrep -fl "vigilante|mesa.py|receptor"`.
2. Empaquetar lo que NO está en GitHub (desde la carpeta del proyecto):
   `tar czf ~/mudanza.tgz .env datos/clientes_privados.json Invesitgacion ejemplos salidas/redes`
   más la carpeta del sistema de diseño (ruta en KEYWORD_DISENO del .env). `salidas/` entera no hace falta (logs, PDF
   de paso); `salidas/redes` sí (bandeja de X). Pasar por Tailscale (`scp`) o USB; nunca por chat ni Drive público.
3. NO apagar la Mac todavía (paso 9).

## 1. Windows

| Hacer | Comprobar |
| - | - |
| Energía: nunca suspender ni hibernar (`powercfg /change standby-timeout-ac 0`, `hibernate-timeout-ac 0`, `monitor-timeout-ac 30`); al volver la luz, encender (BIOS: «Restore on AC power loss» = On). | `powercfg /a`, BIOS |
| Inicio de sesión automático en la cuenta del servidor (Sysinternals **Autologon**; no dejar la clave en texto). Bloquear la pantalla está bien: Chrome y WSL siguen. | reiniciar → entra solo |
| Windows Update: horas activas 6-23, reinicios solo de madrugada; nada de reinicio forzado de día. | Configuración → Windows Update |
| Driver NVIDIA reciente (Game Ready o Studio) en Windows; en WSL NO se instala driver. | `nvidia-smi` en PowerShell |
| UPS conectado (si hay software, que apague limpio al final de la batería). | — |

## 2. WSL2 + Ubuntu

1. PowerShell admin: `wsl --install -d Ubuntu-24.04` → reiniciar → crear usuario Linux.
2. `C:\Users\<usuario>\.wslconfig`:
   ```
   [wsl2]
   networkingMode=mirrored
   memory=40GB
   vmIdleTimeout=-1
   ```
   `mirrored` = Chrome de Windows llega al receptor en `127.0.0.1:8765` igual que en la Mac (la extensión apunta ahí,
   `extension/oficina-chrome/fondo.js`, const MAC). `vmIdleTimeout=-1` = la VM no se apaga sola. `wsl --shutdown` para aplicar.
3. Activar systemd: `/etc/wsl.conf` → `[boot]\nsystemd=true`; `wsl --shutdown`.
4. Paquetes: `sudo apt update && sudo apt install -y git python3-venv python3-pip ffmpeg curl unzip`
   + `curl -LsSf https://astral.sh/uv/install.sh | sh` (deja `uvx` en `~/.local/bin`, la ruta que usa transcribir.py).
5. Comprobar GPU dentro de WSL: `nvidia-smi` muestra la RTX 5080.

## 3. Acceso remoto (lo que más le preocupa a Andrés)

1. **Tailscale** en Windows (instalador) y dentro de WSL (`curl -fsSL https://tailscale.com/install.sh | sh;
   sudo tailscale up --ssh`), con la cuenta que se decida (de la oficina si Gijar lo prefiere). En la Mac de Andrés
   también. Nombres sugeridos: `oficina-win`, `oficina-wsl`.
2. **Claude Code** dentro de WSL (instalador oficial) e iniciar sesión con la cuenta de Andrés. Flujo de trabajo:
   desde la Mac `ssh <usuario>@oficina-wsl`, `cd ~/agente-panama`, `claude`.
3. **Escritorio remoto** para captchas (Gaceta/Corte «Soy humano», sesión de X): Chrome Remote Desktop o AnyDesk
   (si la oficina ya lo usa, AnyDesk), con clave fuerte.

Comprobar: desde la Mac fuera de la red de la oficina (datos del celular) entra el SSH y se ve el escritorio.

## 4. El proyecto

```
cd ~ && git clone https://github.com/wlozano98-dotcom/agente-panama.git && cd agente-panama
tar xzf ~/mudanza.tgz            # .env, datos/clientes_privados.json, Invesitgacion, ejemplos, salidas/redes
chmod 600 .env
```
- En `.env`: corregir KEYWORD_DISENO a la ruta nueva del sistema de diseño.
- `bin/` (rclone y gh de macOS) no sirve: `sudo apt install rclone gh` o binarios Linux en `bin/`. Revisar quién usa
  `bin/rclone` antes (`grep -rn "bin/" --include='*.py' .`).
- Entornos (las rutas son las que espera el código):
  - `python3 -m venv ~/.venvs/whisper && ~/.venvs/whisper/bin/pip install faster-whisper pypdf requests` (+ lo que
    pida `mesa.py` al arrancar: instalar lo que falte hasta que levante). transcribir.py usa faster-whisper con CUDA si
    no hay mlx-whisper (2026-11-18). Si CUDA falla por cuDNN: `pip install nvidia-cudnn-cu12 nvidia-cublas-cu12` y
    exportar LD_LIBRARY_PATH a sus `lib/`.
  - `python3 -m venv ~/.venvs/nav && ~/.venvs/nav/bin/pip install playwright && ~/.venvs/nav/bin/playwright install --with-deps chromium`
    (Keyperfil y lo que imprime PDF).
- Comprobar Whisper en GPU: `~/.venvs/whisper/bin/python -c "from cerebro import transcribir as t; print(t.transcribir('algo.wav')[:2])"`
  con un audio corto (y `nvidia-smi` mostrando el proceso). Esperado: segundos, no minutos.
- Comprobar D1: `python3 -c "import cerebro; cerebro.cargar_env(); from db.d1 import consulta; print(consulta('SELECT 1'))"`.

## 5. Chrome de la oficina (Windows)

1. Chrome con un perfil propio de la oficina. `chrome://extensions` → Modo desarrollador → Cargar descomprimida →
   `\\wsl$\Ubuntu-24.04\home\<usuario>\agente-panama\extension\oficina-chrome` (o copiarla a `C:\` si Chrome no la
   abre desde `\\wsl$`; entonces, tras cada cambio, copiar de nuevo y recargar).
2. Iniciar sesión en la cuenta de X de la oficina (en ESPAÑOL) y abrir una vez la Gaceta y la página de edictos del
   Pleno para pasar la verificación humana (lo hace una persona).
3. Chrome: «Continuar ejecutando apps en segundo plano» = sí; abrir al iniciar Windows (carpeta Inicio o tarea).
4. Si pide permiso de «red local» para 127.0.0.1, aceptarlo.

Comprobar: en `salidas/logs/` del receptor llegan las llamadas de la extensión (GET /tengo, /judicial/vistos).

## 6. Arranque solo

- Servicio systemd de usuario `~/.config/systemd/user/vigilante.service`:
  ```
  [Unit]
  Description=Vigilante Agente Panama
  After=network-online.target
  [Service]
  WorkingDirectory=%h/agente-panama
  ExecStart=/usr/bin/python3 cerebro/vigilante.py
  Restart=always
  RestartSec=20
  StandardOutput=append:%h/agente-panama/salidas/logs/vigilante.log
  StandardError=append:%h/agente-panama/salidas/logs/vigilante.log
  [Install]
  WantedBy=default.target
  ```
  `systemctl --user enable --now vigilante` y `sudo loginctl enable-linger <usuario>` (corre sin sesión abierta).
  OJO: el vigilante levanta mesa y receptor con `start_new_session`; con `Restart=always` revisar que no queden dos
  mesas tras reiniciar el servicio (`pgrep -fl mesa.py`). Para reiniciar la mesa sin alarma: `vigilante.py --reiniciar mesa`.
- Windows debe arrancar WSL al iniciar sesión: Programador de tareas → al iniciar sesión →
  `wsl.exe -d Ubuntu-24.04 --exec /bin/true` (con systemd, eso basta para levantar el servicio).

## 7. Vigía externo (ya está hecho, 2026-11-18)

Worker aparte `vigia-panama` (bot/vigia.js; desplegar con `python3 bot/desplegar_vigia.py`), cron cada 5 min, lee
`latidos` en D1: si la mesa no late hace más de 15 min avisa al grupo de la oficina (recordatorio cada 2 h y aviso al
volver). Se arma solo con el primer latido fresco. Estado: https://vigia-panama.agentemonitoreopa.workers.dev.
El equipo en `latidos` es el hostname: la PC aparece con otro nombre (la fila de la Mac queda vieja; borrarla tras la
mudanza: `DELETE FROM latidos WHERE equipo = 'Andress-MacBook-Air'`).

## 8. Prueba de fuego

1. Reiniciar Windows sin tocar nada → en menos de 5 min: entra solo, Chrome abierto, `pgrep -fl "mesa|receptor"` en
   WSL, la oficina muestra la mesa encendida, el vigía en `vivo`.
2. Matar la mesa a propósito (`pkill -f mesa.py`) → el vigilante la levanta y avisa.
3. Apagar WSL 20 min (`wsl --shutdown`) → llega el 🚨 del vigía; al volver, el ✅.
4. Un en vivo o un video corto del canal de la Asamblea: transcribe con la GPU.

## 9. Apagar la Mac (solo después del paso 8)

En la Mac: matar vigilante, mesa y receptor; quitar o desactivar la extensión de la oficina en el Chrome de la Mac.
Dos mesas a la vez = avisos duplicados y los bots de Telegram (getUpdates) se pisan.

## 10. Cuentas de la oficina (pendiente de decisión, 2026-11-18)

Andrés quiere pasar Cloudflare (Workers Paid) y GitHub a las cuentas de la oficina. Ver la sección «Cambio de
cuentas» en PLAN.md antes de hacerlo; no mezclarlo con la mudanza física el mismo día.
