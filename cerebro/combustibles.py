"""Tomás · precios de los combustibles: la Secretaría Nacional de Energía (energia.gob.pa, WordPress, sin anti-bots)
publica cada 14 días un comunicado con los precios máximos de venta que rigen desde el viernes siguiente. Los precios
vienen en IMÁGENES dentro del comunicado (variación por litro, precios por localidad): Gemini lee el texto y las
imágenes, saca la vigencia, los precios y la tendencia, y escribe el Keyeconomics (formato de los reales de
"Precios Combustibles" en ejemplos/keyword/Keyeconomics/). Cada comunicado es también una fila de `cifras`
(indicador "Combustibles"), así sale en "Cifras publicadas" de la oficina junto con el INEC.

Uso: python3 cerebro/combustibles.py               (una revisión; la mesa la corre con las del INEC, cada hora L-V 8-18)
     python3 cerebro/combustibles.py --redactar <id> (vuelve a escribir el Keyeconomics de un comunicado)
"""
import base64
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import editora, ia  # noqa: E402
from cerebro.cifras import bajar, crear_tabla, ejemplos, limpio  # noqa: E402
from db import d1  # noqa: E402

API = "https://www.energia.gob.pa/wp-json/wp/v2/posts?search=" + urllib.parse.quote("precios de los combustibles") + \
      "&per_page=10&_fields=id,date,link,title,content"
NOMBRE = "Precios de los combustibles"

REDACCION = """Eres Tomás, economista de Keyword (consultora de asuntos públicos) en Panamá. Recibes el comunicado de
la Secretaría Nacional de Energía con los nuevos precios máximos de venta de los combustibles y sus imágenes
(tablas de precios por localidad y variación por litro). Primero LEE las imágenes y saca los datos; después escribe
el Keyeconomics: el correo corto a clientes. Es DESCRIPTIVO: solo lo que dicen el comunicado y sus tablas, sin
opinión ni proyecciones. Estructura fija:
Estimados,
Ponemos en su conocimiento los nuevos precios máximos de venta al público de los combustibles que rigen del <fecha>
al <fecha>, publicados por la Secretaría Nacional de Energía.
Una oración con la tendencia (qué sube y qué baja, y cuánto por litro si está).
Los precios en la Ciudad de Panamá, en viñetas "- " (gasolina de 95 octanos, de 91 octanos y diésel), con la unidad
que use la tabla.
Si la tabla trae otras localidades, una línea con el rango (la más barata y la más cara).
Saludos cordiales,
Reglas: usa SOLO cifras que se lean en el comunicado o sus imágenes; si una imagen no se lee, no inventes: dilo en
"faltantes". Montos con punto decimal como los publica Panamá y SIEMPRE en balboas por litro: "B/. 1.421 por litro"
(los precios rondan 1 balboa por litro; nunca escribas "centavos" para un monto mayor que 1); las variaciones
igual: "B/. 0.039 por litro".
Asunto en tipo título, como los ejemplos ("Precios Combustibles del 16 al 30 de Octubre de 2026")."""
ESQUEMA = {"type": "object", "properties": {
    "desde": {"type": "string", "description": "AAAA-MM-DD"}, "hasta": {"type": "string", "description": "AAAA-MM-DD"},
    "tendencia": {"type": "string"},
    "precios": {"type": "array", "items": {"type": "object", "properties": {
        "localidad": {"type": "string"}, "gasolina_95": {"type": "string"}, "gasolina_91": {"type": "string"},
        "diesel": {"type": "string"}}, "required": ["localidad", "gasolina_95", "gasolina_91", "diesel"]}},
    "variacion": {"type": "array", "items": {"type": "object", "properties": {
        "nombre": {"type": "string"}, "valor": {"type": "string"}}, "required": ["nombre", "valor"]}},
    "faltantes": {"type": "string"},
    "dato": {"type": "string", "description": "una línea con lo principal, para el aviso"},
    "asunto": {"type": "string", "description": "asunto sin 'Keyeconomics:'"},
    "cuerpo": {"type": "string"},
}, "required": ["desde", "hasta", "tendencia", "precios", "variacion", "faltantes", "dato", "asunto", "cuerpo"]}


def comunicados():
    out = []
    for p in json.loads(bajar(API)):
        titulo = limpio(p["title"]["rendered"])
        if not re.search(r"precios de los combustibles", titulo, re.I):
            continue
        out.append({"id": cerebro.huella("combustibles", p["link"]), "titulo": titulo, "url": p["link"],
                    "publicado": p["date"][:10], "html": p["content"]["rendered"]})
    return out


def imagenes(html):
    """Las imágenes del comunicado (menos el logo), como adjuntos para Gemini."""
    out = []
    for src in re.findall(r'<img[^>]+src="([^"]+)"', html):
        if re.search(r"logo", src, re.I) or not re.search(r"\.(jpe?g|png|webp)$", src, re.I):
            continue
        try:
            datos = bajar(urllib.parse.quote(src.replace("http://", "https://"), safe=":/%?=&"), binario=True)
        except Exception as e:
            print(f"  imagen {src}: {e}", flush=True)
            continue
        tipo = "image/png" if src.lower().endswith(".png") else "image/webp" if src.lower().endswith(".webp") else "image/jpeg"
        out.append({"inline_data": {"mime_type": tipo, "data": base64.b64encode(datos).decode()}})
    return out[:6]


def redactar(c):
    """Lee el comunicado y sus imágenes, guarda el texto en el cerebro y deja el Keyeconomics en borrador."""
    html = c.get("html") or next((x["html"] for x in comunicados() if x["id"] == c["id"]), "")
    texto = limpio(html)
    guia = ejemplos(r"Precios_Combustibles", 3).replace("aquí la fuente es el INEC de Panamá",
                                                         "aquí la fuente es la Secretaría Nacional de Energía de Panamá")
    r = ia.generar_json(REDACCION + guia, f"Comunicado: {c['titulo']}\nPublicado: {c['publicado']}\n\n{texto[:20000]}",
                        ESQUEMA, adjuntos=imagenes(html))
    resumen = "\n".join(f"{p['localidad']}: 95 {p['gasolina_95']} · 91 {p['gasolina_91']} · diésel {p['diesel']}"
                        for p in r["precios"])
    doc, _ = cerebro.guardar_documento("energia", c["url"], f"{texto}\n\nPrecios (leídos de las tablas):\n{resumen}",
                                       tipo="cifra", url=c["url"], fecha=c["publicado"], titulo=f"Energía · {c['titulo']}")
    asunto = "Keyeconomics: " + re.sub(r"^Keyeconomics:\s*", "", r["asunto"]).strip()
    pid = cerebro.huella("keyeconomics", c["id"])
    editora.guardar(["id", "tipo", "titulo", "entidad", "contenido", "archivo", "estado", "agente", "fuentes",
                                     "creado", "actualizado"],
                       [[pid, "keyeconomics", asunto, None, r["cuerpo"], c["url"], "borrador", "cifras", json.dumps([doc]),
                         cerebro.ahora(), cerebro.ahora()]], modo="INSERT OR REPLACE")
    cifras = [{"nombre": f"{p['localidad']} · {k}", "valor": p[c2]} for p in r["precios"][:3]
              for k, c2 in (("gasolina 95", "gasolina_95"), ("gasolina 91", "gasolina_91"), ("diésel", "diesel"))] + r["variacion"]
    d1.consulta("UPDATE cifras SET periodo = ?, dato = ?, cifras = ?, documento = ?, producto = ? WHERE id = ?",
                [f"del {r['desde']} al {r['hasta']}", r["dato"], json.dumps(cifras, ensure_ascii=False), doc, pid, c["id"]])
    if r["faltantes"].strip():
        print(f"  combustibles: faltantes: {r['faltantes']}", flush=True)
    return r, asunto


def revisar():
    crear_tabla()
    ya = {f["id"] for f in d1.consulta("SELECT id FROM cifras WHERE indicador = 'Combustibles'")}
    hay = comunicados()
    nuevas = [c for c in hay if c["id"] not in ya]
    primera = not ya
    d1.insertar_muchas("cifras", ["id", "indicador", "nombre", "titulo", "url", "pagina", "publicado", "estado", "creado"],
                       [[c["id"], "Combustibles", NOMBRE, c["titulo"], c["url"], "energia.gob.pa", c["publicado"],
                         "base" if primera else "nueva", cerebro.ahora()] for c in nuevas], modo="INSERT OR IGNORE")
    if primera:  # la primera vez solo se anota; el más reciente sí se escribe, para que se vea en la oficina
        nuevas = sorted(nuevas, key=lambda c: c["publicado"])[-1:]
        avisar = False
    else:
        avisar = True
    hechos = []
    for c in nuevas:
        try:
            r, asunto = redactar(c)
            hechos.append(f"⛽ Tomás · Combustibles del {r['desde']} al {r['hasta']}: {r['dato']}\n"
                          f"El Keyeconomics «{asunto.replace('Keyeconomics: ', '')}» ya está en la plataforma para revisión.")
        except Exception as e:
            print(f"  combustibles: {e}", flush=True)
    if avisar:
        for h in hechos:
            cerebro.telegram(h, destino="general")
    return f"{len(nuevas)} comunicados de combustibles, {len(hechos)} Keyeconomics en borrador"


def redactar_id(cid):
    c = d1.consulta("SELECT * FROM cifras WHERE id = ?", [cid])
    if not c:
        raise SystemExit("No conozco ese comunicado")
    r, asunto = redactar(c[0])
    return f"{asunto} (borrador)"


if __name__ == "__main__":
    cerebro.cargar_env()
    if len(sys.argv) > 2 and sys.argv[1] == "--redactar":
        print(redactar_id(sys.argv[2]))
    else:
        print(revisar())
