"""Llamadas a Gemini para los agentes del cerebro (nivel gratuito).

En el nivel gratuito cada modelo tiene su propia cuota diaria: si uno la agota, se prueba el siguiente.
Respaldo LOCAL (Ollama en la PC de la oficina, 127.0.0.1:11434, gpt-oss:20b; lo agregó un Claude en la PC el
2026-11-19): SOLO para tareas internas que se pueden rehacer y nunca llegan al cliente (hoy: perfiles de actores).
Andrés, 2026-11-19: «solo para lo que no dañe la calidad del servicio». Cada llamada lo pide con local=True; los
reportes, avisos, Gaceta, reguladores, Corte, Paula y en vivo NUNCA lo usan. Sin PDF ni fotos. OLLAMA_MODELO="" lo
apaga. En la Mac no hay Ollama: el intento falla al instante.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agente  # noqa: E402  (gemini_pedir, leer_error_gemini)

MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
castigados = {}  # modelo → hasta cuándo no se le pide nada (agotó su cuota): así no se espera en cada llamada
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def generar_local(instrucciones, contenido, esquema, temperatura=None):
    """Respaldo local (Ollama): mismo contrato que generar_json. Lanza excepción si no hay Ollama o falla."""
    modelo = os.environ.get("OLLAMA_MODELO", "gpt-oss:20b")
    if not modelo:
        raise RuntimeError("respaldo local desactivado (OLLAMA_MODELO vacío)")
    # keep_alive 1m: gpt-oss ocupa ~12 GB de los 16 de la RTX 5080; se suelta pronto para Whisper y el worker de Ecuador
    cuerpo = {"model": modelo, "stream": False, "format": esquema, "keep_alive": "1m",
              "messages": [{"role": "system", "content": instrucciones}, {"role": "user", "content": contenido}],
              "options": {"num_ctx": 32768, **({"temperature": temperatura} if temperatura is not None else {})}}
    pedido = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(cuerpo).encode(),
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=600) as r:
        salida = json.loads(json.load(r)["message"]["content"])
    salida["modelo"] = f"local:{modelo}"
    return salida


def generar_pdf_json(instrucciones, uri, contenido, esquema, modelos=MODELOS):
    """Como generar_json, con un PDF ya subido a Gemini (agente.gemini_subir) delante del texto."""
    return generar_json(instrucciones, contenido, esquema, modelos,
                        [{"file_data": {"mime_type": "application/pdf", "file_uri": uri}}])


def generar_json(instrucciones, contenido, esquema, modelos=MODELOS, adjuntos=(), temperatura=None, local=False):
    """Devuelve el JSON que pide el esquema, más la clave 'modelo'. temperatura=0 para comparaciones repetibles."""
    cuerpo = {
        "systemInstruction": {"parts": [{"text": instrucciones}]},
        "contents": [{"role": "user", "parts": [*adjuntos, {"text": contenido}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": esquema,
                             **({"temperature": temperatura} if temperatura is not None else {})},
    }
    errores = []
    activos = [m for m in modelos if castigados.get(m, 0) < time.time()] or list(modelos)
    for modelo in activos:
        for intento in range(3):
            try:
                r = json.load(agente.gemini_pedir(f"{agente.GEMINI}/v1beta/models/{modelo}:generateContent",
                                                  data=json.dumps(cuerpo).encode(),
                                                  headers={"Content-Type": "application/json"}))
                salida = json.loads(r["candidates"][0]["content"]["parts"][-1]["text"])
                salida["modelo"] = modelo
                if errores:
                    print("  (Gemini) " + " | ".join(errores), file=sys.stderr, flush=True)
                return salida
            except urllib.error.HTTPError as e:
                error = agente.leer_error_gemini(e)
                errores.append(f"{modelo}: HTTP {e.code} {error['mensaje'][:100]}")
                if e.code == 429 and modelo != activos[-1]:
                    castigados[modelo] = time.time() + (3600 if error["diaria"] or "quota" in error["mensaje"] else 300)
                    break  # cuota: siguiente modelo, sin esperar
                if e.code in (429, 500, 503) and not error["diaria"] and intento < 2:
                    time.sleep(min(error["esperar"] or 20 * (intento + 1), 90))
                    continue
                break  # cuota diaria u otro error: siguiente modelo
            except (TimeoutError, urllib.error.URLError, KeyError, ValueError) as e:
                errores.append(f"{modelo}: {e}")
                break
    if local and not adjuntos:  # solo tareas internas que lo piden (local=True); PDF y fotos solo los entiende Gemini
        try:
            salida = generar_local(instrucciones, contenido, esquema, temperatura)
            print("  (Gemini) " + " | ".join(errores[-4:]) + f" → respondió {salida['modelo']}", file=sys.stderr, flush=True)
            return salida
        except Exception as e:  # noqa: BLE001  (sin Ollama, JSON roto, etc.: se informa el error de Gemini)
            errores.append(f"local: {e}")
    raise RuntimeError("Gemini no respondió: " + " | ".join(errores[-4:]))
