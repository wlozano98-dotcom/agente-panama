"""La Analista normativa: cada edición de la Gaceta Oficial → índice de normas; Keymonitor de las que elige la oficina.

Uso: python3 cerebro/normativa.py [número, p. ej. 30641_A]      lee una edición (sin número: todas las aún sin leer)
     python3 cerebro/normativa.py --redactar <id,id,…>         escribe el Keymonitor de esas normas
1. Sube el PDF de la edición (salidas/gaceta/, lo trae el Vigía) a Gemini, que lo lee entero, también las páginas
   escaneadas (no hace falta OCR aparte).
2. Gemini lista cada norma (quién la emite, tipo, número, de qué trata, sectores e impacto sugerido); van a la tabla
   `normas` y Telegram avisa qué salió.
3. Una persona elige en la oficina qué normas merecen Keymonitor (decisión humana); la mesa de la Mac llama a
   redactar(), que escribe cada Keymonitor con el tono de los ejemplos reales de Keyword y lo deja en borrador.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agente  # noqa: E402  (gemini_subir)
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from db import d1  # noqa: E402

CARPETA = os.path.join(cerebro.CARPETA, "salidas", "gaceta")
SECTORES = ["ALIMENTOS", "BANANERO", "CAMARONERO Y PESQUERO", "CEMENTERAS", "EXTRACTIVO", "FINANCIERO", "INDUSTRIAS",
            "OTROS", "PETRÓLEO", "SALUD", "SEGUROS", "TRANSPORTE", "TURISMO", "TODAS LAS EMPRESAS"]

INDICE = """Eres la Analista normativa de Keyword, consultora de asuntos públicos en Panamá. Recibes una edición completa
de la Gaceta Oficial de Panamá (PDF; algunas páginas son escaneos: léelas igual).

Lista TODAS las normas y actos publicados, en orden: quién los emite (ministerio, entidad, municipio, Asamblea, Corte),
tipo (Ley, Decreto Ejecutivo, Resolución, Resuelto, Acuerdo, Fallo, Aviso, Edicto…), número, fecha de expedición,
título o asunto en una línea, un nombre corto de 3 a 7 palabras para el archivo (p. ej. "Plan Nacional de Vivienda",
sin tipo ni número) y las páginas del PDF donde está el texto de la norma (sin las del sumario inicial). En "explicacion", para que una persona decida si vale un reporte,
cuenta en 3 a 5 oraciones qué establece o cambia, a quién aplica y desde cuándo (plazos, cifras, requisitos); para
actos individuales basta una oración.
Impacto sugerido para empresas privadas (clientes de una consultora): alto = crea, cambia o elimina obligaciones,
permisos, tributos, tarifas, requisitos o sanciones para un sector; medio = afecta a un sector de forma acotada
(reglamentos técnicos, procedimientos, plazos, autoridades que regulan un sector); bajo = interés general sin efecto
directo; ninguno = actos internos o individuales (nombramientos, licencias, jubilaciones, edictos, avisos de
particulares, personerías, concesiones a una persona). "economica" = true si la norma toca impuestos, tarifas,
aranceles, precios, presupuesto, deuda, salario mínimo, subsidios o incentivos fiscales (materia de un reporte
económico). Sectores: solo de la lista que recibes. Usa solo lo que dice la
Gaceta, con nombres y números exactos."""

ESQUEMA_INDICE = {
    "type": "object",
    "properties": {
        "fecha_edicion": {"type": "string", "description": "AAAA-MM-DD de la edición"},
        "normas": {"type": "array", "items": {"type": "object", "properties": {
            "entidad": {"type": "string"}, "tipo": {"type": "string"}, "numero": {"type": "string"},
            "fecha": {"type": "string"}, "titulo": {"type": "string"}, "nombre": {"type": "string"},
            "explicacion": {"type": "string"},
            "paginas": {"type": "string"},
            "sectores": {"type": "array", "items": {"type": "string", "enum": SECTORES}},
            "impacto": {"type": "string", "enum": ["alto", "medio", "bajo", "ninguno"]},
            "economica": {"type": "boolean"},
        }, "required": ["entidad", "tipo", "numero", "fecha", "titulo", "nombre", "explicacion", "paginas", "sectores", "impacto",
                        "economica"]}},
    },
    "required": ["fecha_edicion", "normas"],
}

REDACCION = """Eres la Analista normativa de Keyword, consultora de asuntos públicos en Panamá. Recibes una edición de
la Gaceta Oficial (PDF) y la lista de normas que la oficina eligió. Escribe un Keymonitor (correo para clientes
empresariales) por cada norma de la lista, leyéndola completa en el PDF.

Forma (igual que los ejemplos reales que siguen):
Estimados,
Ponemos en su conocimiento que <entidad con artículo: "la Asamblea Nacional", "el Ministerio de…">, mediante <tipo y
número>, <qué hizo: expidió / reformó / reglamentó / estableció…> <objeto>.
<Una o dos oraciones de contexto: a quién aplica.>
- <Cada disposición relevante en una viñeta que empieza con verbo en presente: "Exige…", "Establece…", "Prohíbe…".
  Concretas: cifras, plazos, requisitos, autoridades.>
<Si hay plazos de transición, un subtítulo con sus viñetas.>
Para su mejor referencia, adjuntamos <la ley / el decreto / la resolución>.
Saludos cordiales,

Reglas: solo lo que dice la Gaceta; registro ejecutivo, neutral, tercera persona, sin adjetivos de opinión ni emojis;
nombres y números exactos. Asunto: "Keymonitor: <título descriptivo y corto de lo que cambia>"."""

ESQUEMA_REDACCION = {"type": "object", "properties": {"keymonitor": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string", "description": "id de la norma, tal como viene en la lista"},
    "asunto": {"type": "string"}, "cuerpo": {"type": "string"}}, "required": ["id", "asunto", "cuerpo"]}}},
    "required": ["keymonitor"]}


def numero_de(titulo):
    m = re.match(r"Gaceta Oficial (\d{5})(?:-([A-Z]))?", titulo or "")
    return m.group(1) + ("_" + m.group(2) if m.group(2) else "") if m else None


def pendientes():
    """Ediciones de la Gaceta que ya están en el cerebro y en la Mac, pero que la Analista aún no leyó."""
    filas = d1.consulta("SELECT d.id, d.titulo, d.fecha, d.url FROM documentos d WHERE d.fuente = 'gaceta' "
                        "AND NOT EXISTS (SELECT 1 FROM normas n WHERE n.gaceta = d.id) ORDER BY d.fecha, d.titulo")
    return [(numero_de(f["titulo"]), f) for f in filas
            if numero_de(f["titulo"]) and os.path.exists(os.path.join(CARPETA, numero_de(f["titulo"]) + ".pdf"))]


def subir(numero):
    datos = open(os.path.join(CARPETA, numero + ".pdf"), "rb").read()
    return agente.gemini_subir(f"Gaceta {numero.replace('_', '-')}", datos)


def criterio_equipo(n=15):
    """Aprendizaje nivel 2: lo que el equipo ELIGIÓ para Keymonitor y lo que dejó pasar aunque el impacto sugerido
    era alto o medio. Sirve para calibrar el impacto sugerido de las próximas ediciones."""
    from cerebro import aprendizaje
    e = aprendizaje.estado()
    if not e["activo"]:  # apagado hasta el lanzamiento (Andrés, 2026-10-26)
        return ""
    try:
        elegidas = d1.consulta("SELECT tipo, numero, entidad, titulo, impacto FROM normas WHERE producto IS NOT NULL "
                               "AND creado >= strftime('%Y-%m-%dT%H:%M:%S', ?, '-5 hours') ORDER BY creado DESC LIMIT ?", [e["desde"], n])
        pasadas = d1.consulta("SELECT tipo, numero, entidad, titulo, impacto FROM normas WHERE producto IS NULL AND "
                              "impacto IN ('alto', 'medio') AND creado < datetime('now', '-2 days') "
                              "AND creado >= strftime('%Y-%m-%dT%H:%M:%S', ?, '-5 hours') ORDER BY creado DESC LIMIT ?", [e["desde"], n])
    except Exception:
        return ""
    if not elegidas and not pasadas:
        return ""
    linea = lambda x: f"- {x['tipo']} {x['numero']} ({x['entidad']}): {x['titulo']} [tu impacto sugerido fue: {x['impacto']}]"
    out = "\n\nCRITERIO DEL EQUIPO DE KEYWORD PANAMÁ (decisiones reales en ediciones anteriores; ajusta tu impacto sugerido a él):"
    if elegidas:
        out += "\nEl equipo ELIGIÓ hacer Keymonitor de:\n" + "\n".join(linea(x) for x in elegidas)
    if pasadas:
        out += "\nEl equipo NO hizo Keymonitor de (aunque sugeriste alto o medio):\n" + "\n".join(linea(x) for x in pasadas)
    return out


def leer(numero, doc=None):
    doc = doc or d1.consulta("SELECT id, titulo, fecha, url FROM documentos WHERE id = ?",
                             [cerebro.huella("gaceta", numero)])[0]
    edicion = numero.replace("_", "-")
    r = ia.generar_pdf_json(INDICE + criterio_equipo(), subir(numero), f"Gaceta Oficial N.º {edicion}. Sectores: {'; '.join(SECTORES)}",
                            ESQUEMA_INDICE)
    fecha = r["fecha_edicion"] if re.match(r"\d{4}-\d{2}-\d{2}$", r.get("fecha_edicion") or "") else doc["fecha"]
    normas = []
    for x in r["normas"]:
        nid = cerebro.huella(doc["id"], x["tipo"], x["numero"], x["entidad"], x["titulo"])
        normas.append([nid, doc["id"], edicion, fecha, x["entidad"], x["tipo"], x["numero"], x["titulo"], x["explicacion"],
                       json.dumps(x["sectores"], ensure_ascii=False), x["impacto"], x["paginas"], None, cerebro.ahora(),
                       x["nombre"], 1 if x.get("economica") else 0])
    try:  # columna nueva (pases a Tomás, 2026-10-25)
        d1.consulta("ALTER TABLE normas ADD COLUMN economica INTEGER")
    except Exception:
        pass
    d1.insertar_muchas("normas", ["id", "gaceta", "edicion", "fecha", "entidad", "tipo", "numero", "titulo", "resumen",
                                  "sectores", "impacto", "paginas", "producto", "creado", "nombre", "economica"], normas)
    print(f"Gaceta {edicion} ({fecha}): {len(normas)} normas ({r['modelo']})", flush=True)
    try:  # un PDF por norma, con el nombre de Keyword, en Drive
        from cerebro import partir
        partir.partir(numero)
    except Exception as e:
        print(f"  partir: {e}", flush=True)
    pases = []
    try:  # Inés pasa lo económico a Tomás y lo de impacto alto a Diego (cerebro/pases.py)
        from cerebro import pases as pases_mod
        pases = pases_mod.de_la_gaceta([n[0] for n in normas])
    except Exception as e:
        print(f"  pases: {e}", flush=True)
    avisar(edicion, fecha, r["normas"], pases)
    return {"normas": len(normas)}


def avisar(edicion, fecha, normas, pases=()):
    """Telegram: salió una edición, estos son sus temas; la oficina elige cuáles van a Keymonitor."""
    importantes = [n for n in normas if n["impacto"] in ("alto", "medio")]
    lineas = [f"📰 Gaceta Oficial {edicion} ({fecha[8:10]}/{fecha[5:7]}): {len(normas)} normas, "
              f"{len(importantes)} con posible impacto."]
    for n in importantes[:12]:
        lineas.append(f"{'🔴' if n['impacto'] == 'alto' else '🟠'} {n['tipo']} {n['numero']} ({n['entidad']}): {n['titulo']}")
    otras = len(normas) - len(importantes)
    if otras:
        lineas.append(f"Y {otras} de impacto bajo o ninguno (avisos, edictos, nombramientos).")
    lineas += list(pases)
    lineas.append("Elige en la oficina (mesa de Inés) cuáles van a Keymonitor.")
    try:
        cerebro.telegram("\n".join(lineas), destino="gaceta", agente="normativa",
                         ref=f"gaceta:{edicion}")
    except Exception as e:
        print(f"  Telegram: {e}", flush=True)


def redactar(ids):
    """Keymonitor de las normas elegidas por la oficina (agrupadas por edición: un PDF por llamada)."""
    marcas = ",".join("?" * len(ids))
    normas = d1.consulta(f"SELECT n.*, d.titulo AS gaceta_titulo, d.url FROM normas n JOIN documentos d ON d.id = n.gaceta "
                         f"WHERE n.id IN ({marcas})", list(ids))
    hechos = []
    for gid in sorted({n["gaceta"] for n in normas}):
        grupo = [n for n in normas if n["gaceta"] == gid and not n["producto"]]
        if not grupo:
            continue
        numero = numero_de(grupo[0]["gaceta_titulo"])
        lista = "\n".join(f"- id {n['id']}: {n['tipo']} {n['numero']} de {n['entidad']} — {n['titulo']} (páginas {n['paginas']})"
                          for n in grupo)
        r = ia.generar_pdf_json(REDACCION + cerebro.ejemplos("Keymonitor"), subir(numero),
                                f"Gaceta Oficial N.º {numero.replace('_', '-')}. Normas elegidas:\n{lista}", ESQUEMA_REDACCION)
        por_id = {n["id"]: n for n in grupo}
        productos = []
        for k in r["keymonitor"]:
            n = por_id.get(k["id"])
            if not n:
                continue
            pid = cerebro.huella("keymonitor", n["id"])
            ndoc, _ = cerebro.guardar_documento(
                "gaceta_norma", n["id"], f"{n['entidad']}. {n['tipo']} {n['numero']} de {n['fecha']}. {n['titulo']}.\n"
                                         f"{n['resumen']}\n\n{k['cuerpo']}",
                tipo=n["tipo"].lower(), titulo=f"{n['tipo']} {n['numero']} ({n['entidad']})", url=n["url"],
                fecha=n["fecha"], resumen=n["resumen"])
            productos.append([pid, "keymonitor", k["asunto"], None, k["cuerpo"], None, "borrador", "normativa",
                              json.dumps([ndoc, gid]), cerebro.ahora(), cerebro.ahora()])
            d1.consulta("UPDATE normas SET producto = ? WHERE id = ?", [pid, n["id"]])
            hechos.append(k["asunto"])
        editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                         "fuentes", "creado", "actualizado"], productos)
        print(f"Gaceta {numero}: {len(productos)} Keymonitor ({r['modelo']})", flush=True)
    if hechos:
        cerebro.enlazar()
        cerebro.telegram("📝 Keymonitor listos para revisar en la oficina:\n" + "\n".join("• " + h for h in hechos), destino="gaceta")
    return f"{len(hechos)} Keymonitor en borrador"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "--redactar":
        print(redactar(sys.argv[2].split(",")))
    elif len(sys.argv) > 1:
        leer(sys.argv[1])
    else:
        for numero, doc in pendientes():
            leer(numero, doc)
