#!/bin/bash
# En la MAC: empaqueta lo que NO está en GitHub para llevarlo a la PC (docs/INSTALAR_PC.md, paso 0).
# Uso: bash docs/empaquetar_mudanza.sh   → ~/mudanza.tgz (pasarlo por Tailscale/scp o USB; nunca por chat ni Drive)
set -euo pipefail
cd "$(dirname "$0")/.."

# La carpeta está en iCloud: hay archivos que solo existen en la nube. Leerlos los baja antes de empaquetar.
echo "bajando de iCloud lo que falte…"
find .env datos Invesitgacion ejemplos salidas/redes -type f -exec cat {} + > /dev/null 2>&1 || true

DISENO=$(grep -E '^KEYWORD_DISENO=' .env | cut -d= -f2- | tr -d '"' || true)
EXTRA=()
if [ -n "$DISENO" ] && [ -d "$DISENO" ]; then
  find "$DISENO" -type f -exec cat {} + > /dev/null 2>&1 || true
  rm -rf /tmp/diseno_keyword && cp -R "$DISENO" /tmp/diseno_keyword
  EXTRA=(-C /tmp diseno_keyword)
fi

tar czf ~/mudanza.tgz .env datos/clientes_privados.json Invesitgacion ejemplos salidas/redes "${EXTRA[@]}"
rm -rf /tmp/diseno_keyword

# Comprobar: ningún archivo vacío que no lo estaba (señal de que iCloud no lo bajó).
VACIOS=$(tar tzvf ~/mudanza.tgz | awk '$3 == 0 && $NF !~ /\/$/' | wc -l | tr -d ' ')
echo "listo: ~/mudanza.tgz ($(du -h ~/mudanza.tgz | cut -f1), $(tar tzf ~/mudanza.tgz | wc -l | tr -d ' ') entradas, $VACIOS archivos vacíos)"
[ "$VACIOS" -gt 5 ] && echo "OJO: muchos archivos vacíos; revisar que iCloud los haya bajado" || true
