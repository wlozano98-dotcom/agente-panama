"""La Diseñadora: Keyperfil en PDF con el modelo de Keyword (la tira vertical de sus Keyperfil reales).

armar(entidad, expediente) → ruta del PDF en salidas/keyperfil/. El sistema de diseño vive fuera del repo (es de
Keyword): su carpeta se toma de KEYWORD_DISENO (.env).
"""
import datetime
import html
import json
import os
import re
import subprocess

CARPETA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISENO = os.environ.get("KEYWORD_DISENO", "")  # en .env (la carpeta está fuera del repo)
NAVEGADOR = os.environ.get("NAV_PYTHON") or os.path.expanduser("~/.venvs/nav/bin/python")
MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()

CSS = """
:root { --titulo: #6552e6; --texto: #3c3d4a; --barra: linear-gradient(#9a6af6, #7f9cf8); }
@page { margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; width: 560px; }
body { font-family: "Open Sans", Arial, sans-serif; color: var(--texto); font-size: 11.5px; line-height: 1.5;
       background: linear-gradient(180deg, #e7eaff 0%, #eef0ff 45%, #f3f3ff 100%); padding: 26px 24px 30px; }
.antetitulo { font-family: Montserrat, sans-serif; font-weight: 300; font-size: 12px; letter-spacing: .32em; color: #4b4f8a; margin: 0 0 14px 6px; }
.persona { display: flex; align-items: center; gap: 22px; margin: 0 6px 22px; }
.foto { width: 96px; height: 96px; border-radius: 50%; overflow: hidden; flex: none; background: #d4d8f5; border: 3px solid #fff;
        box-shadow: 0 6px 16px rgb(60 60 120 / .18); display: flex; align-items: center; justify-content: center;
        font: 700 30px "Figtree", sans-serif; color: var(--titulo); }
.foto img { width: 100%; height: 100%; object-fit: cover; object-position: center 18%; }
.nombre { flex: 1; background: #fff; border-radius: 10px; box-shadow: 0 6px 18px rgb(60 60 120 / .08); text-align: center; padding: 12px 14px 0; }
.nombre h1 { font: 700 16.5px/1.25 "Figtree", sans-serif; color: #15162a; margin: 0 0 9px; letter-spacing: -.005em; }
.nombre .cargo { border-top: 1px solid #e6e6f2; padding: 7px 0 9px; font-size: 11.5px; color: #6d6f86; }
.tarjeta { position: relative; border-radius: 16px; padding: 26px 34px 22px 34px; margin-bottom: 20px;
           background: linear-gradient(180deg, rgb(255 255 255 / .92), rgb(244 245 255 / .92));
           box-shadow: 0 10px 28px rgb(70 70 140 / .10); break-inside: avoid; }
.tarjeta h2 { font: 700 20px/1.2 "Figtree", sans-serif; color: var(--titulo); margin: 4px 0 20px; letter-spacing: -.01em; }
.tarjeta .icono { position: absolute; top: 14px; right: 26px; width: 74px; }
.hito { position: relative; padding-left: 18px; margin: 0 0 13px; text-align: justify; }
.hito::before { content: ""; position: absolute; left: 0; top: 2px; bottom: 2px; width: 4px; background: var(--barra); }
.hito b { color: #111; font-weight: 700; }
ul { list-style: none; padding: 0; margin: 0; }
li { position: relative; padding-left: 22px; margin: 0 0 13px; text-align: justify; }
li::before { content: ""; position: absolute; left: 2px; top: 6px; width: 7px; height: 7px; border-radius: 50%; background: #7a68ee; }
.logo { display: block; margin: 26px auto 0; width: 112px; height: auto; }
.logo path, .logo rect, .logo circle, .logo polygon { fill: #2e3566; }
"""


def fecha_larga(d=None):
    d = d or datetime.date.today()
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _e(t):
    return html.escape(t or "")


def _refs(fuentes):
    return "".join(f'<span class="fuente-ref">[{n}]</span>' for n in sorted(set(fuentes or [])))


def _desde(x):
    """Orden de los trabajos, del más nuevo al más viejo: por el año en que terminó. "Presente" va primero; "Desde
    2009" solo cuenta como actual si dice presente o actual (si no, la investigación no trajo el fin y se usa el año)."""
    anos = re.findall(r"\d{4}", x.get("periodo") or "")
    hasta = 9999 if not anos or re.search(r"presente|actual", x.get("periodo") or "", re.I) else int(anos[-1])
    return (hasta, int(anos[0]) if anos else 0)


def iniciales(nombre):
    p = [x for x in nombre.split() if x[0].isupper()]
    return (p[0][0] + (p[-2][0] if len(p) >= 3 else p[-1][0] if len(p) > 1 else "")).upper()


def pagina(exp, foto=None):
    """Keyperfil con el modelo de Keyword: una tira vertical (PERFIL, foto y nombre, Principales estudios, Principales
    trabajos y Datos de Interés con sus íconos, logo al pie)."""
    activos = os.path.join(CARPETA, "ejemplos", "keyword", "keyperfil")  # íconos del modelo (de Keyword, no se suben)
    logo = open(os.path.join(DISENO, "Manual de marca oficial", "01-logo", "svg", "keyword-negro.svg"), encoding="utf-8").read()
    logo = re.sub(r'fill="#(?:000|000000|18191F|050505)"', 'fill="#2e3566"', logo, flags=re.I).replace("<svg", '<svg class="logo"', 1)

    def icono(n):
        ruta = os.path.join(activos, n + ".png")
        return f"<img class='icono' src='file://{ruta}'>" if os.path.exists(ruta) else ""

    partes = []
    if exp.get("estudios"):
        partes.append("<section class='tarjeta'>" + icono("birrete") + "<h2>Principales estudios:</h2>" + "".join(
            f"<div class='hito'>{_e(s)}</div>" for s in exp["estudios"]) + "</section>")
    if exp.get("experiencia"):
        partes.append("<section class='tarjeta'>" + icono("foco") + "<h2>Principales trabajos:</h2>" + "".join(
            f"<div class='hito'><b>{_e(x['periodo'])}:</b> {_e(x['cargo'])}</div>" for x in sorted(exp["experiencia"], key=lambda x: (x["cargo"] == exp.get("cargo"), _desde(x)), reverse=True)) + "</section>")
    datos = ([exp["resumen"]] if exp.get("resumen") else []) + [x["texto"] for x in exp.get("datos_interes", [])] + \
        [f"{x['tema']}: {x['postura']}" for x in exp.get("posturas", [])]
    if datos:
        partes.append("<section class='tarjeta'>" + icono("info") + "<h2>Datos de Interés</h2><ul>" + "".join(
            f"<li>{_e(t)}</li>" for t in datos) + "</ul></section>")
    retrato = f"<img src='{foto}'>" if foto else _e(iniciales(exp["nombre"]))
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@700&family=Montserrat:wght@300&family=Open+Sans:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="antetitulo">PERFIL</div>
<div class="persona"><div class="foto">{retrato}</div>
  <div class="nombre"><h1>{_e(exp['nombre'])}</h1><div class="cargo">{_e(exp.get('cargo'))}</div></div></div>
{''.join(partes)}
{logo}
</body></html>"""


def a_pdf(ruta_html, ruta_pdf):
    """Imprime el HTML a PDF con el Chromium local (Playwright): una sola página del alto del contenido, como el modelo."""
    codigo = ("import sys\nfrom playwright.sync_api import sync_playwright\n"
              "with sync_playwright() as p:\n"
              "    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 560, 'height': 800})\n"
              "    pg.goto('file://' + sys.argv[1]); pg.wait_for_load_state('networkidle')\n"
              "    alto = pg.evaluate('document.documentElement.scrollHeight')\n"
              "    pg.pdf(path=sys.argv[2], width='560px', height=str(alto + 2) + 'px', print_background=True,"
              " margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})\n    b.close()\n")
    subprocess.run([NAVEGADOR, "-c", codigo, ruta_html, ruta_pdf], check=True)


def armar(entidad, expediente, foto=None):
    carpeta = os.path.join(CARPETA, "salidas", "keyperfil")
    os.makedirs(carpeta, exist_ok=True)
    slug = entidad['id'].split(':', 1)[1]
    base = os.path.join(carpeta, f"{datetime.date.today().isoformat()}_{slug}")
    if not foto:  # foto oficial guardada a mano (ejemplos/keyword/keyperfil/fotos/<slug>.jpg; no se sube)
        ruta = os.path.join(CARPETA, "ejemplos", "keyword", "keyperfil", "fotos", slug + ".jpg")
        foto = "file://" + ruta if os.path.exists(ruta) else None
    open(base + ".html", "w", encoding="utf-8").write(pagina(expediente, foto))
    a_pdf(base + ".html", base + ".pdf")
    json.dump(expediente, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return base + ".pdf"
