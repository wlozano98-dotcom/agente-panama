"""El Perfilador: arma y mantiene la ficha de cada actor con lo que el cerebro sabe de él.

Uso: python3 cerebro/perfilador.py <id de entidad o parte del nombre> [--diseno]
Junta todo lo del cerebro sobre el actor (directorio, relaciones, proyectos presentados, menciones en documentos y
declaraciones), pide a Gemini el expediente con las secciones del Keyperfil y lo guarda en `expedientes`. Gemini solo
puede usar lo que recibe: lo que no está en las fuentes queda fuera (nunca se completa por inferencia).
Con --diseno, la Diseñadora arma además el Keyperfil en PDF y se publica: Drive (<raíz>/Keyperfil/, nombre de Keyword
"AAMMDD Keyperfil Nombre.pdf") y `productos` (tipo keyperfil, uno por actor), para abrirlo desde la mesa del Perfilador.
--publicar sube los PDF que ya estén en salidas/keyperfil/ (el más nuevo de cada actor).
"""
import json
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

INSTRUCCIONES = """Eres el Perfilador de Keyword, consultora de asuntos públicos en Panamá. Armas la ficha de un actor
público (Keyperfil) para clientes empresariales: clara, rigurosa, neutral, sin adjetivos de opinión.

Reglas:
- Usa SOLO la información del contexto. No completes con conocimiento propio ni supongas nada.
- Si un dato está marcado [NV] (no verificado) en el contexto, no lo uses.
- Estudios y experiencia: solo los que aparezcan explícitamente. Si no hay, deja la lista vacía.
- Experiencia: del cargo más reciente al más antiguo; "periodo" como aparezca ("Desde 2024", "2019-2022", "2026").
- Datos de interés: 4 a 8 viñetas de una o dos oraciones, lo más útil para una empresa (qué decide, qué impulsa,
  con quién se alinea, qué proyectos presentó y en qué etapa están, qué ha dicho). Cada viñeta con su fuente
  (el número entre corchetes del contexto).
- Posturas: solo si el contexto trae una declaración o un proyecto que la muestre; tema + postura en una oración.
- Español de Panamá, registro ejecutivo, tercera persona. Sin emojis ni exclamaciones.
- Género: usa la forma (diputado/diputada, ministro/ministra) solo si aparece así en el contexto para esta persona.
  Si no aparece, redacta sin marcar género ("integra la Asamblea", "preside la comisión", "titular del ministerio").
"""

ESQUEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "Dos o tres líneas: quién es y por qué importa hoy"},
        "estudios": {"type": "array", "items": {"type": "string"}},
        "experiencia": {"type": "array", "items": {"type": "object", "properties": {
            "periodo": {"type": "string"}, "cargo": {"type": "string"}}, "required": ["periodo", "cargo"]}},
        "datos_interes": {"type": "array", "items": {"type": "object", "properties": {
            "texto": {"type": "string"}, "fuentes": {"type": "array", "items": {"type": "integer"}}},
            "required": ["texto", "fuentes"]}},
        "posturas": {"type": "array", "items": {"type": "object", "properties": {
            "tema": {"type": "string"}, "postura": {"type": "string"}, "fuentes": {"type": "array", "items": {"type": "integer"}}},
            "required": ["tema", "postura", "fuentes"]}},
        "vacios": {"type": "array", "items": {"type": "string"},
                   "description": "Qué falta saber de este actor (para pedirlo a la investigación)"},
    },
    "required": ["resumen", "estudios", "experiencia", "datos_interes", "posturas", "vacios"],
}


def encontrar(consulta):
    if consulta.startswith(("persona:", "institucion:")):
        filas = d1.consulta("SELECT * FROM entidades WHERE id = ?", [consulta])
    else:
        filas = d1.consulta("SELECT * FROM entidades WHERE tipo = 'persona' AND nombre LIKE ? LIMIT 5", [f"%{consulta}%"])
    if len(filas) != 1:
        sys.exit(f"'{consulta}': {len(filas)} coincidencias {[f['nombre'] for f in filas]}")
    return filas[0]


def contexto(e):
    """Texto con todo lo que el cerebro sabe del actor, con fuentes numeradas [1], [2]… y la lista de fuentes."""
    fuentes, partes = [], []

    def fuente(descripcion):
        fuentes.append(descripcion)
        return len(fuentes)

    datos = json.loads(e["datos"] or "{}")
    n = fuente(f"Directorio de actores ({e['fuente'] or 'cerebro'})")
    partes.append(f"[{n}] {e['nombre']} — {e['cargo'] or ''}\nDatos: {json.dumps(datos, ensure_ascii=False)}\n"
                  f"Perfil: {e['perfil'] or ''}")
    rel = d1.consulta(
        "SELECT r.tipo, r.detalle, d.nombre FROM relaciones r JOIN entidades d ON d.id = r.destino WHERE r.origen = ? "
        "UNION ALL SELECT r.tipo || ' (inversa)', r.detalle, o.nombre FROM relaciones r JOIN entidades o ON o.id = r.origen "
        "WHERE r.destino = ?", [e["id"], e["id"]])
    if rel:
        partes.append(f"[{n}] Relaciones: " + "; ".join(f"{r['tipo']} {r['nombre']}" + (f" ({r['detalle']})" if r["detalle"] else "")
                                                      for r in rel))
    if datos.get("nombre_en_proyectos"):
        proy = d1.consulta(
            "SELECT p.ficha, p.proyecto, p.anteproyecto, COALESCE(p.titulo, p.titulo_oficial) t, p.etapa, p.impacto, "
            "p.fecha_presentacion, x.principal FROM proponentes x JOIN proyectos p ON p.ficha = x.ficha "
            "WHERE x.nombre = ? ORDER BY p.fecha_presentacion DESC", [datos["nombre_en_proyectos"]])
        if proy:
            n = fuente("Seguimiento Legislativo de la Asamblea Nacional (sistemas.asamblea.gob.pa)")
            principales = sum(1 for p in proy if p["principal"])
            lineas = [f"- {p['fecha_presentacion']}: {'Proyecto ' + p['proyecto'] if p['proyecto'] else 'Anteproyecto ' + (p['anteproyecto'] or '')} "
                      f"«{p['t'][:160]}» — etapa {p['etapa']}{', impacto ' + p['impacto'] if p['impacto'] else ''}"
                      f"{' (proponente principal)' if p['principal'] else ''}" for p in proy[:25]]
            partes.append(f"[{n}] Iniciativas: {len(proy)} en total, {principales} como proponente principal. "
                          f"Las más recientes:\n" + "\n".join(lineas))
    # el perfil que investigó ChatGPT para esta persona, completo (el título lo nombra)
    for d in perfiles_de(e):
        n = fuente(f"{d['titulo']} (investigación de fuentes públicas, {d['fecha']})")
        partes.append(f"[{n}] Perfil investigado (cada dato trae sus fuentes originales; [NV] = no verificado):\n"
                      f"{cerebro.texto_documento(d['id'])[:14000]}")
    for m in d1.consulta(
            "SELECT d.titulo, d.fecha, d.fuente, d.url, m.cita FROM menciones m JOIN documentos d ON d.id = m.documento "
            "WHERE m.entidad = ? ORDER BY d.fecha DESC LIMIT 15", [e["id"]]):
        n = fuente(f"{m['titulo']} ({m['fuente']}, {m['fecha']}){' ' + m['url'] if m['url'] else ''}")
        partes.append(f"[{n}] Mención: {m['cita']}")
    for x in d1.consulta("SELECT d.fecha, d.tema, d.cita, d.postura, o.titulo FROM declaraciones d "
                         "JOIN documentos o ON o.id = d.documento WHERE d.entidad = ? ORDER BY d.fecha DESC LIMIT 20",
                         [e["id"]]):
        n = fuente(f"{x['titulo']} ({x['fecha']})")
        partes.append(f"[{n}] Declaración ({x['tema']}, {x['postura']}): «{x['cita']}»")
    return "\n\n".join(partes), fuentes


def perfilar(consulta):
    e = encontrar(consulta)
    texto, fuentes = contexto(e)
    r = ia.generar_json(INSTRUCCIONES, f"Actor: {e['nombre']} ({e['cargo'] or e['subtipo']})\n\nContexto:\n{texto}", ESQUEMA)
    expediente = {"nombre": e["nombre"], "cargo": e["cargo"], "subtipo": e["subtipo"], **r, "fuentes": fuentes}
    d1.insertar_muchas("expedientes", ["entidad", "contenido", "fuentes", "actualizado"],
                       [[e["id"], json.dumps(expediente, ensure_ascii=False), json.dumps(fuentes, ensure_ascii=False),
                         cerebro.ahora()]])
    print(f"{e['nombre']}: {len(r['estudios'])} estudios, {len(r['experiencia'])} cargos, "
          f"{len(r['datos_interes'])} datos de interés, {len(r['posturas'])} posturas ({r['modelo']})")
    if r["vacios"]:
        print("  falta: " + "; ".join(r["vacios"]))
    return e, expediente


def nombre_del_perfil(titulo):
    return re.sub(r"^Perfil de ", "", titulo or "").split(" (")[0]


def perfiles_de(e):
    personas = [{"id": e["id"], "nombre": e["nombre"]}]
    return [d for d in d1.consulta("SELECT id, titulo, fecha FROM documentos WHERE fuente = 'investigacion_perfil'")
            if cerebro.fichas_de_personas(nombre_del_perfil(d["titulo"]), personas)]


def con_perfil_nuevo():
    """Personas con un perfil investigado (ChatGPT) más nuevo que su expediente: las que hay que (re)perfilar."""
    personas = d1.consulta("SELECT e.id, e.nombre, x.actualizado FROM entidades e LEFT JOIN expedientes x ON x.entidad = e.id "
                           "WHERE e.tipo = 'persona'")
    por_id = {p["id"]: p for p in personas}
    out, sin = {}, []
    for d in d1.consulta("SELECT titulo, creado FROM documentos WHERE fuente = 'investigacion_perfil'"):
        ids = cerebro.fichas_de_personas(nombre_del_perfil(d["titulo"]), personas)
        if len(ids) != 1:
            sin.append(nombre_del_perfil(d["titulo"]))
            continue
        p = por_id[ids[0]]
        if not p["actualizado"] or p["actualizado"] < d["creado"]:
            out[p["id"]] = p["nombre"]
    if sin:
        print("perfiles sin persona única en el directorio: " + "; ".join(sorted(set(sin))), flush=True)
    return out


def publicar(entidad, expediente, pdf):
    """Sube el Keyperfil a Drive y lo registra como producto del Perfilador (uno por actor, se reemplaza)."""
    import agente
    from cerebro import partir
    fecha = os.path.basename(pdf)[:10]
    nombre = partir.nombre_keyword(fecha, "Keyperfil " + expediente["nombre"])
    enlace = None
    if agente.drive_disponible():
        destino = agente.drive_ruta("Keyperfil", nombre)
        agente.rclone("copyto", pdf, destino)
        enlace = partir.enlace_drive(destino)
    d1.insertar_muchas("productos", ["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente",
                                     "fuentes", "creado", "actualizado"],
                       [["keyperfil:" + entidad["id"].split(":", 1)[1], "keyperfil", "Keyperfil · " + expediente["nombre"],
                         entidad["id"], json.dumps(expediente, ensure_ascii=False), enlace or "local", "borrador",
                         "perfilador", "[]", fecha, cerebro.ahora()]])
    return enlace


if __name__ == "__main__":
    cerebro.cargar_env()
    from diseno import keyperfil
    if sys.argv[1] == "--todos":  # todos los que tienen perfil nuevo; Keyperfil en PDF con --diseno
        pendientes = con_perfil_nuevo()
        print(f"{len(pendientes)} personas por perfilar", flush=True)
        for i, (eid, nombre) in enumerate(sorted(pendientes.items(), key=lambda x: x[1]), 1):
            try:
                entidad, exp = perfilar(eid)
                if "--diseno" in sys.argv:
                    keyperfil.armar(entidad, exp)
            except (Exception, SystemExit) as ex:
                print(f"  {nombre}: {ex}", flush=True)
            print(f"  [{i}/{len(pendientes)}]", flush=True)
    elif sys.argv[1] == "--publicar":
        carpeta = os.path.join(cerebro.CARPETA, "salidas", "keyperfil")
        ultimos = {}
        for f in sorted(os.listdir(carpeta)):
            if f.endswith(".pdf"):
                ultimos[f[11:-4]] = f
        for i, (sl, f) in enumerate(sorted(ultimos.items()), 1):
            exp = json.load(open(os.path.join(carpeta, f[:-4] + ".json"), encoding="utf-8"))
            ent = d1.consulta("SELECT id FROM entidades WHERE id LIKE ?", ["%:" + sl])
            if not ent:
                print(f"  sin entidad: {sl}", flush=True)
                continue
            print(f"  [{i}/{len(ultimos)}] {exp['nombre']}: {publicar(ent[0], exp, os.path.join(carpeta, f))}", flush=True)
    else:
        entidad, exp = perfilar(sys.argv[1])
        if "--diseno" in sys.argv:
            print(keyperfil.armar(entidad, exp))
