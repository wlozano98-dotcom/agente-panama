"""Escuela de agentes (2026-11-18; plan en PLAN.md «Escuela de agentes»): que los agentes aprendan a hacer los
productos de Keyword como una persona nueva. Empieza por el Keymonitor (pares norma → reporte del correo de Keyword,
ejemplos/keyword/Keymonitor_corpus/, local: no se sube).

  python3 cerebro/escuela.py manual Keymonitor     destila el manual v0 de una muestra variada y lo verifica contra
                                                    otro grupo que no vio → ejemplos/keyword/Keymonitor/MANUAL.md
  python3 cerebro/escuela.py separar Keymonitor     aparta los pares del EXAMEN (nunca se usan para aprender)

El manual es un BORRADOR para que una persona lo corrija: las reglas de Panamá se escriben a mano al final.
Los nombres de clientes se tapan antes de mandar cualquier texto al modelo (clientes.enmascarar).
"""
import glob
import json
import os
import random
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
import clientes  # noqa: E402
from cerebro import ia  # noqa: E402

CARPETA = os.path.join(cerebro.CARPETA, "ejemplos", "keyword")
MODELOS_FUERTES = ["gemini-pro-latest"] + ia.MODELOS  # para destilar (una vez): el mejor disponible


def corpus(producto):
    """[{carpeta, asunto, fecha, texto, adjuntos}] sin rebotes ni vacíos."""
    salida = []
    for r in sorted(glob.glob(os.path.join(CARPETA, producto + "_corpus", "*", "reporte.json"))):
        d = json.load(open(r, encoding="utf-8"))
        if len(d.get("texto") or "") > 300 and "No se pudo entregar" not in d["texto"][:400]:
            d["carpeta"] = os.path.basename(os.path.dirname(r))
            salida.append(d)
    return salida


def examen_ids(producto):
    ruta = os.path.join(CARPETA, producto, "examen.json")
    return set(json.load(open(ruta))) if os.path.exists(ruta) else set()


def separar(producto, n=40, semilla=7):
    """Aparta n pares con norma adjunta, repartidos por año y tipo, para el examen. Se hace UNA vez."""
    ruta = os.path.join(CARPETA, producto, "examen.json")
    if os.path.exists(ruta):
        return f"ya existe ({len(json.load(open(ruta)))} pares): no se rehace para no contaminar el examen"
    con = [d for d in corpus(producto) if d["adjuntos"] and any(a.lower().endswith(".pdf") for a in d["adjuntos"])]
    random.Random(semilla).shuffle(con)
    ids = [d["carpeta"] for d in con[:n]]
    json.dump(ids, open(ruta, "w"), indent=1)
    return f"{len(ids)} pares apartados para el examen"


def tipo_de(asunto):
    a = cerebro.normal(asunto)
    for t in ("NORMA TECNICA", "REGLAMENTO", "REFORMA", "DECRETO", "RESOLUCION", "ACUERDO", "LEY", "INSTRUCTIVO"):
        if t in a:
            return t
    return "OTRO"


def muestra(casos, n, semilla):
    """n casos repartidos por año y tipo de norma (no los más recientes: así entran todas las variantes)."""
    grupos = {}
    for d in casos:
        grupos.setdefault((d["fecha"][:4], tipo_de(d["asunto"])), []).append(d)
    rnd = random.Random(semilla)
    for g in grupos.values():
        rnd.shuffle(g)
    out = []
    while len(out) < n and any(grupos.values()):
        for k in sorted(grupos):
            if grupos[k] and len(out) < n:
                out.append(grupos[k].pop())
    return out


def estadisticas(casos):
    largos = sorted(len(d["texto"]) for d in casos)
    vin = [sum(1 for l in d["texto"].splitlines() if l.strip().startswith("- ")) for d in casos]
    return (f"{len(casos)} Keymonitor reales (2023-2026). Largo del cuerpo: mediana {statistics.median(largos):.0f} "
            f"caracteres (10 % más cortos < {largos[len(largos) // 10]}, 10 % más largos > {largos[9 * len(largos) // 10]}). "
            f"Viñetas: mediana {statistics.median(vin):.0f}. Apertura 'Estimados,' en ~97 %. Cierre 'Saludos cordiales' "
            "en ~97 %. Segunda línea más común: 'Ponemos en su conocimiento la siguiente normativa, publicada en el "
            "<Suplemento del> Registro Oficial No. N:' seguida del nombre de la ENTIDAD en mayúsculas y una viñeta por norma; "
            "cuando es una sola norma importante: 'Ponemos en su conocimiento que <autoridad>, mediante <norma>, <qué hizo>'. "
            "Viñetas que empiezan casi siempre con verbo en presente o artículo: Se…, La/El…, Establece, Exige, Dispone, "
            "Permite, Regula, Obliga, Fija.")


def bloque(casos, largo=3000):
    return "\n\n=====\n\n".join(f"Asunto: {d['asunto']}\n\n{clientes.enmascarar(d['texto'][:largo])}" for d in casos)


DESTILAR = """Eres el editor jefe de Keyword, consultora de asuntos públicos. Vas a escribir el MANUAL DE ESTILO del
"Keymonitor" para entrenar a un redactor nuevo (una IA). El Keymonitor es el correo que avisa a los clientes de una
norma nueva (ley, decreto, acuerdo, resolución, norma técnica, reglamento) y qué dispone. Recibes estadísticas de
~1.000 Keymonitor reales y una muestra variada. Escribe el manual en Markdown, en español, CONCRETO y verificable
(nada de "sé claro"): cada regla debe poder comprobarse en un texto. Secciones:
1. Qué es y qué NO es un Keymonitor (descriptivo, sin opinión ni recomendaciones; solo lo que dice la norma).
2. Asunto: forma exacta, largo, cómo se elige el nombre corto (con ejemplos de la muestra).
3. Estructura obligatoria, en orden, con las fórmulas fijas textuales (apertura, frase de introducción en sus
   variantes: una norma / varias normas / una norma de una autoridad importante; cierre).
4. Cómo se nombra la norma: tipo, número, autoridad, dónde y cuándo se publicó.
5. Las viñetas: cuántas según el tipo de norma, qué va en cada una (orden típico: objeto, alcance, obligaciones,
   plazos, sanciones, vigencia, derogatorias), cómo empiezan (verbos), largo de cada una, qué datos NUNCA faltan
   (plazos, montos, a quién aplica, entrada en vigencia) y qué se omite.
6. Variantes por tipo de norma (norma técnica voluntaria u obligatoria, reforma, reglamento, decreto, resolución
   tributaria, varias normas en un mismo correo) con su patrón.
7. Registro y tono: persona gramatical, tiempos verbales, palabras que se usan y que se evitan, cómo se citan cifras.
8. Errores que NO comete un redactor de Keyword (lista).
9. Lista de verificación final (10-15 puntos sí/no) para revisar un Keymonitor antes de enviarlo.
Reglas: NO menciones instituciones, leyes ni nombres propios de Ecuador como regla (los ejemplos son de Ecuador, pero
el manual se usará en Panamá y otros países: escribe "el diario oficial", "la autoridad", y pon los ejemplos entre
corchetes como ilustración). No inventes reglas que la muestra no respalde."""

VERIFICAR = """Eres un revisor exigente. Recibes un MANUAL DE ESTILO del Keymonitor y un grupo de Keymonitor reales que
el autor del manual NO vio. Compara: ¿qué hacen estos reportes que el manual no dice, qué regla del manual no se
cumple en ellos (quizá es falsa o demasiado rígida) y qué falta? Devuelve el manual CORREGIDO completo (mismas
secciones, en Markdown) y la lista de cambios que hiciste. No agregues reglas que estos ejemplos no respalden."""

ESQ_MANUAL = {"type": "object", "properties": {"manual": {"type": "string"}}, "required": ["manual"]}
ESQ_VERIF = {"type": "object", "properties": {"manual": {"type": "string"},
                                              "cambios": {"type": "array", "items": {"type": "string"}}},
             "required": ["manual", "cambios"]}

PANAMA = """
## Reglas de Panamá (escritas a mano; mandan sobre lo anterior)

- El diario oficial es la **Gaceta Oficial** (Gaceta Oficial Digital N.º 30641, y sus ediciones con letra: 30641-A,
  30641-B…). Fórmula: «Ponemos en su conocimiento la siguiente normativa, publicada en la Gaceta Oficial N.º 30641 del
  23 de octubre de 2026:».
- Tipos de norma frecuentes: Ley N.º, Decreto Ejecutivo N.º, Resolución N.º (de ministerios, superintendencias, ASEP,
  ACODECO, DGI), Acuerdo (SMV, Superintendencia de Seguros), Resolución de Gabinete, reglamentos técnicos DGNTI-COPANIT.
- Las leyes vienen de proyectos con tres debates en la Asamblea: si la norma es una ley, se puede decir «Proyecto de
  Ley N.º X aprobado en tercer debate» solo si consta en la Gaceta o en el sistema.
- Moneda: B/. (balboas) con coma decimal; fechas «23 de octubre de 2026».
- Nada de instituciones, leyes ni nombres de Ecuador.
- (Pendiente: que el equipo de Panamá revise y complete esta sección.)
"""


def manual(producto):
    casos = [d for d in corpus(producto) if d["carpeta"] not in examen_ids(producto)]
    if len(casos) < 100:
        raise SystemExit(f"Pocos casos de {producto} ({len(casos)})")
    a = muestra(casos, 70, semilla=1)
    vistos = {d["carpeta"] for d in a}
    b = muestra([d for d in casos if d["carpeta"] not in vistos], 40, semilla=2)
    print(f"destilando con {len(a)} casos; verificando con {len(b)} distintos…", flush=True)
    r1 = ia.generar_json(DESTILAR, f"ESTADÍSTICAS:\n{estadisticas(casos)}\n\nMUESTRA:\n\n{bloque(a)}", ESQ_MANUAL,
                         modelos=MODELOS_FUERTES, temperatura=0.2)
    r2 = ia.generar_json(VERIFICAR, f"MANUAL:\n{r1['manual']}\n\nKEYMONITOR REALES QUE NO VIO:\n\n{bloque(b)}", ESQ_VERIF,
                         modelos=MODELOS_FUERTES, temperatura=0.2)
    texto = (f"# Manual del {producto} (v0, BORRADOR para que lo corrija el equipo)\n\n"
             f"_Destilado el {cerebro.ahora()[:10]} de {len(a)} {producto} reales y verificado con {len(b)} distintos "
             f"(modelo {r2.get('modelo') or r1.get('modelo') or 'Gemini'}). Ningún par del examen se usó._\n\n"
             + r2["manual"].strip() + "\n" + PANAMA)
    ruta = os.path.join(CARPETA, producto, "MANUAL.md")
    open(ruta, "w", encoding="utf-8").write(texto)
    json.dump({"cambios_verificacion": r2["cambios"], "muestra": sorted(vistos), "verificacion": [d["carpeta"] for d in b]},
              open(os.path.join(CARPETA, producto, "manual_origen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return f"{ruta} ({len(texto)} caracteres; {len(r2['cambios'])} correcciones en la verificación)"


if __name__ == "__main__":
    cerebro.cargar_env()
    orden, producto = (sys.argv[1:3] + ["", "Keymonitor"])[:2] if len(sys.argv) > 1 else ("", "Keymonitor")
    if orden == "separar":
        print(separar(producto))
    elif orden == "manual":
        print(separar(producto))
        print(manual(producto))
    else:
        print(__doc__)
