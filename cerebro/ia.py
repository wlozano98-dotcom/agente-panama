"""Llamadas a Gemini para los agentes del cerebro (nivel gratuito).

En el nivel gratuito cada modelo tiene su propia cuota diaria: si uno la agota, se prueba el siguiente.
"""
import json
import os
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agente  # noqa: E402  (gemini_pedir, leer_error_gemini)

MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
castigados = {}  # modelo → hasta cuándo no se le pide nada (agotó su cuota): así no se espera en cada llamada


def generar_pdf_json(instrucciones, uri, contenido, esquema, modelos=MODELOS):
    """Como generar_json, con un PDF ya subido a Gemini (agente.gemini_subir) delante del texto."""
    return generar_json(instrucciones, contenido, esquema, modelos,
                        [{"file_data": {"mime_type": "application/pdf", "file_uri": uri}}])


def generar_json(instrucciones, contenido, esquema, modelos=MODELOS, adjuntos=(), temperatura=None):
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
    raise RuntimeError("Gemini no respondió: " + " | ".join(errores[-4:]))
