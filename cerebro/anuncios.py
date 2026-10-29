"""Memoria de anuncios (Andrés, 2026-10-25): no repetir lo ya avisado, sí avisar lo NUEVO de un tema conocido.

Ejemplo: el sábado el Presidente anuncia un impuesto a la banca → AVISO. El lunes lo repite → NO se avisa. El martes
da un dato nuevo (tarifa del 2 %) → AVISO solo de la novedad: "Nuevo dato sobre el impuesto a la banca: …".
Antes de mandar un aviso en caliente (Relatora en la Asamblea, Diego en entrevistas y noticieros), filtrar() le pasa a
Gemini el aviso propuesto y los anuncios de los últimos 45 días; Gemini dice qué puntos son nuevos, repetidos o
novedad, y reescribe el aviso solo con lo que hay que contar. Tabla `anuncios` (una fila por afirmación).

Uso: python3 cerebro/anuncios.py          (lista los anuncios recientes)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

DIAS = 45

FILTRO = """Eres la memoria de anuncios de Keyword (consultora de asuntos públicos en Panamá). Un agente quiere avisar
al chat del equipo lo que acaba de decir una autoridad. Recibes el AVISO PROPUESTO y los ANUNCIOS YA AVISADOS de los
últimos 45 días (id, fecha, actor, tema, afirmación, detalles). Separa el aviso en afirmaciones (un anuncio, una cifra,
una medida, una fecha, una postura) y clasifica cada una:
- nuevo: no se había avisado nada de ese tema por ese actor (u otro actor del mismo gobierno sobre la misma medida);
- repetido: ya se avisó lo mismo, aunque con otras palabras, o solo se recuerda ("como ya anunciamos…");
- novedad: el tema ya se avisó pero ahora hay un dato que cambia o completa (tarifa, fecha, a quién aplica, monto,
  marcha atrás). En "anterior" pon el id del anuncio que completa.
Después escribe "aviso": el texto final para el chat SOLO con lo nuevo y las novedades (las novedades empiezan con
"Nuevo dato sobre <tema>:" y pueden citar cuándo se anunció antes). Si todo es repetido, aviso vacío. Mismo tono
neutral y breve del aviso propuesto; no agregues nada que no esté en él."""
ESQUEMA = {"type": "object", "properties": {
    "puntos": {"type": "array", "items": {"type": "object", "properties": {
        "estado": {"type": "string", "enum": ["nuevo", "repetido", "novedad"]},
        "actor": {"type": "string", "description": "quién lo dijo, con cargo si se sabe"},
        "tema": {"type": "string", "description": "3 a 6 palabras, estable para el mismo asunto (p. ej. 'impuesto a la banca')"},
        "afirmacion": {"type": "string"},
        "detalles": {"type": "string", "description": "cifras, fechas y alcance, si hay"},
        "anterior": {"type": "string", "description": "id del anuncio que completa (solo si es novedad o repetido)"}},
        "required": ["estado", "actor", "tema", "afirmacion", "detalles", "anterior"]}},
    "aviso": {"type": "string"}}, "required": ["puntos", "aviso"]}


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS anuncios (id TEXT PRIMARY KEY, actor TEXT, tema TEXT, afirmacion TEXT, "
                "detalles TEXT, fecha TEXT, fuente TEXT, enlace TEXT, veces INTEGER DEFAULT 1, actualizado TEXT)")


def recientes(limite=150):
    crear_tabla()
    return d1.consulta("SELECT id, fecha, actor, tema, afirmacion, detalles FROM anuncios WHERE fecha >= date('now', ?) "
                       "ORDER BY fecha DESC LIMIT ?", [f"-{DIAS} days", limite])


def como_texto(filas):
    return "\n".join(f"{a['id']} | {a['fecha']} | {a['actor']} | {a['tema']} | {a['afirmacion']} | {a['detalles'] or ''}"
                     for a in filas) or "(ninguno todavía)"


def filtrar(aviso, fuente, enlace=""):
    """Devuelve el aviso que hay que mandar (vacío si todo estaba ya avisado) y guarda lo nuevo en la memoria. Si
    Gemini falla, devuelve el aviso tal cual: es mejor repetir que callar algo importante."""
    try:
        r = ia.generar_json(FILTRO, f"ANUNCIOS YA AVISADOS:\n{como_texto(recientes())}\n\nAVISO PROPUESTO:\n{aviso}", ESQUEMA)
    except Exception as e:
        print(f"  anuncios: {e}", flush=True)
        return aviso
    hoy = cerebro.ahora()[:10]
    for p in r["puntos"]:
        if p["estado"] == "repetido" and p["anterior"]:
            d1.consulta("UPDATE anuncios SET veces = veces + 1, actualizado = ? WHERE id = ?", [cerebro.ahora(), p["anterior"]])
        elif p["estado"] in ("nuevo", "novedad"):
            d1.consulta("INSERT OR IGNORE INTO anuncios (id, actor, tema, afirmacion, detalles, fecha, fuente, enlace, actualizado) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [cerebro.huella("anuncio", p["actor"], p["tema"], p["afirmacion"]), p["actor"], p["tema"], p["afirmacion"],
                         p["detalles"], hoy, fuente, enlace, cerebro.ahora()])
    if not r["aviso"].strip():
        print(f"  anuncios: todo ya avisado ({len(r['puntos'])} puntos repetidos)", flush=True)
    return r["aviso"].strip()


def de_actor(texto, limite=20):
    """Anuncios recientes que mencionan a alguien o un tema (para la bola roja: marcar "ya anunciado el sábado")."""
    crear_tabla()
    palabras = [w for w in cerebro.normal(texto).split() if len(w) > 3][:6]
    if not palabras:
        return []
    filas = recientes(400)
    return [a for a in filas if any(w in cerebro.normal(f"{a['actor']} {a['tema']}") for w in palabras)][:limite]


if __name__ == "__main__":
    cerebro.cargar_env()
    print(como_texto(recientes()))
