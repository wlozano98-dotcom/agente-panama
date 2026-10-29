"""Parte cada edición de la Gaceta en un PDF por norma, con el nombre de archivo de Keyword, y lo sube a Drive.

Uso: python3 cerebro/partir.py [número de edición, p. ej. 30641_A]   (sin número: todas las normas aún sin PDF)
Nombre de Keyword: AAMMDD + nombre corto, p. ej. "261024 Plan Nacional de Vivienda.pdf" (fecha de la edición).
Los PDF quedan en salidas/gaceta/normas/ y en Drive (<raíz>/Gaceta Oficial/<edición>/); el enlace va a normas.pdf
para descargarlo desde la oficina y adjuntarlo al Keymonitor. Son de paso: mesa.limpiar_pdf los borra a los 7 días.
El texto de cada norma queda en el cerebro (documento "gaceta_texto", uno por norma).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agente  # noqa: E402  (rclone, drive_ruta, nombre_seguro)
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

CARPETA = os.path.join(cerebro.CARPETA, "salidas", "gaceta")


def nombre_keyword(fecha, nombre):
    """"2026-10-24", "Plan Nacional de Vivienda" → "261024 Plan Nacional de Vivienda.pdf"."""
    return agente.nombre_seguro(f"{fecha[2:4]}{fecha[5:7]}{fecha[8:10]} {nombre}", 120) + ".pdf"


def paginas(texto, total):
    """"1-2, 14-18" → [13, 14, 15, 16, 17] (índices desde 0). Se quitan las páginas del sumario (1-2) cuando la
    norma tiene además su propio texto más adelante."""
    partes = []
    for p in re.split(r"[,;y]+", texto or ""):
        m = re.match(r"\s*(\d+)\s*(?:-|a|–)?\s*(\d+)?\s*$", p)
        if m:
            ini, fin = int(m.group(1)), int(m.group(2) or m.group(1))
            partes.append((min(ini, fin), max(ini, fin)))
    if len(partes) > 1:
        partes = [x for x in partes if x[1] > 2] or partes
    return [i - 1 for a, b in partes for i in range(a, b + 1) if 1 <= i <= total]


def nombres_cortos(normas):
    """Nombre corto (3 a 7 palabras) para las normas que no lo traen del índice."""
    faltan = [n for n in normas if not n.get("nombre")]
    if not faltan:
        return {}
    lista = "\n".join(f"{n['id']}: {n['tipo']} {n['numero']} ({n['entidad']}) — {n['titulo']}" for n in faltan)
    r = ia.generar_json(
        "Para cada norma de la Gaceta Oficial de Panamá, escribe un nombre corto de archivo de 3 a 7 palabras que diga "
        "de qué trata, en español, con mayúscula inicial en las palabras principales, sin tipo ni número de la norma "
        "(p. ej. \"Plan Nacional de Vivienda\", \"Señalización Vial en Obras Públicas\", \"Edicto Adjudicación de "
        "Terreno La Chorrera\").", lista,
        {"type": "object", "properties": {"nombres": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "nombre": {"type": "string"}}, "required": ["id", "nombre"]}}}, "required": ["nombres"]})
    return {x["id"]: x["nombre"] for x in r["nombres"]}


def enlace_drive(ruta):
    carpeta, nombre = ruta.rsplit("/", 1)
    for item in json.loads(agente.rclone("lsjson", "--files-only", carpeta)):
        if item["Name"] == nombre:
            return f"https://drive.google.com/file/d/{item['ID']}/view"
    return None


def partir(numero=None):
    import pypdf
    filtro, params = ("AND n.edicion = ?", [numero.replace("_", "-")]) if numero else ("", [])
    normas = d1.consulta(f"SELECT n.*, d.titulo AS gaceta_titulo FROM normas n JOIN documentos d ON d.id = n.gaceta "
                         f"WHERE n.pdf IS NULL {filtro} ORDER BY n.edicion", params)
    cortos = nombres_cortos(normas)
    hechas = 0
    for edicion in sorted({n["edicion"] for n in normas}):
        archivo = os.path.join(CARPETA, edicion.replace("-", "_") + ".pdf")
        if not os.path.exists(archivo):
            continue
        lector = pypdf.PdfReader(archivo)
        carpeta_local = os.path.join(CARPETA, "normas", edicion)
        os.makedirs(carpeta_local, exist_ok=True)
        usados = set()
        for n in [x for x in normas if x["edicion"] == edicion]:
            hojas = paginas(n["paginas"], len(lector.pages))
            if not hojas:
                continue
            nombre = n.get("nombre") or cortos.get(n["id"]) or n["titulo"][:60]
            fichero = nombre_keyword(n["fecha"] or "", nombre)
            if fichero in usados:  # dos normas con el mismo nombre corto el mismo día
                fichero = fichero[:-4] + f" ({n['numero']}).pdf"
            usados.add(fichero)
            escritor = pypdf.PdfWriter()
            for i in hojas:
                escritor.add_page(lector.pages[i])
            # el texto de la norma queda en el cerebro (el PDF se borra a los 7 días); si es un escaneo, su resumen
            texto = "\n".join((lector.pages[i].extract_text() or "") for i in hojas).strip()
            if len(texto) < 200:
                texto = f"{n['titulo']}\n\n{n.get('resumen') or ''}"
            cerebro.guardar_documento("gaceta_texto", n["id"], f"# {fichero[:-4]}\n\n{n['tipo']} {n['numero']} · {n['entidad']}\n\n{texto}",
                                      tipo="norma", titulo=fichero[:-4], fecha=n["fecha"])
            local = os.path.join(carpeta_local, fichero)
            with open(local, "wb") as f:
                escritor.write(f)
            enlace = None
            if agente.drive_disponible():
                destino = agente.drive_ruta("Gaceta Oficial", edicion, fichero)
                agente.rclone("copyto", local, destino)
                enlace = enlace_drive(destino)
            d1.consulta("UPDATE normas SET nombre = ?, archivo = ?, pdf = ? WHERE id = ?",
                        [nombre, fichero, enlace or "local", n["id"]])
            hechas += 1
            print(f"  {edicion}: {fichero} ({len(hojas)} págs.)", flush=True)
    return hechas


if __name__ == "__main__":
    cerebro.cargar_env()
    print("normas partidas:", partir(sys.argv[1] if len(sys.argv) > 1 else None))
