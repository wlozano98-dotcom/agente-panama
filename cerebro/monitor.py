"""Monitor de medios (Paula): manda al chat el ENLACE de las noticias importantes, nada más (Andrés, 2026-10-25: no
resume ni guarda; solo avisa). Mientras no exista el chat de la oficina, el chat es Telegram.

Uso: python3 cerebro/monitor.py        (una revisión; la mesa de la Mac lo corre cada 15 minutos, de 6:00 a 22:00)
Lee los RSS de La Prensa, TVN y Telemetro (investigación de ChatGPT, Invesitgacion/…report 3.md). Gemini mira solo los
titulares nuevos y marca los que importan a un cliente empresarial (Gobierno, Asamblea, economía, regulación, actores
del cerebro, sectores). De lo demás solo se recuerda que ya se vio (tabla monitor_vistos, 3 días). También revisa las
publicaciones de X que trae el Chrome de la oficina (cerebro/redes.py: listas de medios y autoridades) y, con ellas,
Diego arma la agenda de medios (invitados y apariciones anunciados).
"""
import html
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cerebro  # noqa: E402
from cerebro import ia  # noqa: E402
from db import d1  # noqa: E402

NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
FEEDS = [
    ("La Prensa", "https://www.prensa.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("TVN", "https://www.tvn-2.com/rss/"),
    ("Telemetro", "https://www.telemetro.com/rss/pages/nacionales.xml"),
    ("Telemetro", "https://www.telemetro.com/rss/pages/economia.xml"),
]
# reglas sacadas del chat real del equipo (Invesitgacion/guia_agente_noticias_keyword.md: 5.491 enlaces de 2025 en
# Ecuador), adaptadas a Panamá
FILTRO = """Eres Paula, monitora de medios de Keyword (consultora de asuntos públicos en Panamá). Recibes titulares nuevos.
Marca SOLO los que el equipo compartiría en su chat, en este orden de prioridad:
1. Gobierno y política: decisiones del Presidente y ministros, nombramientos, elecciones y alianzas.
2. Asamblea y justicia: proyectos, votaciones, vetos, fallos de la Corte, Contraloría y otros organismos de control.
3. Regulación: decretos, impuestos, tarifas, permisos y resoluciones de reguladores.
4. Economía y empresas: deuda, presupuesto, comercio, energía, Canal, minería, inversión, cifras oficiales nuevas.
5. Declaraciones sustantivas y verificables de autoridades, partidos o gremios.
6. Conflictos o emergencias con impacto operativo o político (protestas, paros, cierres).
7. Hechos internacionales con repercusión concreta en Panamá (aranceles, listas, acuerdos).
También recibes publicaciones de X (medio "X @cuenta") de medios, autoridades e instituciones: trátalas igual que
un titular. De una autoridad o institución marca lo que es NOTICIA: anuncios, decisiones, cifras, medidas,
nombramientos, posturas nuevas, su AGENDA de actividades del día y las reuniones con contenido (con gremios,
empresas, sindicatos, organismos, otros gobiernos o diputados, visitas de obra, firmas de acuerdos), aunque vengan
como foto del acto. No marques lo puramente de cortesía: saludos, felicitaciones, efemérides, condolencias, campañas
genéricas de la institución ni fotos sin tema.
NO marques: deportes, farándula, entretenimiento, curiosidades, accidentes comunes, sucesos policiales aislados,
publicidad o notas comerciales de una empresa, clima rutinario, rumores ni opiniones sin hechos nuevos. Si varios
titulares cuentan el mismo hecho, marca solo uno (una fuente por hecho).
También recibes lo YA ENVIADO al chat en los últimos 3 días: no marques un titular que cuenta un hecho ya enviado
(aunque sea de otro medio u otro día), salvo que traiga un dato nuevo que cambie o complete la noticia (una cifra,
una fecha, una decisión, una reacción importante)."""
ESQUEMA = {"type": "object", "properties": {"importantes": {"type": "array", "items": {"type": "string"},
                                                            "description": "ids de los titulares importantes"}},
           "required": ["importantes"]}


def titulares():
    out, vistos = [], set()
    for medio, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
            rss = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  {medio}: no respondió ({e})", flush=True)
            continue
        for it in re.findall(r"<item>(.*?)</item>", rss, re.S):
            limpio = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", t or "")))).strip()
            titulo = limpio((re.findall(r"<title>(.*?)</title>", it, re.S) or [""])[0])
            enlace = limpio((re.findall(r"<link>(.*?)</link>", it, re.S) or [""])[0])
            if enlace and enlace not in vistos:
                vistos.add(enlace)
                out.append({"id": cerebro.huella("monitor", enlace), "medio": medio, "titulo": titulo, "url": enlace})
    return out


def criterio_equipo(n=30, forzar=False):
    """Lo que el equipo marcó en el chat (👍 sirvió / 👎 no lo manden) a los enlaces de Paula: se suma a su filtro para
    que aprenda qué le interesa al equipo. Solo con el aprendizaje encendido (cerebro/aprendizaje.py)."""
    from cerebro import aprendizaje
    e = aprendizaje.para_agente("monitor")
    if not e["activo"] and not forzar:
        return ""
    try:
        filas = d1.consulta("SELECT texto, SUM(valor) AS v FROM reacciones WHERE agente = 'monitor' AND texto != '' AND creado >= ? "
                            "GROUP BY chat, mensaje ORDER BY MAX(creado) DESC LIMIT ?", ["" if forzar else e["desde"] or "", n * 2])
    except Exception:
        return ""
    si = [f["texto"] for f in filas if f["v"] > 0][:n]
    no = [f["texto"] for f in filas if f["v"] < 0][:n]
    if not si and not no:
        return ""
    return ("\n\nCRITERIO DEL EQUIPO (reacciones en el chat; aprende de esto y aplícalo a temas parecidos):" +
            ("\nLe SIRVIÓ (👍):\n" + "\n".join("- " + x for x in si) if si else "") +
            ("\nNO le sirvió, no mandes cosas así (👎):\n" + "\n".join("- " + x for x in no) if no else ""))


def revisar():
    d1.consulta("CREATE TABLE IF NOT EXISTS monitor_vistos (id TEXT PRIMARY KEY, medio TEXT, titulo TEXT, url TEXT, "
                "enviado INTEGER, creado TEXT)")
    d1.consulta("DELETE FROM monitor_vistos WHERE creado < datetime('now', '-3 days')")
    from cerebro import redes
    ya = {f["id"] for f in d1.consulta("SELECT id FROM monitor_vistos")}
    # memoria de lo ya enviado (Andrés, 2026-10-25: el mismo hecho en otro medio u otro día no se reenvía salvo novedad)
    enviado_antes = "\n".join(f"- [{f['medio']}] {f['titulo']}" for f in d1.consulta(
        "SELECT medio, titulo FROM monitor_vistos WHERE enviado = 1 ORDER BY creado DESC LIMIT 120")) or "(nada)"
    posts = redes.tomar()
    nuevos = [t for t in titulares() + redes.como_titulares(posts) if t["id"] not in ya]
    criterio = criterio_equipo()
    primera = not ya  # la primera vez solo se toma nota de lo que hay (no se manda el archivo de días anteriores)
    enviados = []
    try:
        if nuevos and not primera:
            for i in range(0, len(nuevos), 60):
                grupo = nuevos[i:i + 60]
                r = ia.generar_json(FILTRO + criterio, f"YA ENVIADO (últimos 3 días):\n{enviado_antes}\n\nTITULARES NUEVOS:\n" +
                                    "\n".join(f"{t['id']}: [{t['medio']}] {t['titulo']}" for t in grupo), ESQUEMA)
                marcados = set(r["importantes"])
                enviados += [t for t in grupo if t["id"] in marcados]
    except Exception:
        redes.devolver(posts)  # sin Gemini: las publicaciones esperan a la próxima vuelta (los RSS se releen solos)
        raise
    agenda = ""
    if posts:
        try:
            agenda = " · Diego: " + redes.agenda(posts)
        except Exception as e:
            agenda = f" · Diego: {e}"
    if enviados:
        for t in enviados[:15]:  # un mensaje por enlace: Telegram solo arma la vista previa (titular) con uno
            cerebro.telegram_pausado(t["url"], vista_previa=True, destino="general", ref="url:" + t["url"], agente="monitor")
    d1.insertar_muchas("monitor_vistos", ["id", "medio", "titulo", "url", "enviado", "creado"],
                       [[t["id"], t["medio"], t["titulo"], t["url"], 1 if t in enviados else 0, cerebro.ahora()] for t in nuevos],
                       modo="INSERT OR IGNORE")
    return f"{len(nuevos)} titulares nuevos ({len(posts)} de X), {len(enviados)} enviados al chat{agenda}"


def comparar(dias=3, limite=120):
    """La PRUEBA de que Paula aprende (para la demo): los mismos titulares de los últimos días filtrados dos veces, sin y
    con el criterio del equipo (reacciones 👍/👎). Lo que cambia de decisión es lo que aprendió. No manda nada al chat."""
    criterio = criterio_equipo(forzar=True)
    if not criterio:
        return "Todavía no hay reacciones del equipo a los enlaces de Paula."
    filas = d1.consulta("SELECT id, medio, titulo FROM monitor_vistos WHERE creado >= datetime('now', ?) ORDER BY creado DESC LIMIT ?",
                        [f"-{dias} days", limite])
    lista = "\n".join(f"{t['id']}: [{t['medio']}] {t['titulo']}" for t in filas)
    # temperatura 0 y el mismo modelo: lo que cambia sale del criterio del equipo, no del azar
    antes = set(ia.generar_json(FILTRO, "TITULARES:\n" + lista, ESQUEMA, temperatura=0)["importantes"])
    despues = set(ia.generar_json(FILTRO + criterio, "TITULARES:\n" + lista, ESQUEMA, temperatura=0)["importantes"])
    t = {f["id"]: f"[{f['medio']}] {f['titulo']}" for f in filas}
    salida = [f"{len(filas)} titulares de los últimos {dias} días · sin aprendizaje: {len(antes)} al chat · con aprendizaje: {len(despues)}",
              criterio.strip(), "", "AHORA SÍ LOS MANDARÍA (antes no):"] + [f"  + {t[i]}" for i in despues - antes] + \
             ["", "AHORA YA NO LOS MANDARÍA (antes sí):"] + [f"  - {t[i]}" for i in antes - despues]
    return "\n".join(salida)


if __name__ == "__main__":
    cerebro.cargar_env()
    print(comparar() if "--comparar" in sys.argv else revisar())
