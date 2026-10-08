"""Lectura del Seguimiento Legislativo de la Asamblea Nacional de Panamá (solo lectura, información pública).

https://sistemas.asamblea.gob.pa/segLegis/viewsPublico/SeguimientoLegislativo es una página ASP.NET WebForms:
cada acción (buscar, cambiar de página, ver etapas) es un POST con los campos ocultos de la página anterior.
El estado vive en esos campos (__VIEWSTATE), así que desde una misma página se pueden hacer varios POST.

- La lista trae 20 fichas por página, las más nuevas primero. El paginador solo acepta las páginas que muestra
  (de a 10): se recorre página por página.
- Los filtros (comisión, etapa) hay que reenviarlos en cada cambio de página o se pierden.
- "Ver etapas" (dataTable$ctlNN$Button3) devuelve el historial de la ficha con fecha, etapa y comentario.
- El texto presentado está en /segLegis/Documents/<ficha>.pdf (no todas las fichas lo tienen).

Uso de prueba:
    python3 seglegis.py            # resumen de la lista completa
    python3 seglegis.py 8543       # historial de etapas de una ficha
"""
import datetime
import html
import http.cookiejar
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://sistemas.asamblea.gob.pa/segLegis"
URL = BASE + "/viewsPublico/SeguimientoLegislativo"
COLUMNAS = ["fecha", "ficha", "proyecto", "anteproyecto", "titulo", "etapa", "proponente"]
MESES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                         "septiembre", "octubre", "noviembre", "diciembre"])}


def url_pdf(ficha):
    return f"{BASE}/Documents/{ficha}.pdf"


def limpiar(texto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))).strip()


def fecha_iso(texto):
    """'08-10-2026' o '31-agosto-2026' → '2026-10-08'."""
    d, m, a = texto.strip().split("-")
    mes = int(m) if m.isdigit() else MESES[m.lower()]
    return datetime.date(int(a), mes, int(d)).isoformat()


class Seguimiento:
    def __init__(self, pausa=0.2):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", "Mozilla/5.0 (agente de monitoreo legislativo)")]
        self.pausa = pausa  # cortesía con el servidor entre pedidos
        self.pedidos = 0

    def _abrir(self, datos=None):
        for intento in range(4):
            try:
                self.pedidos += 1
                time.sleep(self.pausa)
                with self.op.open(URL, datos, timeout=90) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError:
                raise  # un 500 es un pedido inválido (p. ej. página fuera del paginador): no se reintenta
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if intento == 3:
                    raise
                print(f"  seglegis: {e}; reintento", flush=True)
                time.sleep(5 * (intento + 1))

    @staticmethod
    def _campos(pagina):
        c = {}
        for m in re.finditer(r'<input[^>]+type="hidden"[^>]*>', pagina):
            n = re.search(r'name="([^"]+)"', m.group(0))
            v = re.search(r'value="([^"]*)"', m.group(0))
            if n:
                c[n.group(1)] = html.unescape(v.group(1)) if v else ""
        return c

    def _post(self, pagina, extra):
        datos = self._campos(pagina)
        datos.update(extra)
        return self._abrir(urllib.parse.urlencode(datos).encode())

    @staticmethod
    def opciones(pagina, select_id):
        sel = re.search(rf'<select[^>]+id="{select_id}"[\s\S]*?</select>', pagina)
        return [(v, limpiar(t)) for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel.group(0))
                if v.isdigit()]

    @staticmethod
    def filas(pagina):
        """Fichas de una página de resultados, con el nombre del control de su botón "Ver etapas"."""
        out = []
        for tr in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", pagina):
            celdas = [limpiar(td) for td in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]
            if len(celdas) != 9 or not re.match(r"\d\d-\d\d-\d{4}$", celdas[2]):
                continue
            f = dict(zip(COLUMNAS, celdas[2:]))
            f["fecha"] = fecha_iso(f["fecha"])
            boton = re.search(r'name="(dataTable\$ctl\d+\$Button3)"', tr)
            f["_boton_etapas"] = boton.group(1) if boton else None
            f["tiene_documento"] = bool(re.search(r'name="dataTable\$ctl\d+\$Button2"', tr))
            out.append(f)
        return out

    def inicio(self):
        return self._abrir()

    def recorrer(self, filtros=None, al_pasar=None):
        """Todas las fichas (con filtros opcionales, p. ej. {"dlistComicion": "4"}). al_pasar(pagina, filas) se
        llama en cada página: sirve para pedir etapas desde esa misma página."""
        p = self.inicio()
        if filtros:
            p = self._post(p, dict(filtros, __EVENTTARGET="btnFiltrar"))
        else:
            p = self._post(p, {"btnMostrarTodo": "🔎"})
        todas, n = [], 1
        while True:
            f = self.filas(p)
            if al_pasar:
                al_pasar(p, f)
            todas += f
            if f"Page${n + 1}" not in p:
                break
            n += 1
            p = self._post(p, dict(filtros or {}, __EVENTTARGET="dataTable", __EVENTARGUMENT=f"Page${n}"))
        vistas, unicas = set(), []
        for f in todas:  # por si una ficha cambia de página mientras se recorre
            if f["ficha"] not in vistas:
                vistas.add(f["ficha"])
                unicas.append(f)
        return unicas

    def etapas_desde(self, pagina, fila):
        """Historial de etapas de una ficha de la página: [{fecha, etapa, comentario}], la más nueva primero."""
        r = self._post(pagina, {fila["_boton_etapas"]: "Ver etapas"})
        panel = re.search(r'id="panelVerEtapas"[\s\S]*?</table>', r)
        if not panel:
            return []
        etapas = []
        for tr in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", panel.group(0)):
            c = [limpiar(td) for td in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]
            if len(c) >= 4 and c[0].isdigit():
                etapas.append({"fecha": fecha_iso(c[1]), "etapa": c[2], "comentario": c[3]})
        return etapas

    def comisiones(self):
        """{ficha: comisión} recorriendo el filtro de cada comisión (~1 min para las ~25 comisiones)."""
        p = self.inicio()
        por_ficha = {}
        for valor, nombre in self.opciones(p, "dlistComicion"):
            for f in self.recorrer({"dlistComicion": valor}):
                por_ficha[f["ficha"]] = nombre
        return por_ficha

    def etapas_de(self, ficha):
        """Historial de una sola ficha (busca por su número de proyecto o anteproyecto)."""
        for f in self.recorrer():
            if f["ficha"] == str(ficha):
                break
        else:
            return []
        filtro = {"txtProyecto": f["proyecto"]} if f["proyecto"] not in ("", "0") else {"txtAnteproyecto": f["anteproyecto"]}
        encontrado = {}

        def mirar(pagina, filas):
            for x in filas:
                if x["ficha"] == str(ficha) and not encontrado:
                    encontrado["etapas"] = self.etapas_desde(pagina, x)
        self.recorrer(filtro, mirar)
        return encontrado.get("etapas", [])

    def pdf(self, ficha):
        """Bytes del PDF de la ficha, o None si no tiene."""
        try:
            with self.op.open(url_pdf(ficha), timeout=180) as r:
                datos = r.read()
            return datos if datos[:4] == b"%PDF" else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise


if __name__ == "__main__":
    s = Seguimiento()
    if len(sys.argv) > 1:
        for x in s.etapas_de(sys.argv[1]):
            print(x)
    else:
        t = time.time()
        todas = s.recorrer()
        print(len(todas), "fichas en", round(time.time() - t), "s,", s.pedidos, "pedidos")
        for f in todas[:3]:
            print({k: v for k, v in f.items() if not k.startswith("_")})
