"""Agente de alertas de la Asamblea Nacional de Panamá.

Cada hora lee el Seguimiento Legislativo (seglegis.py), detecta anteproyectos nuevos y cambios de etapa, analiza
el texto presentado con Gemini según criterios.md, guarda el PDF y el análisis en Google Drive (una carpeta por
comisión y otra por ficha) y avisa por Telegram.

La primera corrida solo registra las fichas existentes (sin avisos). Después, las fichas activas que aún no tienen
análisis se analizan de a poco ("rezagadas", sin avisar) para que los cambios de etapa lleguen con su impacto.

Uso:
    python3 agente.py                  # corrida normal
    python3 agente.py --prueba         # no guarda estado ni envía a Telegram (imprime los mensajes)
    python3 agente.py --demo 8629      # analiza una ficha y manda el aviso como si fuera nueva (no toca el estado)
"""
import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid

import base
import nombres
import seglegis

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_ESTADO = os.path.join(CARPETA, "estado.json")
ARCHIVO_CRITERIOS = os.path.join(CARPETA, "criterios.md")

# Si Google retira un modelo, se cambia aquí. Se prueban en orden.
MODELOS_GEMINI = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]
GEMINI = "https://generativelanguage.googleapis.com"

DRIVE_RAIZ = "Asamblea Nacional de Panamá"
SIN_COMISION = "Por asignar"
LIMITE_TELEGRAM = 50 * 1024 * 1024  # los bots no pueden enviar archivos más grandes
LIMITE_PDF_GEMINI = 30 * 1024 * 1024  # más grande: se analiza solo por el título
MAX_INTENTOS = 3
REZAGADAS_POR_CORRIDA = 4   # fichas viejas sin análisis que se analizan en silencio en cada corrida
ETAPAS_POR_CORRIDA = 60     # fichas viejas a las que se les baja el historial de etapas en cada corrida
HORAS_COMISIONES = 6        # la comisión de cada ficha se revisa cada 6 horas (o antes si hay fichas nuevas)

# Etapas donde el proyecto ya no avanza: no se analizan como rezagadas.
TERMINADAS = {"Ley", "Archivado", "Negado", "Retirado por proponente", "Fusionado"}
# La lista no cambia de etapa cuando el Pleno aprueba el tercer debate: a estas se les mira el historial siempre.
VIGILAR_HISTORIAL = {"Tercer Debate", "Tercer Debate(Objetado)"}
# Las rezagadas se analizan de las más avanzadas a las menos (lo que está por volverse ley importa más).
AVANCE = {"Enviado al Ejecutivo": 9, "Objetado por Ejecutivo": 8, "Tercer Debate(Objetado)": 8, "Tercer Debate": 7,
          "Segundo Debate(Objetado)": 6, "Segundo Debate": 6, "Primer Debate": 5, "Enviado a subcomisión para analisis": 4,
          "Prohijado": 3, "Suspendido": 1}


# ---------------------------------------------------------------- configuración


def cargar_env():
    """Lee el .env local (en GitHub Actions las claves llegan como secretos)."""
    ruta = os.path.join(CARPETA, ".env")
    if not os.path.exists(ruta):
        return
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


def config(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        sys.exit(f"Falta la variable {nombre}")
    return valor


def cargar_estado():
    estado = json.load(open(ARCHIVO_ESTADO, encoding="utf-8")) if os.path.exists(ARCHIVO_ESTADO) else {}
    for clave in ("fichas", "pendientes", "drive"):
        estado.setdefault(clave, {})
    return estado


def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1, sort_keys=True)


def normalizar(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()


def hoy():
    return datetime.date.today().isoformat()


def ddmm(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


# ---------------------------------------------------------------- nombres legibles

TILDES = {
    "COMISION": "Comisión", "ECONOMIA": "Economía", "EDUCACION": "Educación", "POBLACION": "Población",
    "PREVENCION": "Prevención", "ERRADICACION": "Erradicación", "PLANIFICACION": "Planificación",
    "POLITICA": "Política", "ECONOMICA": "Económica", "ECONOMICOS": "Económicos", "PUBLICA": "Pública",
    "PUBLICAS": "Públicas", "ETICA": "Ética", "INDIGENAS": "Indígenas", "COMUNICACION": "Comunicación",
    "NIÑEZ": "Niñez", "MINISTERIO": "Ministerio", "ORGANO": "Órgano", "NACION": "Nación",
    "ADMINISTRACION": "Administración", "PROCURADURIA": "Procuraduría", "TRAFICO": "Tráfico",
}
MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "por", "a", "al", "con"}


def titulo(texto):
    """'COMISION DE ECONOMIA Y FINANZAS' → 'Comisión de Economía y Finanzas'."""
    palabras = []
    for i, p in enumerate((texto or "").split()):
        limpio, signo = p.rstrip(",.;"), p[len(p.rstrip(",.;")):]
        if limpio in TILDES:
            palabras.append(TILDES[limpio] + signo)
        elif i > 0 and p.lower() in MINUSCULAS:
            palabras.append(p.lower())
        else:
            palabras.append(p[:1].upper() + p[1:].lower())
    return " ".join(palabras)


def nombre_comision(texto):
    if not texto or "POR ASIGNAR" in texto:
        return SIN_COMISION
    return titulo(texto)


def nombre_proponente(texto):
    """'H.D ALAIN ALBENIS CEDEÑO HERRERA' → 'H.D. Alain Albenis Cedeño Herrera'."""
    t = re.sub(r"^H\.\s?D\.?\s*", "", texto or "").strip()
    nombre = titulo(t)
    return ("H.D. " + nombre) if re.match(r"^H\.\s?D", texto or "") else nombre


_UNIFICADOR = {}


def unificador(estado=None):
    """Unificador de nombres de proponentes aprendido de todas las fichas (se arma una vez por corrida)."""
    if "u" not in _UNIFICADOR:
        _UNIFICADOR["u"] = nombres.Unificador([f["proponente"] for f in (estado or cargar_estado())["fichas"].values()])
    return _UNIFICADOR["u"]


def texto_proponentes(f, todos=False):
    """'José Pérez Barboni' · 'José Pérez Barboni y 3 más' · o la lista completa."""
    lista = unificador().lista(f["proponente"])
    if not lista:
        return nombre_proponente(f["proponente"])
    nombres_ = [p["nombre"] + (" (suplente)" if p["tipo"] == "Suplente" else "") for p in lista]
    if todos or len(nombres_) == 1:
        return "; ".join(nombres_)
    return f"{nombres_[0]} y {len(nombres_) - 1} más"


def numero(f):
    """'Proyecto 724' o 'Anteproyecto 203' (los números se reinician; la ficha es el identificador único)."""
    if f.get("proyecto") not in ("", "0", None):
        return f"Proyecto {f['proyecto']}"
    if f.get("anteproyecto") not in ("", "0", None):
        return f"Anteproyecto {f['anteproyecto']}"
    return f"Ficha {f['ficha']}"


# ---------------------------------------------------------------- sectores y clientes

CLIENTES_DATOS = json.load(open(os.path.join(CARPETA, "datos", "clientes.json"), encoding="utf-8"))
SECTORES = CLIENTES_DATOS["sectores"]
CLIENTES = CLIENTES_DATOS["clientes"]
TEMAS = sorted({t for c in CLIENTES.values() for t in c.get("temas", [])})
TODAS = "TODAS LAS EMPRESAS"
SECTORES_GENERALES = {"OTROS", "INDUSTRIAS", TODAS}
NIVELES = ["alto", "medio", "bajo"]
ICONOS = {"alto": "🔴", "medio": "🟠", "bajo": "🟡", "ninguno": "⚪"}


def sectores_cliente(c):
    return set(c["sector"]) if isinstance(c["sector"], list) else {c["sector"]}


def clientes_afectados(r):
    """Cruce local de sectores y temas con la ficha de clientes (los nombres nunca pasan por Gemini)."""
    temas, sectores = set(r.get("temas", [])), set(r.get("sectores", [])) - SECTORES_GENERALES
    return sorted(n for n, c in CLIENTES.items() if temas & set(c.get("temas", [])) or sectores_cliente(c) & sectores)


def completar_impacto(r):
    """Impacto general = el máximo de los sectores; sectores de la ficha = los de nivel alto/medio (o bajo si no hay)."""
    por_sector = {}
    for x in r.get("impactos") or []:
        if x.get("sector") in SECTORES + [TODAS] and x.get("nivel") in NIVELES:
            antes = por_sector.get(x["sector"])
            if not antes or NIVELES.index(x["nivel"]) < NIVELES.index(antes["nivel"]):
                por_sector[x["sector"]] = x
    r["impactos"] = sorted(por_sector.values(), key=lambda x: NIVELES.index(x["nivel"]))
    r["impacto"] = r["impactos"][0]["nivel"] if r["impactos"] else "ninguno"
    r["sectores"] = [x["sector"] for x in r["impactos"] if x["nivel"] != "bajo" or r["impacto"] == "bajo"]
    return r


def texto_sectores(r):
    niveles = {x["sector"]: x["nivel"] for x in r.get("impactos") or []}
    return ", ".join(f"{s} ({niveles[s]})" if s in niveles else s for s in r.get("sectores", []))


# ---------------------------------------------------------------- Gemini

ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING", "description": "El título oficial completo, con mayúsculas y tildes correctas "
                                                    "(no en mayúsculas sostenidas). No lo resumas."},
        "titulo_corto": {"type": "STRING", "description": "Nombre corto, máximo 70 caracteres, para nombrar una "
                                                          "carpeta. Ej.: 'Reforma a la ley de la AMPYME'"},
        "resumen": {"type": "STRING", "description": "3 a 5 líneas, en lenguaje sencillo: qué propone y a quién afecta"},
        "impactos": {
            "type": "ARRAY",
            "description": "Un elemento por cada sector al que la ley le cambia reglas que se le aplican directamente, "
                           "según los criterios. Vacío si no impacta a ningún sector.",
            "items": {"type": "OBJECT", "properties": {
                "sector": {"type": "STRING", "enum": SECTORES + [TODAS]},
                "nivel": {"type": "STRING", "enum": NIVELES},
                "razon": {"type": "STRING", "description": "Por qué ese nivel para ese sector, en una frase concreta"},
            }, "required": ["sector", "nivel", "razon"]},
        },
        "razon": {"type": "STRING", "description": "Por qué ese impacto para las empresas, en 1 o 2 frases concretas "
                                                   "(o por qué no tiene)"},
        "disposiciones": {"type": "ARRAY", "items": {"type": "STRING"},
                          "description": "Artículos concretos que podrían afectar a empresas y qué hacen. Vacío si no hay."},
    },
    "required": ["titulo", "titulo_corto", "resumen", "impactos", "razon", "disposiciones"],
}
if TEMAS:  # el esquema no admite listas vacías: los temas solo existen cuando haya clientes cargados
    ESQUEMA["properties"]["temas"] = {"type": "ARRAY", "items": {"type": "STRING", "enum": TEMAS},
                                      "description": "Temas de la lista que el documento toca de forma concreta."}
    ESQUEMA["required"].append("temas")

INSTRUCCIONES = """Eres analista legislativo para el sector empresarial panameño.
Recibes una ficha del Seguimiento Legislativo de la Asamblea Nacional de Panamá (anteproyecto o proyecto de ley)
con sus datos oficiales y, cuando existe, el texto presentado en PDF.

Evalúa el impacto para las empresas según estos criterios:

{criterios}

Reglas:
- Impacto por sector: evalúa cada sector por separado y sé estricto. Incluye un sector solo si la ley le cambia
  reglas que se le aplican directamente; lo indirecto es "bajo" o no va. Marca "alto" solo si de verdad cumple la
  definición. No infles la relevancia de temas que apenas rozan a las empresas.
- En disposiciones cita artículos concretos (número y qué cambian). No inventes artículos.
- Si no hay PDF, analiza solo con el título y dilo en el resumen ("Análisis basado solo en el título").
- Escribe en español, claro y directo, sin jerga innecesaria.
"""


class GeminiSaturado(Exception):
    """Gemini no respondió por carga o límite por minuto: se reintenta en la próxima hora."""


class CuotaAgotada(Exception):
    """Se acabó la cuota del día: se deja todo para la próxima corrida."""


def gemini_pedir(url, data=None, headers=None, method=None, timeout=300):
    cabeceras = {"x-goog-api-key": config("GEMINI_KEY")}
    cabeceras.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=cabeceras, method=method), timeout=timeout)


def gemini_subir(nombre, datos):
    inicio = gemini_pedir(
        f"{GEMINI}/upload/v1beta/files", method="POST",
        data=json.dumps({"file": {"display_name": nombre[:100]}}).encode(),
        headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                 "X-Goog-Upload-Header-Content-Length": str(len(datos)),
                 "X-Goog-Upload-Header-Content-Type": "application/pdf", "Content-Type": "application/json"},
    )
    req = urllib.request.Request(inicio.headers["X-Goog-Upload-URL"], data=datos, method="POST",
                                 headers={"X-Goog-Upload-Command": "upload, finalize", "X-Goog-Upload-Offset": "0"})
    archivo = json.load(urllib.request.urlopen(req, timeout=300))["file"]
    while archivo.get("state") == "PROCESSING":
        time.sleep(3)
        archivo = json.load(gemini_pedir(f"{GEMINI}/v1beta/{archivo['name']}"))
    if archivo.get("state") != "ACTIVE":
        raise RuntimeError(f"Gemini no pudo procesar {nombre}: {archivo.get('state')}")
    return archivo["uri"]


def leer_error_gemini(e):
    error = {"mensaje": "", "esperar": None, "diaria": False}
    cuerpo = e.read().decode(errors="replace")
    try:
        datos = json.loads(cuerpo)["error"]
    except (ValueError, KeyError, TypeError):
        error["mensaje"] = cuerpo
        return error
    error["mensaje"] = datos.get("message", "")
    for detalle in datos.get("details", []):
        m = re.match(r"([\d.]+)s", detalle.get("retryDelay", ""))
        if m:
            error["esperar"] = float(m.group(1)) + 2
        if any("PerDay" in v.get("quotaId", "") for v in detalle.get("violations", [])):
            error["diaria"] = True
    return error


def gemini_generar(cuerpo):
    """Llama a Gemini probando los modelos en orden; devuelve el JSON de la respuesta."""
    errores, solo_saturacion = [], True
    for modelo in MODELOS_GEMINI:
        for intento in range(3):
            try:
                r = json.load(gemini_pedir(f"{GEMINI}/v1beta/models/{modelo}:generateContent",
                                           data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}))
                resultado = json.loads(r["candidates"][0]["content"]["parts"][-1]["text"])
                resultado["modelo"] = modelo
                return resultado
            except urllib.error.HTTPError as e:
                error = leer_error_gemini(e)
                errores.append(f"{modelo}: HTTP {e.code} {error['mensaje'][:120]}")
                print(f"  {errores[-1]}")
                if e.code == 429 and error["diaria"]:
                    raise CuotaAgotada("se acabó la cuota diaria gratuita de Gemini")
                if e.code in (429, 500, 503):
                    if intento < 2:
                        time.sleep(min(error["esperar"] or 20 * (intento + 1), 90))
                        continue
                else:
                    solo_saturacion = False
                break
            except (KeyError, ValueError) as e:
                errores.append(f"{modelo}: respuesta inválida ({e})")
                solo_saturacion = False
                break
    if solo_saturacion:
        raise GeminiSaturado(" | ".join(errores[-3:]))
    raise RuntimeError(" | ".join(errores[-3:]))


def gemini_analizar(f, pdf):
    """Analiza una ficha (datos oficiales + historial + PDF si hay)."""
    criterios = open(ARCHIVO_CRITERIOS, encoding="utf-8").read()
    historial = "\n".join(f"- {ddmm(x['fecha'])}: {x['etapa']} ({x['comentario']})" for x in reversed(f.get("etapas") or []))
    datos = (f"{numero(f)} (ficha {f['ficha']})\nTítulo oficial: {f['titulo']}\nProponente: {f['proponente']}\n"
             f"Fecha de presentación: {ddmm(f['fecha'])}\nEtapa actual: {f['etapa']}\n"
             f"Comisión: {nombre_comision(f.get('comision'))}\nHistorial de etapas:\n{historial or '(sin historial)'}")
    partes = []
    if pdf and len(pdf) <= LIMITE_PDF_GEMINI:
        partes.append({"file_data": {"mime_type": "application/pdf", "file_uri": gemini_subir(f"ficha {f['ficha']}", pdf)}})
    else:
        datos += "\n\n(No hay texto en PDF: analiza solo con el título.)"
    partes.append({"text": datos})
    cuerpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCCIONES.format(criterios=criterios)}]},
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": ESQUEMA},
    }
    r = completar_impacto(gemini_generar(cuerpo))
    r["con_pdf"] = bool(partes and "file_data" in partes[0])
    r["fecha_analisis"] = hoy()
    return r


# ---------------------------------------------------------------- Google Drive (con rclone)


def drive_disponible():
    return bool(os.environ.get("DRIVE_TOKEN"))


def rclone(*argumentos, entrada=None):
    binario = os.path.join(CARPETA, "bin", "rclone")
    entorno = dict(os.environ, RCLONE_CONFIG_DRIVE_TYPE="drive", RCLONE_CONFIG_DRIVE_SCOPE="drive",
                   RCLONE_CONFIG_DRIVE_TOKEN=os.environ["DRIVE_TOKEN"],
                   RCLONE_CONFIG_DRIVE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID", ""),
                   RCLONE_CONFIG_DRIVE_CLIENT_SECRET=os.environ.get("GOOGLE_CLIENT_SECRET", ""))
    r = subprocess.run([binario if os.path.exists(binario) else "rclone", "-q", *argumentos],
                       env=entorno, capture_output=True, text=True, timeout=600, input=entrada)
    if r.returncode != 0:
        raise RuntimeError(f"rclone {argumentos[0]}: {r.stderr.strip()[-300:]}")
    return r.stdout


def nombre_seguro(texto, largo=90):
    limpio = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", texto or "").strip(" .")
    return re.sub(r"\s+", " ", limpio)[:largo].strip() or "Sin título"


def drive_ruta(*partes):
    return "drive:" + "/".join([DRIVE_RAIZ, *partes])


def drive_link_carpeta(ruta):
    padre, nombre = ruta.rsplit("/", 1)
    for item in json.loads(rclone("lsjson", "--dirs-only", padre)):
        if item["Name"] == nombre:
            return f"https://drive.google.com/drive/folders/{item['ID']}"
    return None


def drive_carpeta(estado, f, r):
    """Carpeta de la ficha: <raíz>/<comisión>/<nombre corto> (ficha N). Si la ficha cambió de comisión
    (p. ej. se asignó), la carpeta se muda."""
    comision = nombre_seguro(nombre_comision(f.get("comision")), 150)
    reg = estado["drive"].get(f["ficha"])
    if reg is None:
        reg = {"carpeta": nombre_seguro(f"{r['titulo_corto']} (ficha {f['ficha']})"), "comision": comision}
    elif reg["comision"] != comision:
        rclone("moveto", drive_ruta(reg["comision"], reg["carpeta"]), drive_ruta(comision, reg["carpeta"]))
        reg["comision"] = comision
    estado["drive"][f["ficha"]] = reg
    return drive_ruta(reg["comision"], reg["carpeta"])


def drive_guardar(estado, f, r, pdf):
    carpeta = drive_carpeta(estado, f, r)
    if pdf:
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "doc.pdf")
            open(local, "wb").write(pdf)
            rclone("copyto", local, f"{carpeta}/{nombre_seguro(f['fecha'] + ' - Texto presentado.pdf', 150)}")
    drive_guardar_md(carpeta, f, r)
    return drive_link_carpeta(carpeta)


def drive_guardar_md(carpeta, f, r):
    nombre = nombre_seguro(f"{hoy()} - {f['etapa']} - análisis.md", 150)
    rclone("rcat", f"{carpeta}/{nombre}", entrada=analisis_md(f, r))


def analisis_md(f, r):
    """El análisis completo en Markdown: queda en Drive para consulta (y para el futuro chatbot)."""
    lineas = [
        f"# {r['titulo']}", "",
        f"- **{numero(f)}** · ficha {f['ficha']}",
        f"- **Presentado:** {ddmm(f['fecha'])}",
        f"- **Proponentes:** {texto_proponentes(f, todos=True)}",
        f"- **Comisión:** {nombre_comision(f.get('comision'))}",
        f"- **Etapa:** {f['etapa']}",
        f"- **Impacto:** {r['impacto'].capitalize()}",
        f"- **Sectores:** {texto_sectores(r) or '—'}",
        f"- **Clientes posiblemente afectados:** {', '.join(clientes_afectados(r)) or '—'}",
        f"- **Texto oficial:** {seglegis.url_pdf(f['ficha'])}" if r.get("con_pdf") else "- **Texto oficial:** no disponible",
        "", "## Resumen", "", r["resumen"], "", "## Por qué este nivel de impacto", "", r["razon"],
    ]
    if r.get("impactos"):
        lineas += ["", "## Impacto por sector", ""] + [f"- **{x['sector']}** ({x['nivel']}): {x['razon']}" for x in r["impactos"]]
    lineas += ["", "## Posibles disposiciones de impacto", ""] + ([f"- {d}" for d in r["disposiciones"]] or ["- Ninguna identificada."])
    if f.get("etapas"):
        lineas += ["", "## Historial de etapas", ""] + [f"- {ddmm(x['fecha'])}: {x['etapa']} — {x['comentario'].capitalize()}"
                                                      for x in f["etapas"]]
    lineas += ["", f"_Analizado automáticamente con {r.get('modelo', 'Gemini')} el {ddmm(r.get('fecha_analisis', hoy()))}._", ""]
    return "\n".join(lineas)


# ---------------------------------------------------------------- Telegram


def e(texto):
    return html.escape(str(texto or ""))


def chats():
    return [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]


def telegram(metodo, campos, archivo=None):
    errores = []
    for chat in chats():
        try:
            telegram_a(chat, metodo, campos, archivo)
        except Exception as ex:
            errores.append(f"{chat}: {ex}")
            print(f"  Telegram {chat}: {ex}")
    if chats() and len(errores) == len(chats()):
        raise RuntimeError("no se pudo enviar a ningún chat de Telegram: " + " | ".join(errores))


def telegram_a(chat, metodo, campos, archivo=None):
    url = f"https://api.telegram.org/bot{config('TELEGRAM_TOKEN')}/{metodo}"
    campos = dict(campos, chat_id=chat)
    if archivo is None:
        datos, tipo = json.dumps(campos).encode(), "application/json"
    else:
        limite = uuid.uuid4().hex
        partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in campos.items()]
        nombre, contenido = archivo
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="document"; filename="{nombre}"\r\n'
                      "Content-Type: application/pdf\r\n\r\n".encode())
        partes += [contenido, f"\r\n--{limite}--\r\n".encode()]
        datos, tipo = b"".join(partes), f"multipart/form-data; boundary={limite}"
    urllib.request.urlopen(urllib.request.Request(url, data=datos, headers={"Content-Type": tipo}), timeout=300)


def lineas_impacto(r):
    lineas = [f"{ICONOS[r['impacto']]} <b>Impacto:</b> {e(r['impacto'].capitalize())}"]
    if r["impacto"] == "ninguno":
        lineas.append(f"<i>{e(r['razon'])}</i>")
        return lineas
    lineas.append(f"🏭 <b>Sectores impactados:</b> {e(texto_sectores(r) or '—')}")
    clientes = clientes_afectados(r)
    if clientes:
        lineas.append(f"👥 <b>Clientes:</b> {e(', '.join(clientes))}")
    return lineas


def texto_nueva(f, r, encabezado="🆕 Nuevo"):
    lineas = [
        f"{encabezado} · <b>{e(numero(f))}</b>",
        f"📜 {e(r['titulo'])}",
        f"📍 <b>Etapa:</b> {e(f['etapa'])} ({ddmm(f['fecha'])})",
        f"👤 <b>Proponente:</b> {e(texto_proponentes(f))}",
        f"🏛 <b>Comisión:</b> {e(nombre_comision(f.get('comision')))}",
    ] + lineas_impacto(r)
    if r["impacto"] != "ninguno":
        lineas += ["", e(r["resumen"]), "", f"<b>Por qué:</b> {e(r['razon'])}"]
        if r["disposiciones"]:
            lineas += ["", "<b>Posibles disposiciones de impacto:</b>"] + [f"• {e(d)}" for d in r["disposiciones"][:6]]
    return lineas


def pie(f, r):
    enlaces = []
    if r.get("drive"):
        enlaces.append(f'📁 <a href="{e(r["drive"])}">Drive</a>')
    if r.get("con_pdf"):
        enlaces.append(f'📄 <a href="{e(seglegis.url_pdf(f["ficha"]))}">Texto oficial</a>')
    return ["", " · ".join(enlaces)] if enlaces else []


def texto_cambio(f, r, antes, nuevas):
    """Aviso corto de avance: etapa anterior → nueva y lo que dice el historial."""
    lineas = [
        f"🔄 <b>Avanzó</b> · {e(numero(f))}",
        f"📜 {e(r['titulo'] if r else titulo(f['titulo']))}",
        f"📍 {e(antes)} → <b>{e(f['etapa'])}</b>" if antes and antes != f["etapa"] else f"📍 <b>{e(f['etapa'])}</b>",
    ]
    for x in reversed(nuevas[:4]):
        lineas.append(f"🗓 {ddmm(x['fecha'])}: {e(x['comentario'].capitalize())}")
    lineas.append(f"🏛 <b>Comisión:</b> {e(nombre_comision(f.get('comision')))}")
    if r:
        lineas += lineas_impacto(r)
    return lineas


def enviar(lineas, pdf=None, nombre_pdf="documento.pdf"):
    texto = "\n".join(lineas)
    if pdf and len(pdf) <= LIMITE_TELEGRAM and len(texto) <= 1024:
        telegram("sendDocument", {"caption": texto, "parse_mode": "HTML"}, (nombre_pdf, pdf))
        return
    telegram("sendMessage", {"text": texto[:4096], "parse_mode": "HTML", "disable_web_page_preview": True})
    if pdf and len(pdf) <= LIMITE_TELEGRAM:
        telegram("sendDocument", {}, (nombre_pdf, pdf))


# ---------------------------------------------------------------- detección de novedades


def clave_etapa(x):
    return f"{x['fecha']}|{x['etapa']}|{x['comentario']}"


def leer_asamblea(estado):
    """Recorre el Seguimiento Legislativo y devuelve (fichas actuales, novedades). En el mismo recorrido baja el
    historial de las fichas nuevas, de las que cambiaron de etapa, de las que están en tercer debate y de unas
    cuantas viejas que aún no lo tienen."""
    s = seglegis.Seguimiento()
    t = time.time()
    viejas = estado["fichas"]
    primera_vez = not viejas
    cupo = {"historial": 0 if primera_vez else ETAPAS_POR_CORRIDA}
    historiales = {}
    # sin historial todavía: primero las analizadas (van a la matriz) y las próximas rezagadas; esas no gastan cupo
    sin_historial = [f for f in viejas.values() if "etapas" not in f]
    prioridad = {f["ficha"] for f in sin_historial if "analisis" in f}
    prioridad |= {f["ficha"] for f in orden_rezagadas(viejas)[:2 * REZAGADAS_POR_CORRIDA]}

    def al_pasar(pagina, filas):
        for f in filas:
            v = viejas.get(f["ficha"])
            necesita = (not primera_vez and v is None) or (v and (v["etapa"] != f["etapa"] or f["etapa"] in VIGILAR_HISTORIAL))
            necesita = necesita or (v is not None and "etapas" not in v and f["ficha"] in prioridad)
            if not necesita and v is not None and "etapas" not in v and cupo["historial"] > 0:
                cupo["historial"] -= 1
                necesita = True
            if necesita and f["_boton_etapas"]:
                try:
                    historiales[f["ficha"]] = s.etapas_desde(pagina, f)
                except Exception as ex:
                    print(f"  historial de {f['ficha']}: {ex}")

    actuales = s.recorrer(al_pasar=al_pasar)
    print(f"Seguimiento Legislativo: {len(actuales)} fichas, {len(historiales)} historiales, {s.pedidos} pedidos "
          f"({round(time.time() - t)} s)")
    if len(actuales) < 0.8 * len(viejas):
        raise RuntimeError(f"la lista vino incompleta ({len(actuales)} de {len(viejas)}): no se toca el estado")

    # La comisión sale de recorrer el filtro de cada comisión (~100 s): cada HORAS_COMISIONES o si hay fichas nuevas.
    hay_nuevas = any(f["ficha"] not in viejas for f in actuales)
    ultima = estado.get("comisiones_revisadas", "")
    vencida = not ultima or datetime.datetime.now() - datetime.datetime.fromisoformat(ultima) > datetime.timedelta(hours=HORAS_COMISIONES)
    if hay_nuevas or vencida:
        t = time.time()
        comisiones = s.comisiones()
        estado["comisiones_revisadas"] = datetime.datetime.now().isoformat(timespec="seconds")
        print(f"comisiones: {len(comisiones)} fichas con comisión ({round(time.time() - t)} s)")
    else:
        comisiones = {k: v.get("comision", "") for k, v in viejas.items()}

    novedades = []
    for f in actuales:
        f = {k: v for k, v in f.items() if not k.startswith("_")}
        f["comision"] = comisiones.get(f["ficha"], "")
        v = viejas.get(f["ficha"])
        if f["ficha"] in historiales:
            f["etapas"] = historiales[f["ficha"]]
        elif v and "etapas" in v:
            f["etapas"] = v["etapas"]
        if v is None:
            if not primera_vez:
                novedades.append({"tipo": "nueva", "ficha": f["ficha"]})
        else:
            for k in ("analisis",):
                if k in v:
                    f[k] = v[k]
            vistas = {clave_etapa(x) for x in v.get("etapas") or []}
            nuevas = [x for x in f.get("etapas") or [] if clave_etapa(x) not in vistas] if "etapas" in v else []
            if v["etapa"] != f["etapa"] or nuevas:
                novedades.append({"tipo": "cambio", "ficha": f["ficha"], "antes": v["etapa"], "nuevas": nuevas})
        viejas[f["ficha"]] = f
    if primera_vez:
        estado["inicio"] = hoy()
        print(f"primera corrida: {len(actuales)} fichas registradas sin avisar")
    return novedades


# ---------------------------------------------------------------- procesamiento


def analizar_y_guardar(estado, f, s=None):
    """Baja el PDF, lo analiza y lo guarda en Drive. Devuelve (análisis, pdf)."""
    pdf = (s or seglegis.Seguimiento()).pdf(f["ficha"]) if f.get("tiene_documento", True) else None
    r = gemini_analizar(f, pdf)
    print(f"  {numero(f)} | {f['etapa']} | impacto: {r['impacto']} ({r['modelo']}){'' if r['con_pdf'] else ' | sin PDF'}")
    if drive_disponible():
        try:
            r["drive"] = drive_guardar(estado, f, r, pdf)
            print("  guardado en Drive")
        except Exception as ex:
            print(f"  Drive: {ex}")
    f["analisis"] = r
    return r, pdf


def procesar_novedad(estado, n, args):
    f = estado["fichas"][n["ficha"]]
    nombre_pdf = f"ficha-{f['ficha']}.pdf"
    if n["tipo"] == "nueva":
        print(f"→ nueva: {numero(f)} {f['titulo'][:90]}")
        r, pdf = analizar_y_guardar(estado, f)
        mostrar(args, texto_nueva(f, r) + pie(f, r), pdf, nombre_pdf)
        return
    print(f"→ cambio: {numero(f)} {n['antes']} → {f['etapa']} {f['titulo'][:70]}")
    r = f.get("analisis")
    if r is None:  # ficha vieja sin análisis: se analiza ahora para que el aviso traiga su impacto
        r, pdf = analizar_y_guardar(estado, f)
        mostrar(args, texto_nueva(f, r, encabezado=f"🔄 Avanzó a {f['etapa']}") + pie(f, r), pdf, nombre_pdf)
        return
    if drive_disponible() and r.get("drive"):
        try:  # el .md se rehace con el historial nuevo (y la carpeta se muda si cambió la comisión)
            drive_guardar_md(drive_carpeta(estado, f, r), f, r)
        except Exception as ex:
            print(f"  Drive: {ex}")
    mostrar(args, texto_cambio(f, r, n["antes"], n["nuevas"]) + pie(f, r))


def mostrar(args, lineas, pdf=None, nombre_pdf="documento.pdf"):
    if args.prueba:
        print("  ── mensaje ──\n  " + "\n  ".join(lineas).replace("\n", "\n  "))
        return
    enviar(lineas, pdf, nombre_pdf)
    print("  enviado a Telegram")


def orden_rezagadas(fichas):
    """Fichas activas sin análisis, de las más avanzadas a las menos (y las más nuevas primero)."""
    return sorted((f for f in fichas.values() if "analisis" not in f and f["etapa"] not in TERMINADAS),
                  key=lambda f: (AVANCE.get(f["etapa"], 0), f["fecha"]), reverse=True)


def rezagadas(estado, args, cupo):
    """Fichas activas sin análisis (de antes de que existiera el agente): se analizan sin avisar, las más nuevas primero."""
    candidatas = orden_rezagadas(estado["fichas"])
    print(f"rezagadas: {len(candidatas)} fichas activas sin análisis; hoy van {min(cupo, len(candidatas))}")
    for f in candidatas[:cupo]:
        print(f"→ rezagada: {numero(f)} {f['titulo'][:80]}")
        analizar_y_guardar(estado, f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prueba", action="store_true", help="no guarda estado ni envía a Telegram")
    parser.add_argument("--demo", help="analiza esta ficha y manda el aviso como si fuera nueva (no guarda estado)")
    args = parser.parse_args()
    cargar_env()
    estado = cargar_estado()

    if args.demo:
        if args.demo not in estado["fichas"]:
            sys.exit("Esa ficha no está en el estado: corre primero el agente una vez.")
        f = dict(estado["fichas"][args.demo])
        if "etapas" not in f:
            f["etapas"] = seglegis.Seguimiento().etapas_de(f["ficha"])
        r, pdf = analizar_y_guardar({"drive": {}, "fichas": {}}, f)
        mostrar(args, texto_nueva(f, r, encabezado="🧪 Ejemplo") + pie(f, r), pdf, f"ficha-{f['ficha']}.pdf")
        return

    novedades = leer_asamblea(estado)
    unificador(estado)
    pendientes = [p for p in estado["pendientes"].values()] + novedades
    estado["pendientes"] = {}
    print(f"{len(novedades)} novedades nuevas, {len(pendientes) - len(novedades)} pendientes de corridas anteriores")
    cuota = True
    for n in pendientes:
        clave = f"{n['tipo']}:{n['ficha']}"
        if not cuota:
            estado["pendientes"][clave] = n
            continue
        try:
            procesar_novedad(estado, n, args)
        except CuotaAgotada as ex:
            print(f"  {ex}: el resto queda para la próxima corrida")
            cuota = False
            estado["pendientes"][clave] = n
        except GeminiSaturado as ex:
            print(f"  Gemini saturado ({ex}): se reintenta la próxima hora")
            estado["pendientes"][clave] = n
        except Exception as ex:
            n["intentos"] = n.get("intentos", 0) + 1
            print(f"  error ({n['intentos']}/{MAX_INTENTOS}): {ex}")
            if n["intentos"] < MAX_INTENTOS:
                estado["pendientes"][clave] = n
            elif not args.prueba:
                telegram("sendMessage", {"text": f"⚠️ No se pudo procesar la ficha {n['ficha']}: {str(ex)[:300]}"})
    if cuota and not args.prueba and estado.get("inicio") != hoy():
        try:
            rezagadas(estado, args, REZAGADAS_POR_CORRIDA)
        except (CuotaAgotada, GeminiSaturado) as ex:
            print(f"  rezagadas: {ex}")
    if not args.prueba and base.disponible():
        try:
            base.sincronizar(estado, sys.modules[__name__])
            if drive_disponible():
                base.matriz_generar(estado, DRIVE_RAIZ)
        except Exception as ex:  # la base o la matriz fallan: se reintenta en la próxima corrida
            print(f"base/matriz: {ex}")
    estado["ultima_corrida"] = datetime.datetime.now().isoformat(timespec="seconds")
    if not args.prueba:
        guardar_estado(estado)


if __name__ == "__main__":
    main()
