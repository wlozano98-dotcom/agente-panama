"""Pases entre agentes (Andrés, 2026-10-25): un agente detecta algo y se lo pasa a otro, a la vista en el chat.

Uso: python3 cerebro/pases.py <de> <para> <producto> <id de la norma>     (un pase a mano, para probar)
Inés (Gaceta), Mateo (reguladores) y Elena (Corte) → Tomás (Keyeconomics de lo que tiene efecto económico) y → Diego
(bola roja de lo de impacto alto). Cada pase es una fila en `pases` y una tarea para la mesa del que lo recibe; así se
ve en la oficina y la mesa de la Mac lo hace. El Keyeconomics (correo) queda en la plataforma y el chat solo avisa que
está para revisión; la bola roja sí llega completa al chat para revisión (antes la limpia la Editora).
El origen del pase dice de dónde sale: el id de una norma (Gaceta), "regulatoria:<id>", "judicial:<id>" o "chat:<id>"
(lo pidió el equipo respondiendo a un mensaje en el grupo: cerebro/chat.py; el texto va en pases.texto).
"""
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from db import d1  # noqa: E402

NOMBRES = {"normativa": "Inés", "cifras": "Tomás", "entrevistas": "Diego", "regulatoria": "Mateo", "judicial": "Elena",
           "chat": "el equipo"}
TAREA = {("cifras", "keyeconomics"): "keyeconomics_norma", ("entrevistas", "bolaroja"): "bola_norma"}

KEYECO_NORMA = """Eres Tomás, economista de Keyword (consultora de asuntos públicos) en Panamá. Un colega te pasó una
norma, resolución, fallo o noticia con efecto económico (impuestos, tarifas, aranceles, precios, presupuesto, deuda,
salario mínimo, subsidios o incentivos). Escribe el Keyeconomics: el correo a clientes que lo cuenta. DESCRIPTIVO:
solo lo que dice la fuente, sin opinión ni recomendaciones. Estructura de los ejemplos reales:
Estimados,
Ponemos en su conocimiento que, a través de <tipo y número de la norma>, <quién> dispuso <qué>.
<desde cuándo aplica, a quién y con qué cifras, en una o dos oraciones>
Si la norma enumera actividades, bienes o requisitos, ponlos como viñetas "- ".
Para su referencia, adjuntamos <la norma> en mención.
Saludos cordiales,
Nombres, números, cifras y fechas exactos, con coma decimal. Asunto en tipo título, sin el número de la norma salvo
que sea lo que la identifica (p. ej. "Reducción del ITBMS para Actividades Turísticas en el Feriado de Noviembre")."""
BOLA_NORMA = """Eres Diego, de Keyword, consultora de asuntos públicos en Panamá. Un colega te pasó algo de impacto alto
(una norma de la Gaceta, una resolución de un regulador, un fallo de la Corte, una noticia o lo que dijo una
autoridad). Escribe la "bola roja": el aviso corto que llega al celular de los clientes. Forma de los ejemplos reales:
primera línea "🔴 " + título en mayúsculas (qué es y qué hace, p. ej. "🔴 DECRETO EJECUTIVO N.º 45: REBAJA DEL ITBMS AL
TURISMO"); luego dos a cuatro viñetas "•  <Tema>: <qué establece o qué se dijo>", con cifras, fechas y a quién aplica;
al final "Saludos cordiales." Registro ejecutivo, neutral, sin opinión. Solo lo que dice la fuente. Si recibes
ANUNCIOS PREVIOS y algo ya se había anunciado, puedes marcarlo "(ya anunciado el <día>)"."""
ESQUEMA = {"type": "object", "properties": {"asunto": {"type": "string"}, "cuerpo": {"type": "string"}},
           "required": ["asunto", "cuerpo"]}


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS pases (id TEXT PRIMARY KEY, de TEXT, para TEXT, producto TEXT, origen TEXT, "
                "titulo TEXT, estado TEXT, resultado TEXT, creado TEXT)")
    try:
        d1.consulta("ALTER TABLE pases ADD COLUMN texto TEXT")  # lo que mandó el chat (pases pedidos desde el grupo)
    except Exception:
        pass


def pasar(de, para, producto, norma_id, titulo, texto=None, tarea=True):
    """Deja el pase y la tarea para la mesa del que lo recibe. Devuelve el id del pase (o None si ya se había pasado)."""
    crear_tabla()
    pid = cerebro.huella("pase", de, para, producto, norma_id)
    if d1.consulta("SELECT 1 FROM pases WHERE id = ?", [pid]):
        return None
    d1.consulta("INSERT INTO pases (id, de, para, producto, origen, titulo, estado, creado, texto) VALUES (?, ?, ?, ?, ?, ?, "
                "'pendiente', ?, ?)", [pid, de, para, producto, norma_id, titulo[:300], cerebro.ahora(), texto])
    if not tarea:
        return pid
    d1.consulta("INSERT INTO tareas (id, agente, tipo, ref, estado, detalle, creado) VALUES (?, ?, ?, ?, 'pendiente', ?, ?)",
                [str(uuid.uuid4()), para, TAREA[(para, producto)], pid, f"Pase de {NOMBRES[de]}: {titulo[:200]}",
                 cerebro.ahora()])
    return pid


def norma(nid):
    n = d1.consulta("SELECT * FROM normas WHERE id = ?", [nid])
    if not n:
        raise SystemExit("No conozco esa norma")
    n = n[0]
    doc = cerebro.huella("gaceta_texto", nid)
    texto = cerebro.texto_documento(doc) if d1.consulta("SELECT 1 FROM documentos WHERE id = ?", [doc]) else ""
    return n, (texto or f"{n['titulo']}\n\n{n['resumen'] or ''}"), (doc if texto else n["gaceta"])


def fuente(p):
    """(datos para el agente, documento de la fuente) según de dónde sale el pase."""
    tipo, _, ref = p["origen"].partition(":") if ":" in p["origen"] else ("norma", "", p["origen"])
    if tipo == "norma":
        n, texto, doc = norma(ref)
        return (f"{n['tipo']} {n['numero']} · {n['entidad']} · Gaceta Oficial {n['edicion']} del {n['fecha']}\n"
                f"Título: {n['titulo']}\n\nTexto:\n{texto[:40000]}"), doc
    if tipo in ("regulatoria", "judicial"):
        x = d1.consulta(f"SELECT * FROM {'regulatorias' if tipo == 'regulatoria' else 'judiciales'} WHERE id = ?", [ref])
        if not x:
            raise SystemExit("No encuentro el origen del pase")
        x = x[0]
        texto = cerebro.texto_documento(x["documento"]) if x.get("documento") else ""
        quien = x.get("ente") or f"Corte Suprema de Justicia · {x.get('tribunal') or ''}"
        return (f"{quien} · {x['fecha']} · {x['titulo']}\nNombre: {x['nombre']}\nResumen del analista: {x['resumen']}\n"
                f"Enlace: {x['url']}\n\nTexto:\n{texto[:40000]}"), x.get("documento")
    return p["texto"] or p["titulo"], None  # chat: lo que mandó el equipo (mensaje, nota enlazada, cerebro)


def hacer(pase_id):
    """La mesa del que recibe el pase lo hace: Keyeconomics en borrador o bola roja al chat."""
    p = d1.consulta("SELECT * FROM pases WHERE id = ?", [pase_id])[0]
    datos, doc = fuente(p)
    de = NOMBRES.get(p["de"], p["de"])
    ref = "pase:" + pase_id
    if p["producto"] == "keyeconomics":
        from cerebro import cifras
        r = ia.generar_json(KEYECO_NORMA + cifras.ejemplos(r"IVA|Arancel|ISD|Tasa_de_Seguridad|Salario", 4), datos, ESQUEMA)
        asunto = "Keyeconomics: " + re.sub(r"^Keyeconomics:\s*", "", r["asunto"]).strip()
        prod = cerebro.huella("keyeconomics", p["origen"])
        editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                         "fuentes", "creado", "actualizado"],
                           [[prod, "keyeconomics", asunto, None, r["cuerpo"], None, "borrador", "cifras",
                             json.dumps([doc] if doc else []), cerebro.ahora(), cerebro.ahora()]], texto_fuente=datos)
        cerebro.telegram(f"📊 Tomás: el Keyeconomics «{asunto[14:]}» (pase de {de}) ya está en la plataforma para revisión.",
                         destino="general", ref=ref, agente="cifras")
    else:
        from cerebro import anuncios
        previos = anuncios.como_texto(anuncios.de_actor(datos[:400]))
        r = ia.generar_json(BOLA_NORMA + cerebro.ejemplos("BolaRoja", 3), f"{datos}\n\nANUNCIOS PREVIOS:\n{previos}", ESQUEMA)
        asunto = re.sub(r"^🔴\s*", "", r["asunto"]).strip()
        cuerpo = r["cuerpo"] if r["cuerpo"].lstrip().startswith("🔴") else f"🔴 {asunto}\n\n{r['cuerpo']}"
        # sale directo al chat: antes Kiwi la revisa contra la fuente (quita lo que no está y arregla el formato)
        prod = cerebro.huella("bolaroja", p["origen"])
        cuerpo = editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                  "fuentes", "creado", "actualizado"],
                                 [[prod, "bolaroja", "🔴 " + asunto, None, cuerpo, None, "borrador", "entrevistas",
                                   json.dumps([doc] if doc else []), cerebro.ahora(), cerebro.ahora()]],
                                 texto_fuente=datos)[prod]
        cerebro.telegram(f"Diego · bola roja para revisión (pase de {de}):\n\n{cuerpo}", destino="general", ref=ref, agente="entrevistas")
    d1.consulta("UPDATE pases SET estado = 'hecho', resultado = ? WHERE id = ?", [prod, pase_id])
    return f"{p['producto']} listo"


def de_entes(de, items):
    """Mateo (reguladores) y Elena (Corte): los mismos pases que Inés. items: [{id, nombre, impacto, economica}].
    Devuelve las líneas para su aviso en el chat."""
    tipo = {"regulatoria": "regulatoria", "judicial": "judicial"}[de]
    lineas = []
    for x in items:
        a = []
        origen = f"{tipo}:{x['id']}"
        if x.get("economica") and x["impacto"] in ("alto", "medio") and pasar(de, "cifras", "keyeconomics", origen, x["nombre"]):
            a.append("a Tomás para el Keyeconomics (correo)")
        if x["impacto"] == "alto" and pasar(de, "entrevistas", "bolaroja", origen, x["nombre"]):
            a.append("a Diego para la bola roja (celular)")
        if a:
            lineas.append(f"➡️ {x['nombre']}: se lo pasé " + " y ".join(a) + ".")
    return lineas


def del_chat(producto, texto, titulo):
    """El equipo lo pidió en el grupo ("pásenme la bola roja de esto"): el pase se hace en el momento (sin esperar a la
    mesa) y lo que sale llega al mismo chat. Devuelve el id del pase."""
    para = "cifras" if producto == "keyeconomics" else "entrevistas"
    pid = pasar("chat", para, producto, "chat:" + cerebro.huella(texto[:3000], cerebro.ahora()), titulo, texto[:60000], tarea=False)
    hacer(pid)
    return pid


def de_la_gaceta(normas_ids):
    """Inés: decide los pases de las normas recién leídas. Devuelve las líneas para su aviso en el chat."""
    lineas = []
    for nid in normas_ids:
        n = d1.consulta("SELECT id, tipo, numero, titulo, impacto, economica FROM normas WHERE id = ?", [nid])
        if not n:
            continue
        n = n[0]
        nombre = f"{n['tipo']} {n['numero']}".strip()
        a = []
        if n["economica"] and n["impacto"] in ("alto", "medio") and pasar("normativa", "cifras", "keyeconomics", nid, f"{nombre}: {n['titulo']}"):
            a.append("a Tomás para el Keyeconomics (correo)")
        if n["impacto"] == "alto" and pasar("normativa", "entrevistas", "bolaroja", nid, f"{nombre}: {n['titulo']}"):
            a.append("a Diego para la bola roja (celular)")
        if a:
            lineas.append(f"➡️ {nombre}: se lo pasé " + " y ".join(a) + ".")
    return lineas


if __name__ == "__main__":
    cerebro.cargar_env()
    de, para, producto, nid = sys.argv[1:5]
    n, _, _ = norma(nid)
    pid = pasar(de, para, producto, nid, f"{n['tipo']} {n['numero']}: {n['titulo']}")
    print(hacer(pid) if pid else "Ese pase ya estaba hecho")
