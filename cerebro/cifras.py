"""Tomás · Cifras y Keyeconomics: vigila las publicaciones económicas del INEC y escribe el Keyeconomics.

Uso: python3 cerebro/cifras.py                 (una revisión; la mesa de la Mac lo corre cada hora, días hábiles 8-18)
     python3 cerebro/cifras.py --redactar <id>   (Keyeconomics de una cifra ya vista, aunque sea vieja: para probar)
Solo lo REGULAR (Andrés, 2026-10-25: lo analítico necesita un cerebro humano): IPC, IMAE, Principales Indicadores
Económicos Mensuales, PIB trimestral y Encuesta de Mercado Laboral. Cada publicación del INEC trae un PDF "Comentario"
con el texto oficial: esa es la señal de que salió el dato y la materia prima del correo (el INEC no tiene anti-bots).
El Keyeconomics queda en borrador en la oficina; por Telegram solo se avisa que está para revisión (regla de Andrés: lo
que va por correo nunca se revisa en el chat). Formato: los Keyeconomics reales de Keyword (ejemplos/, no se suben).
La primera vez solo se toma nota de lo que ya está publicado.
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from db import d1  # noqa: E402

INEC = "https://www.inec.gob.pa"
NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
# indicador: (nombre, página, fila del comentario, publicación a elegir en una lista, ejemplos de Keyword a imitar)
FUENTES = {
    "IPC": ("Índice de Precios al Consumidor (inflación)", "/avance/Default2.aspx?ID_CATEGORIA=2&ID_CIFRAS=10&ID_IDIOMA=1",
            r"^COMENTARIO.*CONSUMIDOR", None, r"Cifras_de_Empleo_(?!.*Trimestre)"),
    "IMAE": ("Índice Mensual de Actividad Económica (IMAE)", "/avance/Default2.aspx?ID_CATEGORIA=1&ID_CIFRAS=49&ID_IDIOMA=1",
             r"^Comentario", None, r"Cifras_de_Empleo_(?!.*Trimestre)"),
    "PIEM": ("Principales Indicadores Económicos Mensuales", None, r"^COMENTARIO$", None, r"Cifras_de_Empleo_(?!.*Trimestre)"),
    "PIB": ("Producto Interno Bruto Trimestral", "/publicaciones/Default2.aspx?ID_CATEGORIA=4&ID_SUBCATEGORIA=73",
            r"^Comentario", r"^Producto Interno Bruto Trimestral:", r"Economía_Ecuatoriana_(Creció|Decreció|se_Contrajo)"),
    "Empleo": ("Encuesta de Mercado Laboral", "/publicaciones/Default2.aspx?ID_CATEGORIA=5&ID_SUBCATEGORIA=38",
               r"^COMENTARIO", r"^Boletín de la Encuesta Mercado Laboral", r"Empleo"),
}

REDACCION = """Eres Tomás, economista de Keyword (consultora de asuntos públicos) en Panamá. Recibes el comentario
oficial del Instituto Nacional de Estadística y Censo (INEC) sobre una cifra económica recién publicada. Escribe el
Keyeconomics: el correo a clientes que cuenta la cifra. Es DESCRIPTIVO: solo lo que dice el INEC, sin opinión,
interpretación propia, proyecciones ni recomendaciones. Estructura fija:
Estimados,
Ponemos en su conocimiento las cifras de <indicador> correspondientes a <periodo>, recientemente publicadas por el
Instituto Nacional de Estadística y Censo (INEC).
Según los datos oficiales, <las 2 o 3 cifras principales en una o dos oraciones>.
Si suma, de 2 a 4 viñetas "- " con los detalles que más le importan a una empresa (sectores, rubros, regiones).
Saludos cordiales,
Reglas: usa SOLO cifras que estén en el documento, con coma decimal (2,1%); el mes y el año deben ser los del dato
(revísalo dos veces: es un error común); nombres de instituciones completos la primera vez. Asunto en tipo título,
como los ejemplos ("Cifras de Inflación Septiembre 2026", "Economía Panameña Creció 4,1% en el Segundo Trimestre de 2026")."""
ESQUEMA = {"type": "object", "properties": {
    "periodo": {"type": "string", "description": "mes o trimestre y año del dato, p. ej. 'septiembre de 2026'"},
    "asunto": {"type": "string", "description": "asunto sin 'Keyeconomics:'"},
    "dato": {"type": "string", "description": "una línea con el dato principal, para el aviso"},
    "cuerpo": {"type": "string"},
    "cifras": {"type": "array", "items": {"type": "object", "properties": {
        "nombre": {"type": "string"}, "valor": {"type": "string"}}, "required": ["nombre", "valor"]}},
}, "required": ["periodo", "asunto", "dato", "cuerpo", "cifras"]}


def bajar(url, binario=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": NAVEGADOR}), timeout=90) as r:
        datos = r.read()
    return datos if binario else datos.decode("utf-8", "ignore")


def limpio(t):
    import html
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def absoluta(href, pagina):
    return urllib.parse.urljoin(INEC + pagina, href.replace(" ", "%20"))


def filas(pagina):
    """Filas de una página del INEC: (título, enlaces a archivos)."""
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", bajar(INEC + pagina))
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", s):
        enlaces = re.findall(r'(?is)href="([^"]*archivos/[^"]+)"', tr)
        celdas = [limpio(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)]
        if enlaces and celdas:
            out.append((next((c for c in celdas if c), ""), [absoluta(e, pagina) for e in enlaces]))
    return out


def pagina_piem():
    """La página de los Indicadores Económicos Mensuales cambia cada año: se busca la del año más reciente."""
    s = bajar(INEC + "/avance/Default.aspx?ID_CATEGORIA=1&ID_IDIOMA=1")
    anios = re.findall(r'href="(Default2\.aspx\?ID_CATEGORIA=1&(?:amp;)?ID_CIFRAS=\d+&(?:amp;)?ID_IDIOMA=1)"[^>]*>\s*'
                       r"Principales Indicadores Económicos Mensuales - (\d{4})", s)
    href, _ = max(anios, key=lambda x: x[1])
    return "/avance/" + href.replace("&amp;", "&")


def publicaciones():
    """Los comentarios del INEC que hay hoy publicados, uno por indicador y publicación."""
    out = []
    for clave, (nombre, pagina, fila, pub, _) in FUENTES.items():
        try:
            if clave == "PIEM":
                pagina = pagina_piem()
            if pub:  # lista de publicaciones: se toma la más nueva de ese tipo
                s = bajar(INEC + pagina)
                m = next(m for m in re.finditer(r'href="(Default3\.aspx\?[^"]+)"[^>]*>([^<]+)', s)
                         if re.search(pub, limpio(m.group(2))))
                pagina, titulo_pub = "/publicaciones/" + m.group(1).replace("&amp;", "&"), limpio(m.group(2))
            for titulo, enlaces in filas(pagina):
                if re.search(fila, titulo, re.I):
                    pdf = next((e for e in enlaces if e.lower().endswith(".pdf")), enlaces[0])
                    f = re.search(r"(20\d{2})(\d{2})(\d{2})\d{6}", pdf)
                    out.append({"id": cerebro.huella("inec", pdf), "indicador": clave, "nombre": nombre,
                                "titulo": titulo_pub if pub else titulo, "url": pdf, "pagina": INEC + pagina,
                                "publicado": f"{f.group(1)}-{f.group(2)}-{f.group(3)}" if f else None})
        except Exception as e:
            print(f"  INEC {clave}: no pude leer ({e})", flush=True)
    return out


def crear_tabla():
    d1.consulta("CREATE TABLE IF NOT EXISTS cifras (id TEXT PRIMARY KEY, indicador TEXT, nombre TEXT, titulo TEXT, url TEXT, "
                "pagina TEXT, publicado TEXT, periodo TEXT, dato TEXT, cifras TEXT, documento TEXT, producto TEXT, "
                "estado TEXT, creado TEXT)")


def texto_pdf(datos):
    import pypdf
    lector = pypdf.PdfReader(io.BytesIO(datos))
    return "\n".join((p.extract_text() or "") for p in lector.pages[:12]).strip()


def ejemplos(patron, n=3):
    import glob
    rutas = [r for r in sorted(glob.glob(os.path.join(cerebro.CARPETA, "ejemplos", "keyword", "Keyeconomics", "*.txt")),
                               reverse=True) if re.search(patron, os.path.basename(r))][:n]
    out = ["\n".join(l for l in open(r, encoding="utf-8").read().splitlines()
                     if not l.startswith(("Fecha:", "De:", "Adjuntos:"))).strip() for r in rutas]
    return (("\n\nEJEMPLOS REALES de Keyword (son de Ecuador: copia su tono, estructura y largo, NO sus instituciones ni "
             "datos; aquí la fuente es el INEC de Panamá):\n\n" + "\n\n-----\n\n".join(out)) if out else "") + \
        cerebro.aprendido("keyeconomics")


def redactar(c):
    """Lee el comentario del INEC, guarda el texto en el cerebro y deja el Keyeconomics en borrador."""
    datos = bajar(c["url"], binario=True)
    texto = texto_pdf(datos)
    adjuntos = []
    if len(texto) < 300:  # escaneado: Gemini lee el PDF
        import agente
        adjuntos = [{"file_data": {"mime_type": "application/pdf", "file_uri": agente.gemini_subir(c["titulo"], datos)}}]
    doc, _ = cerebro.guardar_documento("inec", c["url"], texto or c["titulo"], tipo="cifra", url=c["url"],
                                       fecha=c["publicado"], titulo=f"INEC · {c['titulo']}")
    r = ia.generar_json(REDACCION + ejemplos(FUENTES[c["indicador"]][4]),
                        f"Indicador: {c['nombre']}\nPublicación: {c['titulo']}\nFecha de publicación: {c['publicado']}\n\n"
                        f"Comentario del INEC:\n{texto[:30000]}", ESQUEMA, adjuntos=adjuntos)
    asunto = "Keyeconomics: " + re.sub(r"^Keyeconomics:\s*", "", r["asunto"]).strip()
    pid = cerebro.huella("keyeconomics", c["id"])
    editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente", "fuentes",
                                     "creado", "actualizado"],
                       [[pid, "keyeconomics", asunto, None, r["cuerpo"], c["url"], "borrador", "cifras", json.dumps([doc]),
                         cerebro.ahora(), cerebro.ahora()]], modo="INSERT OR REPLACE")
    d1.consulta("UPDATE cifras SET periodo = ?, dato = ?, cifras = ?, documento = ?, producto = ? WHERE id = ?",
                [r["periodo"], r["dato"], json.dumps(r["cifras"], ensure_ascii=False), doc, pid, c["id"]])
    return r, asunto


def revisar():
    crear_tabla()
    ya = {f["id"] for f in d1.consulta("SELECT id FROM cifras")}
    hay = publicaciones()
    nuevas = [c for c in hay if c["id"] not in ya]
    primera = not ya
    d1.insertar_muchas("cifras", ["id", "indicador", "nombre", "titulo", "url", "pagina", "publicado", "estado", "creado"],
                       [[c["id"], c["indicador"], c["nombre"], c["titulo"], c["url"], c["pagina"], c["publicado"],
                         "base" if primera else "nueva", cerebro.ahora()] for c in nuevas], modo="INSERT OR IGNORE")
    if primera:
        return f"{len(nuevas)} publicaciones del INEC anotadas (primera vez: sin Keyeconomics)"
    hechos = []
    for c in nuevas:
        try:
            r, asunto = redactar(c)
            hechos.append(f"📊 Tomás · {c['nombre']}, {r['periodo']}: {r['dato']}\n"
                          f"El Keyeconomics «{asunto.replace('Keyeconomics: ', '')}» ya está en la plataforma para revisión.")
        except Exception as e:
            print(f"  {c['indicador']}: {e}", flush=True)
    for h in hechos:
        cerebro.telegram(h, destino="general")
    return f"{len(nuevas)} publicaciones nuevas del INEC, {len(hechos)} Keyeconomics en borrador"


def redactar_id(cid):
    crear_tabla()
    c = d1.consulta("SELECT * FROM cifras WHERE id = ?", [cid])
    if not c:
        raise SystemExit("No conozco esa cifra")
    if c[0]["indicador"] == "Combustibles":
        from cerebro import combustibles
        return combustibles.redactar_id(cid)
    r, asunto = redactar(c[0])
    return f"{asunto} (borrador)"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "--redactar":
        print(redactar_id(sys.argv[2]))
    else:
        print(revisar())
