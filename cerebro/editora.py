"""Kiwi revisa (Andrés, 2026-10-26): el control de calidad es una función INTERNA de Kiwi, no un agente aparte.

El agente que escribe un reporte (Keylaw, Keymonitor, Keyeconomics, bola roja) se lo manda a Kiwi antes de guardarlo;
Kiwi lo compara con el texto de sus fuentes y lo devuelve corregido, y recién ahí queda en la oficina para que el
equipo lo vea y lo edite. Todos los agentes guardan sus reportes con guardar() (en lugar de insertar directo).
Kiwi corrige:
- dato: una cifra, fecha, nombre, cargo o número de norma que NO está en la fuente (posible invento) o está mal copiado;
- formato: lo que se aparta del formato Keyword de ese producto;
- redaccion: ortografía, concordancia, frases confusas, opinión.
Lo que cambió queda en productos.editora (JSON: veredicto y observaciones) y la oficina lo muestra arriba del editor
("Revisado por Kiwi"). Si Gemini falla, el reporte se guarda como lo escribió el agente y la oficina no muestra la marca.

Uso: python3 cerebro/editora.py <id de producto>      (vuelve a revisar uno ya guardado)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

REVISABLES = ("keylaw", "keymonitor", "keyeconomics", "bolaroja")
FORMATOS = {
    "keylaw": "Keylaw (reporte de una sesión de la Asamblea por correo): asunto con la comisión o el Pleno y el tema; "
              "abre con 'Estimados,' y qué sesión fue y cuándo; viñetas por tema con quién dijo qué; cierra con "
              "'Saludos cordiales,'. Neutral, sin opinión.",
    "keymonitor": "Keymonitor (norma publicada o de un regulador o de la Corte, por correo): asunto con el nombre corto de "
                  "la norma; 'Estimados,'; qué norma es (tipo, número, quién la emite, Gaceta y fecha) y qué dispone; "
                  "viñetas con lo principal; 'Saludos cordiales,'. Solo lo que dice la norma.",
    "keyeconomics": "Keyeconomics (cifra o norma económica, por correo): 'Estimados,' + 'Ponemos en su conocimiento que…' "
                    "con la institución que publica; viñetas con cifras (coma decimal, unidad y período); 'Saludos "
                    "cordiales,'. Descriptivo, sin opinión ni recomendaciones.",
    "bolaroja": "Bola roja (aviso corto al celular): primera línea '🔴 ' + título en MAYÚSCULAS; dos a seis viñetas "
                "'•  <Tema>: <qué se dijo o estableció>'; al final 'Saludos cordiales.'. Ejecutivo y neutral.",
}

REVISION = """Eres Kiwi, jefe de redacción de Keyword (consultora de asuntos públicos en Panamá). Un agente te manda un
reporte antes de que lo vea el equipo. Recibes el REPORTE, su FORMATO esperado y el TEXTO DE LAS FUENTES de donde sale
(transcripciones, normas, comunicados, cifras). Revísalo con rigor y corrígelo:
- dato: una cifra, fecha, nombre, cargo, institución o número de norma del reporte que NO aparece en las fuentes o
  aparece distinto (posible invento o error de copia): corrígelo con lo de la fuente o quítalo. Las transcripciones de
  Whisper pueden escribir mal los nombres: si el reporte corrige un nombre mal transcrito por el correcto, está bien.
  Si no hay fuentes, no toques los datos.
- formato: lo que se aparta del formato esperado (saludo, cierre, viñetas, asunto, mayúsculas del título).
- redaccion: ortografía, concordancia, frases confusas, opinión o adjetivos que un reporte neutral no lleva.
Devuelve "corregido": el reporte completo con los problemas arreglados, sin agregar información nueva ni cambiar lo que
está bien (conserva el formato del texto: **negrita**, viñetas "- " o "•"). Y en "observaciones", cada cambio que
hiciste: la frase original, qué estaba mal y cómo quedó. veredicto = "aprobado" si no tuviste que cambiar datos ni
formato; si no, "corregido"."""
ESQUEMA = {"type": "object", "properties": {
    "veredicto": {"type": "string", "enum": ["aprobado", "corregido"]},
    "observaciones": {"type": "array", "items": {"type": "object", "properties": {
        "tipo": {"type": "string", "enum": ["dato", "formato", "redaccion"]},
        "frase": {"type": "string"}, "problema": {"type": "string"}, "sugerencia": {"type": "string"}},
        "required": ["tipo", "frase", "problema", "sugerencia"]}},
    "corregido": {"type": "string"}},
    "required": ["veredicto", "observaciones", "corregido"]}


def columna():
    try:
        d1.consulta("ALTER TABLE productos ADD COLUMN editora TEXT")
    except Exception:
        pass  # ya existe


def fuentes_de(fuentes, largo=60000):
    if isinstance(fuentes, str):
        try:
            fuentes = json.loads(fuentes or "[]")
        except ValueError:
            fuentes = []
    textos = [t for t in (cerebro.texto_documento(i) for i in (fuentes if isinstance(fuentes, list) else []) if i) if t]
    return "\n\n-----\n\n".join(textos)[:largo]


def corregir(tipo, titulo, contenido, fuentes, texto_fuente=None):
    """Kiwi revisa un reporte: devuelve (texto corregido, revisión). Si Gemini falla, (el mismo texto, None).
    texto_fuente: el material que recibió el agente, cuando no está guardado como documento (pases pedidos en el chat)."""
    try:
        r = ia.generar_json(REVISION, f"FORMATO ESPERADO: {FORMATOS.get(tipo, tipo)}\n\nREPORTE:\nAsunto: {titulo}\n\n{contenido}"
                            f"\n\nTEXTO DE LAS FUENTES:\n{(texto_fuente or '')[:60000] or fuentes_de(fuentes) or '(sin fuentes guardadas)'}", ESQUEMA)
    except Exception as e:
        print(f"  Kiwi (revisión): {e}", flush=True)
        return contenido, None
    corregido = (r.pop("corregido", "") or "").strip() or contenido
    r.pop("modelo", None)
    r["fecha"] = cerebro.ahora()
    return corregido, r


def guardar(columnas, filas, modo="INSERT", texto_fuente=None):
    """Guarda productos pasando antes por la revisión de Kiwi (solo Keylaw, Keymonitor, Keyeconomics y bola roja).
    Devuelve {id: contenido final} para quien tenga que mandarlo (la bola roja va al chat)."""
    columna()
    columnas = list(columnas) + ([] if "editora" in columnas else ["editora"])
    finales, salida = {}, []
    for fila in filas:
        p = dict(zip(columnas, list(fila) + [None] * (len(columnas) - len(fila))))
        if p.get("tipo") in REVISABLES and p.get("contenido") and not p.get("editora"):
            p["contenido"], revision = corregir(p["tipo"], p.get("titulo") or "", p["contenido"], p.get("fuentes"), texto_fuente)
            p["editora"] = json.dumps(revision, ensure_ascii=False) if revision else None
        finales[p["id"]] = p.get("contenido")
        salida.append([p[c] for c in columnas])
    d1.insertar_muchas("productos", columnas, salida, modo=modo)
    return finales


def revisar(pid):
    """Vuelve a revisar un producto ya guardado (a mano) y lo reemplaza por la versión corregida."""
    columna()
    p = d1.consulta("SELECT id, tipo, titulo, contenido, fuentes FROM productos WHERE id = ?", [pid])
    if not p:
        raise SystemExit("No conozco ese producto")
    p = p[0]
    texto, r = corregir(p["tipo"], p["titulo"], p["contenido"], p["fuentes"])
    if not r:
        return "Kiwi no pudo revisarlo ahora"
    d1.consulta("UPDATE productos SET contenido = ?, editora = ? WHERE id = ?", [texto, json.dumps(r, ensure_ascii=False), pid])
    return f"{r['veredicto']} ({len(r['observaciones'])} cambios)"


if __name__ == "__main__":
    cerebro.cargar_env()
    print(revisar(sys.argv[1]))
