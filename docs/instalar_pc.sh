#!/bin/bash
# En la PC, DENTRO de WSL (Ubuntu 24.04), como el usuario normal: instala todo lo de Linux de docs/INSTALAR_PC.md
# (pasos 2.4, 4 y 6). Lo de Windows (.wslconfig, energía, Tailscale de Windows, Chrome) se hace a mano antes.
# Uso: bash instalar_pc.sh [ruta de mudanza.tgz]   (por defecto ~/mudanza.tgz). Se puede correr de nuevo sin daño.
set -euo pipefail
MUDANZA=${1:-$HOME/mudanza.tgz}
REPO=${REPO:-https://github.com/wlozano98-dotcom/agente-panama.git}
DIR=$HOME/agente-panama
paso() { echo; echo "== $*"; }

paso "systemd y hora (UTC-5, igual que Panamá y Ecuador)"
if ! grep -q "systemd=true" /etc/wsl.conf 2>/dev/null; then
  printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf >/dev/null
  echo "systemd activado: en PowerShell 'wsl --shutdown', volver a entrar y correr este script otra vez"; exit 0
fi
sudo timedatectl set-timezone America/Panama || true

paso "paquetes del sistema"
sudo apt-get update -q
sudo apt-get install -y -q git python3-venv python3-pip ffmpeg curl unzip rclone gh jq
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH=$HOME/.local/bin:$PATH

paso "GPU"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || echo "OJO: WSL no ve la NVIDIA (driver de Windows)"

paso "el proyecto"
[ -d "$DIR/.git" ] || git clone "$REPO" "$DIR"
cd "$DIR" && git pull -q
if [ -f "$MUDANZA" ]; then
  tar xzf "$MUDANZA" -C "$DIR"
  if [ -d "$DIR/diseno_keyword" ]; then
    rm -rf "$HOME/diseno_keyword" && mv "$DIR/diseno_keyword" "$HOME/diseno_keyword"
    sed -i "s#^KEYWORD_DISENO=.*#KEYWORD_DISENO=$HOME/diseno_keyword#" .env
  fi
  chmod 600 .env
else
  echo "OJO: no encontré $MUDANZA (.env, ficha privada, ejemplos): sin eso no arranca"
fi
mkdir -p salidas/logs salidas/redes

paso "entorno de la mesa y Whisper (~/.venvs/whisper)"
python3 -m venv ~/.venvs/whisper
~/.venvs/whisper/bin/pip install -q --upgrade pip
~/.venvs/whisper/bin/pip install -q faster-whisper pypdf requests pillow nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
CUDA_LIBS=$(~/.venvs/whisper/bin/python -c "import os,nvidia.cublas.lib as a,nvidia.cudnn.lib as b;print(os.path.dirname(a.__file__)+':'+os.path.dirname(b.__file__))")

paso "navegador para PDF y Keyperfil (~/.venvs/nav)"
python3 -m venv ~/.venvs/nav
~/.venvs/nav/bin/pip install -q playwright pypdf   # pypdf: prensa.py (Orden del Día) corre con este python
~/.venvs/nav/bin/playwright install --with-deps chromium

paso "servicio que arranca solo (vigilante → mesa y receptor)"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/vigilante.service <<EOF
[Unit]
Description=Vigilante Agente Panama
After=network-online.target
[Service]
WorkingDirectory=%h/agente-panama
Environment=TZ=America/Panama
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=LD_LIBRARY_PATH=$CUDA_LIBS
ExecStart=/usr/bin/python3 cerebro/vigilante.py
Restart=always
RestartSec=20
StandardOutput=append:%h/agente-panama/salidas/logs/vigilante.log
StandardError=append:%h/agente-panama/salidas/logs/vigilante.log
[Install]
WantedBy=default.target
EOF
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload

paso "comprobaciones"
~/.venvs/whisper/bin/python -c "import cerebro; cerebro.cargar_env(); from db.d1 import consulta; print('D1:', consulta('SELECT 1'))" || echo "OJO: D1 no responde (.env)"
LD_LIBRARY_PATH=$CUDA_LIBS ~/.venvs/whisper/bin/python -c "
from faster_whisper import WhisperModel
WhisperModel('large-v3-turbo', device='cuda', compute_type='float16'); print('Whisper en GPU: OK')" || echo "OJO: Whisper no usa la GPU (seguirá en CPU, lento)"
[ -f datos/clientes_privados.json ] && echo "ficha privada: OK" || echo "OJO: falta datos/clientes_privados.json"

echo
echo "Listo. Para arrancar (SOLO cuando la Mac esté apagada, paso 9): systemctl --user enable --now vigilante"
echo "Ver: pgrep -fl 'mesa|receptor'; tail -f salidas/logs/vigilante.log"
