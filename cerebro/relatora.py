"""La Relatora de sesiones: transcripción de una sesión de comisión o del Pleno → Keylaw + declaraciones.

Uso: python3 cerebro/relatora.py <id de YouTube>   (antes: cerebro/transcribir.py en la Mac)
1. Guarda la transcripción en el cerebro (documento buscable) y la enlaza.
2. Gemini escribe un Keylaw por cada proyecto tratado (formato de los Keylaw de Keyword) y extrae lo que dijo cada
   diputado o invitado, con cita textual.
3. Las declaraciones de actores del directorio van a `declaraciones` (alimentan su Keyperfil); los Keylaw, a
   `productos` y a salidas/keylaw/. Decisión humana: si la oficina marcó la sesión para Keylaw (en la agenda o al
   pedir la transcripción), queda en borrador; si no, NO se escribe (Andrés, 2026-10-25: sin respuesta = solo
   guardar). La oficina puede pedirlo después desde el historial (tarea relatora/keylaw).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora  # noqa: E402
from cerebro import ia, normal  # noqa: E402
from db import d1  # noqa: E402

INSTRUCCIONES = """Eres la Relatora de Keyword, consultora de asuntos públicos en Panamá. Recibes la transcripción
automática (Whisper, con tiempos) de una sesión de la Asamblea Nacional y escribes el reporte Keylaw para clientes.

Formato del Keylaw (es un correo; respétalo):
Estimados,
Ponemos en su conocimiento que la Comisión de <nombre> de la Asamblea Nacional <qué hizo: inició / continuó con el
tratamiento / aprobó en primer debate…> del <Proyecto de Ley N.º … que …>.
<Invitados, si los hubo: "Durante la sesión se recibieron los aportes de…"; por cada uno, nombre y cargo o entidad, y
sus planteamientos en viñetas que empiezan con un sustantivo ("- La incorporación de…", "- Mayor control de…").>
Ante ello, los diputados hicieron las siguientes observaciones:
<Por cada diputado que intervino: "Nombre (Partido) planteó / cuestionó / advirtió / respaldó …" en una o dos
oraciones. Quien preside va primero: "Nombre, presidente de la Comisión (Partido) …".>
<Si se votó: resultado. Luego, qué sigue: "La Comisión continuará con el análisis…">
Los mantendremos informados sobre cualquier actualización relevante.
Saludos cordiales,

Reglas:
- Usa solo lo que está en la transcripción. Whisper se equivoca en nombres propios: corrígelos SOLO con la lista de
  miembros y proyectos que recibes; si no puedes identificar a quien habla, escribe su rol ("una diputada de la
  comisión", "un representante del MINSA") y no inventes el nombre.
- Partido entre paréntesis según la lista de miembros. Género (diputado/diputada) solo como lo indique la
  transcripción ("la diputada…", "el honorable diputado…"); si no, redacta sin marcarlo.
- Un Keylaw por cada proyecto tratado con sustancia. Si la sesión fue de otro tipo (citación, informe, presupuesto),
  un solo Keylaw con el asunto tratado.
- Registro ejecutivo, neutral, tercera persona, sin adjetivos de opinión, sin emojis.
- Declaraciones: lo más relevante que dijo cada persona identificada, con cita TEXTUAL de la transcripción (corrige
  solo errores evidentes de Whisper), el tema y su postura respecto del proyecto.
"""

ESQUEMA = {
    "type": "object",
    "properties": {
        "tipo_sesion": {"type": "string"},
        "fecha_sesion": {"type": "string", "description": "AAAA-MM-DD en que se realizó la sesión, según la transcripción"},
        "keylaws": {"type": "array", "items": {"type": "object", "properties": {
            "asunto": {"type": "string", "description": "Título del correo: 'Keylaw: Proyecto de Ley N.º … (hito)'"},
            "proyecto": {"type": "string", "description": "Número del proyecto o anteproyecto, o vacío"},
            "cuerpo": {"type": "string"}}, "required": ["asunto", "proyecto", "cuerpo"]}},
        "declaraciones": {"type": "array", "items": {"type": "object", "properties": {
            "nombre": {"type": "string"}, "rol": {"type": "string"}, "tema": {"type": "string"},
            "cita": {"type": "string"}, "postura": {"type": "string", "enum": ["a favor", "en contra", "matiza", "informa"]},
            "minuto": {"type": "string"}}, "required": ["nombre", "rol", "tema", "cita", "postura", "minuto"]}},
        "dudas": {"type": "array", "items": {"type": "string"},
                  "description": "Hablantes o nombres que no se pudieron identificar con seguridad"},
    },
    "required": ["tipo_sesion", "fecha_sesion", "keylaws", "declaraciones", "dudas"],
}


def comision_del_titulo(titulo):
    t = normal(titulo)
    for c in d1.consulta("SELECT id, nombre FROM entidades WHERE tipo = 'comision'"):
        claves = [p for p in normal(c["nombre"]).replace("COMISION DE ", "").split() if len(p) > 4][:2]
        if claves and all(k in t for k in claves):
            return c
    return None


def contexto(info):
    partes = [f"Sesión: {info['titulo']} · {info['fecha']} · {info['url']}"]
    com = comision_del_titulo(info["titulo"])
    if com:
        miembros = d1.consulta(
            "SELECT e.nombre, r.tipo, json_extract(e.datos, '$.partido') partido FROM relaciones r "
            "JOIN entidades e ON e.id = r.origen WHERE r.destino = ? AND r.tipo IN ('integra', 'preside')", [com["id"]])
        partes.append(f"Comisión: {com['nombre']}\nMiembros: " + "; ".join(
            f"{m['nombre']} ({m['partido'] or '?'}){' — preside' if m['tipo'] == 'preside' else ''}" for m in miembros))
        agenda = d1.consulta("SELECT fecha, descripcion FROM agenda WHERE fecha BETWEEN date(?, '-3 day') AND ? AND comision LIKE ?",
                             [info["fecha"], info["fecha"], "%" + com["nombre"].replace("Comisión de ", "")[:20] + "%"])
        if agenda:
            partes.append("Agenda oficial de la comisión (días previos al video): " + " | ".join(
                f"{a['fecha']}: {a['descripcion'][:600]}" for a in agenda))
    proyectos = d1.consulta(
        "SELECT p.proyecto, p.anteproyecto, COALESCE(p.titulo, p.titulo_oficial) t, p.etapa FROM agenda a "
        "JOIN agenda_fichas f ON f.agenda_id = a.id JOIN proyectos p ON p.ficha = f.ficha "
        "WHERE a.fecha BETWEEN date(?, '-3 day') AND ?", [info["fecha"], info["fecha"]])
    if proyectos:
        partes.append("Proyectos en la agenda de esos días: " + "; ".join(
            f"{'Proyecto ' + p['proyecto'] if p['proyecto'] else 'Anteproyecto ' + (p['anteproyecto'] or '')}: "
            f"{p['t'][:150]} ({p['etapa']})" for p in proyectos))
    return "\n".join(partes), com


def pedido(com, fecha):
    """¿La oficina marcó para Keylaw alguna sesión de esa comisión ese día?"""
    if not com:
        return False
    filas = d1.consulta("SELECT x.decision FROM agenda a JOIN decisiones x ON x.ref = 'agenda:' || a.id "
                        "WHERE a.fecha = ? AND a.comision LIKE ?",
                        [fecha, "%" + com["nombre"].replace("Comisión de ", "")[:20] + "%"])
    return any(f["decision"] == "keylaw" for f in filas)


def relatar(video, keylaw=None):
    ruta = os.path.join(cerebro.CARPETA, "salidas", "transcripciones", f"{video}.json")
    info = json.load(open(ruta, encoding="utf-8"))
    texto = open(ruta.replace(".json", ".txt"), encoding="utf-8").read()
    if len(texto) < 500:
        sys.exit(f"{video}: transcripción vacía o muy corta, no se reporta")
    ctx, com = contexto(info)
    r = ia.generar_json(INSTRUCCIONES + cerebro.ejemplos("Keylaw"), f"{ctx}\n\nTranscripción:\n{texto}", ESQUEMA)
    if re.match(r"\d{4}-\d{2}-\d{2}$", r.get("fecha_sesion") or ""):
        info["fecha"] = r["fecha_sesion"]  # el video se sube después de la sesión
    doc, _ = cerebro.guardar_documento("youtube_asamblea", video, texto, tipo="transcripcion",
                                       titulo=f"{info['titulo'].title()} ({info['fecha']})", url=info["url"],
                                       fecha=info["fecha"])
    cerebro.enlazar()
    print(f"{info['titulo']} ({info['fecha']}): {len(r['keylaws'])} Keylaw, {len(r['declaraciones'])} declaraciones "
          f"({r['modelo']})")

    # declaraciones → actores del directorio (por alias; las que no calzan quedan en el informe de dudas)
    alias = cerebro.cargar_alias()
    filas, sin_actor = [], []
    for x in r["declaraciones"]:
        actores = [e for e in cerebro.menciones_en(x["nombre"], alias) if e.startswith("persona:")]
        if len(actores) != 1:
            sin_actor.append(x["nombre"])
            continue
        filas.append([cerebro.huella(doc, actores[0], x["cita"]), actores[0], doc, info["fecha"], x["tema"], x["cita"],
                      x["postura"], cerebro.ahora()])
    d1.insertar_muchas("declaraciones", ["id", "entidad", "documento", "fecha", "tema", "cita", "postura", "creado"], filas)

    carpeta = os.path.join(cerebro.CARPETA, "salidas", "keylaw")
    os.makedirs(carpeta, exist_ok=True)
    if keylaw is None:
        keylaw = pedido(com, info["fecha"])
    r["pedido"] = keylaw
    productos = []
    for k in (r["keylaws"] if keylaw else []):  # sin pedido no se escribe Keylaw: la sesión solo se guarda
        pid = cerebro.huella("keylaw", video, k["asunto"])
        productos.append([pid, "keylaw", k["asunto"], com["id"] if com else None, k["cuerpo"], None, "borrador",
                          "relatora", json.dumps([doc]), cerebro.ahora(), cerebro.ahora()])
        nombre = re.sub(r"[^\w\-]+", "_", f"{info['fecha']}_{k['asunto']}")[:120]
        open(os.path.join(carpeta, nombre + ".md"), "w", encoding="utf-8").write(
            f"# {k['asunto']}\n\nFuente: {info['titulo']}, {info['fecha']} — {info['url']}\n\n{k['cuerpo']}\n")
        print(f"  {k['asunto']}")
    editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                     "fuentes", "creado", "actualizado"], productos)
    print(f"  declaraciones guardadas: {len(filas)}; sin actor del directorio: {sorted(set(sin_actor))}")
    if r["dudas"]:
        print("  dudas: " + "; ".join(r["dudas"]))
    return r


if __name__ == "__main__":
    cerebro.cargar_env()
    relatar(sys.argv[1], keylaw=True if "--keylaw" in sys.argv else None)
