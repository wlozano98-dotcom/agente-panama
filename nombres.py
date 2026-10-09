"""Proponentes: separar la lista del Seguimiento Legislativo y unificar las distintas formas de un mismo nombre.

El sistema trae los proponentes en un solo texto separado por comas, con "H.D" (diputado) o "H.D.S" (diputado
suplente) delante de cada nombre. Un mismo diputado aparece escrito de varias formas: "JOSE PEREZ BARBONI" y
"JOSÉ ANTONIO PÉREZ BARBONI", "ERNESTO CEDEÑO" y "ERNESTO CEDEÑO ALVARADO". Se unifican en la forma más completa:
una forma corta es la misma persona si todas sus palabras (sin tildes) están en la larga, empieza por el mismo nombre
y hay una sola forma larga que calce.
"""
import re
import unicodedata

TIPOS = {"H.D.S": "Suplente", "H.D": "Diputado"}
MINUSCULAS = {"de", "del", "la", "las", "los", "y", "e"}


def _sin_tildes(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _palabras(nombre):
    return [p for p in re.findall(r"[A-Z]+", _sin_tildes(nombre)) if len(p) > 1 or p not in ("A", "S", "D")]


def titulo(nombre):
    """'JOSÉ ANTONIO PÉREZ BARBONI' → 'José Antonio Pérez Barboni' (respeta "de", "D´Orcy")."""
    out = []
    for i, p in enumerate(nombre.split()):
        if i > 0 and p.lower() in MINUSCULAS:
            out.append(p.lower())
        else:
            out.append(re.sub(r"(^|[´'’\-])(\w)", lambda m: m.group(1) + m.group(2).upper(), p.lower()))
    return " ".join(out)


INSTITUCION = re.compile(r"^(MINISTERIO|PROCURADUR|TRIBUNAL|CORTE|CONTRAL|DEFENSOR|AUTORIDAD|COMISION|ORGANO|CAJA|"
                         r"ASAMBLEA|CONSEJO|CREDENCIALES|GOBIERNO|ECONOMIA|EDUCACION|PRESUPUESTO)")
# palabras con que empieza una institución nueva (las demás de INSTITUCION son nombres de comisión sin "comisión")
CABEZAS = ("MINISTERIO", "PROCURADUR", "TRIBUNAL", "CORTE", "CONTRAL", "DEFENSOR", "AUTORIDAD", "COMISION", "ORGANO",
           "CAJA", "ASAMBLEA", "CONSEJO")
TILDES = {"COMISION": "Comisión", "ECONOMIA": "Economía", "EDUCACION": "Educación", "ETICA": "Ética",
          "ORGANO": "Órgano", "PROCURADURIA": "Procuraduría", "NACION": "Nación", "ADMINISTRACION": "Administración",
          "POBLACION": "Población", "PUBLICA": "Pública", "PUBLICAS": "Públicas", "INDIGENAS": "Indígenas",
          "ECONOMICOS": "Económicos", "ECONOMICA": "Económica", "COMUNICACION": "Comunicación", "POLITICA": "Política",
          "PLANIFICACION": "Planificación", "ELECTORAL": "Electoral"}


def separar(texto):
    """'H.D A,H.D.S B,MINISTERIO X' → [{nombre, tipo}] en el orden del sistema (el primero es el principal).
    Ojo: algunos nombres de comisión llevan comas ("CREDENCIALES, REGLAMENTO, ETICA…"): las comas solo separan
    proponentes cuando lo que sigue es un diputado (H.D) o empieza una institución nueva."""
    grupos = []
    for x in (y.strip() for y in (texto or "").split(",")):
        if not x:
            continue
        sigue_institucion = (grupos and INSTITUCION.match(_sin_tildes(grupos[-1])) and not re.match(r"^H\.\s?D", x)
                             and not _sin_tildes(x).startswith(CABEZAS))
        if sigue_institucion:  # coma dentro del nombre de una institución
            grupos[-1] += ", " + x
        else:
            grupos.append(x)
    out = []
    for parte in grupos:
        m = re.match(r"^(H\.\s?D\.?\s?S|H\.\s?D)\.?\s+(.*)$", parte)
        if m:
            tipo = "Suplente" if m.group(1).replace(" ", "").rstrip(".").endswith("S") else "Diputado"
            out.append({"nombre": m.group(2).strip(), "tipo": tipo})
        elif INSTITUCION.match(_sin_tildes(parte)):
            nombre = parte if _sin_tildes(parte).startswith(CABEZAS) else "COMISION DE " + parte
            out.append({"nombre": nombre, "tipo": "Institución"})
        else:
            out.append({"nombre": parte, "tipo": "Ciudadano"})  # participación ciudadana u otro
    return out


def titulo_institucion(nombre):
    out = []
    for i, p in enumerate(nombre.replace(" ,", ",").split()):
        limpio = p.rstrip(",")
        coma = "," if p.endswith(",") else ""
        if limpio in TILDES:
            out.append(TILDES[limpio] + coma)
        elif i > 0 and limpio.lower() in MINUSCULAS | {"el", "en", "para", "por", "a", "al"}:
            out.append(limpio.lower() + coma)
        else:
            out.append(limpio[:1].upper() + limpio[1:].lower() + coma)
    return " ".join(out)


class Unificador:
    """Aprende las formas completas de los nombres de todas las fichas y traduce cada forma a la más completa."""

    def __init__(self, textos):
        formas = {}
        for t in textos:
            for p in separar(t):
                if p["tipo"] in ("Diputado", "Suplente"):
                    formas[p["nombre"]] = _palabras(p["nombre"])
        self.canon = {}
        largas = sorted(formas, key=lambda n: (-len(formas[n]), n))
        for nombre in largas:
            pal = formas[nombre]
            candidatas = [l for l in largas if l != nombre and len(formas[l]) > len(pal) and pal and formas[l][0] == pal[0]
                          and set(pal) <= set(formas[l])]
            # quedarse con las formas más largas (si una candidata ya se unificó en otra, cuenta la otra)
            destinos = {self.canon.get(c, c) for c in candidatas}
            self.canon[nombre] = destinos.pop() if len(destinos) == 1 else nombre

    def nombre(self, crudo):
        return titulo(self.canon.get(crudo, crudo)) if crudo else ""

    def lista(self, texto):
        """[{nombre, tipo, principal}] unificados y sin repetir."""
        out, vistos = [], set()
        for i, p in enumerate(separar(texto)):
            if p["tipo"] in ("Diputado", "Suplente"):
                n = self.nombre(p["nombre"])
            elif p["tipo"] == "Institución":
                n = titulo_institucion(p["nombre"])
            else:
                n = titulo(p["nombre"])
            if n.lower() in vistos:
                continue
            vistos.add(n.lower())
            out.append({"nombre": n, "tipo": p["tipo"], "principal": i == 0})
        return out


if __name__ == "__main__":
    import json
    import os
    estado = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")))
    textos = [f["proponente"] for f in estado["fichas"].values()]
    u = Unificador(textos)
    unidos = {k: v for k, v in u.canon.items() if k != v}
    print(f"{len(u.canon)} formas de nombres de diputados; {len(unidos)} unificadas en su forma completa:")
    for k, v in sorted(unidos.items()):
        print(f"  {k}  →  {v}")
    personas = {p["nombre"] for t in textos for p in u.lista(t) if p["tipo"] in ("Diputado", "Suplente")}
    print(f"{len(personas)} personas distintas")
