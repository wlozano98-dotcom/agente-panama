// Keyword · Chrome de la oficina. Cada 20 minutos (de 7:00 a 22:00) abre en una pestaña de fondo, como lo haría una
// persona, la portada de la Gaceta Oficial y la web de la Corte, y manda lo nuevo a la Mac de la oficina
// (cerebro/receptor_gaceta.py, en 127.0.0.1:8765): cada edición de la Gaceta (Inés la lee), los edictos del Pleno y las
// noticias de la Corte (Elena). Si una web pide verificación ("Soy humano"), no la toca: avisa para que una persona
// la pase en este Chrome; después sigue sola.
// Redes (desde la v1.6): cada 15 minutos (de 6:00 a 22:00) lee las dos listas privadas de X de la cuenta de la oficina
// (Medios Panamá y Autoridades Panamá) y manda las publicaciones a la Mac (Paula y Diego las revisan). Si X cerró la
// sesión, avisa para que una persona vuelva a entrar.
const CORTE = "https://www.organojudicial.gob.pa";
const EDICTOS = CORTE + "/files/edictos-de-salas-y-tribunales-superiores/corte-suprema-de-justicia-edictos/pleno-de-la-corte-suprema-de-justicia-edictos";
const MAC = "http://127.0.0.1:8765";
const GACETA = "https://www.gacetaoficial.gob.pa/";
const ASAMBLEA = "https://www.asamblea.gob.pa/";

const LISTAS_X = { medios: "2114583852370850260", autoridades: "2114584467381616745" };

function alarmas() {
  chrome.alarms.create("corte", { periodInMinutes: 20, delayInMinutes: 1 });
  chrome.alarms.create("redes", { periodInMinutes: 15, delayInMinutes: 2 });
}
chrome.runtime.onInstalled.addListener(alarmas);
chrome.runtime.onStartup.addListener(alarmas);
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === "corte") revisar(false);
  if (a.name === "redes") revisarRedes(false);
});
chrome.action.onClicked.addListener(() => { revisar(true); revisarRedes(true); });

function avisar(titulo, mensaje) {
  chrome.notifications.create({ type: "basic", iconUrl: "icono128.png", title: titulo, message: mensaje });
}

// corre DENTRO de la pestaña de la Corte (mismo sitio): lee las listas y baja lo que la Mac todavía no tiene
async function recolectar(edictosUrl, vistos) {
  const ya = new Set(vistos), out = { edictos: [], comunicados: [], bloqueo: false };
  // verificación = la web manda a la página de Radware (perfdrive) o responde 403/429; otro error (p. ej. una nota que ya
  // no existe) solo se salta
  const leer = async (url) => {
    const r = await fetch(url, { credentials: "include" }).catch(() => null);
    if (r && (/perfdrive|validate/.test(r.url) || r.status === 403 || r.status === 429)) { out.bloqueo = true; return null; }
    return r && r.ok ? r : null;
  };
  const lista = await leer(edictosUrl);
  if (!lista) return out;  // sin lista no hay nada que hacer (si fue verificación, out.bloqueo ya está marcado)
  const doc = new DOMParser().parseFromString(await lista.text(), "text/html");
  const pdfs = [...new Set([...doc.querySelectorAll("a")].map((a) => a.href).filter((h) => /\/uploads\/.*edicto.*\.pdf$/i.test(h)))];
  for (const url of pdfs.filter((u) => !ya.has(u)).slice(0, 4)) {
    const r = await leer(url); if (!r) { if (out.bloqueo) break; continue; }
    const b = new Uint8Array(await r.arrayBuffer());
    let bin = ""; for (let i = 0; i < b.length; i += 8192) bin += String.fromCharCode(...b.subarray(i, i + 8192));
    const nombre = decodeURIComponent(url.split("/").pop().replace(/\.pdf$/i, "")).replace(/-/g, " ");
    out.edictos.push({ url, titulo: nombre.charAt(0).toUpperCase() + nombre.slice(1), pdf: btoa(bin) });
  }
  const noticias = await leer(location.origin + "/noticias");
  if (!noticias) return out;
  const nd = new DOMParser().parseFromString(await noticias.text(), "text/html");
  const enlaces = new Map();
  nd.querySelectorAll("a").forEach((a) => {
    const t = a.textContent.trim().replace(/\s+/g, " ");
    if (/\/noticias\/[a-z0-9-]{12,}$/.test(a.href) && t.length > 15 && !enlaces.has(a.href)) enlaces.set(a.href, t);
  });
  for (const [url, titulo] of [...enlaces].filter(([u]) => !ya.has(u)).slice(0, 12)) {
    const r = await leer(url); if (!r) { if (out.bloqueo) break; continue; }
    out.comunicados.push({ url, titulo, html: await r.text() });
  }
  return out;
}

// corre DENTRO de la pestaña de la Gaceta: las ediciones de la portada que la Mac no tiene (la portada muestra las 5 últimas)
async function recolectarGaceta(ya) {
  const out = { ediciones: [], bloqueo: false };
  // la portada dibuja las ediciones unos segundos después de cargar: se espera hasta 20 s antes de decidir
  let enlaces = [];
  for (let i = 0; i < 20 && !enlaces.length; i++) {
    enlaces = [...document.querySelectorAll("a")].filter((a) => /^\d{5}( [A-Z])?$/.test(a.innerText.trim())).map((a) => a.href);
    if (!enlaces.length) await new Promise((ok) => setTimeout(ok, 1000));
  }
  if (!enlaces.length) {  // sin ediciones: solo es verificación si se ve la casilla
    out.bloqueo = !!document.querySelector('iframe[src*="hcaptcha"], iframe[src*="captcha"]') || /soy humano|no soy un robot|verify you are human/i.test(document.body.innerText);
    return out;
  }
  for (const url of enlaces) {
    const numero = (/gacetas\/\d{4}\/\d{2}\/(\d{5}(?:_[A-Z])?)\//.exec(url) || [])[1];
    if (!numero || ya.includes(numero)) continue;
    const r = await fetch(url, { credentials: "include" });
    const b = new Uint8Array(await r.arrayBuffer());
    if (String.fromCharCode(...b.subarray(0, 4)) !== "%PDF") { out.bloqueo = true; break; }
    let bin = ""; for (let i = 0; i < b.length; i += 8192) bin += String.fromCharCode(...b.subarray(i, i + 8192));
    out.ediciones.push({ numero, url, pdf: btoa(bin) });
  }
  return out;
}

async function leerEn(tab, func, args) {
  for (let intento = 0; intento < 2; intento++) {
    try {
      const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func, args });
      return result;
    } catch (e) {
      if (intento) throw e;
      await new Promise((ok) => setTimeout(ok, 5000));
    }
  }
}

async function abrir(url) {
  const tab = await chrome.tabs.create({ url, active: false });
  await new Promise((ok) => {
    const fin = setTimeout(ok, 40000);
    chrome.tabs.onUpdated.addListener(function f(id, info) {
      if (id === tab.id && info.status === "complete") { clearTimeout(fin); chrome.tabs.onUpdated.removeListener(f); ok(); }
    });
  });
  return tab;
}

async function revisarGaceta(aMano) {
  let ya;
  try { ya = await (await fetch(MAC + "/tengo")).json(); } catch (e) { return; }
  const tab = await abrir(GACETA);
  try {
    const t = await chrome.tabs.get(tab.id);
    let res = { ediciones: [], bloqueo: true };
    if (t.url.startsWith(GACETA)) res = await leerEn(tab, recolectarGaceta, [ya]);
    if (res.bloqueo) {
      await fetch(MAC + "/judicial/alerta?que=gaceta", { method: "POST" });
      avisar("La Gaceta pide «Soy humano»", "Abre gacetaoficial.gob.pa en este Chrome y marca la casilla; después sigue sola.");
    }
    for (const e of res.ediciones) {
      const bytes = Uint8Array.from(atob(e.pdf), (c) => c.charCodeAt(0));
      await fetch(`${MAC}/gaceta?numero=${e.numero}&url=${encodeURIComponent(e.url)}`, { method: "POST", body: bytes });
    }
    if (aMano) avisar("Gaceta revisada", `${res.ediciones.length} ediciones nuevas enviadas a la Mac.`);
    resumen.gaceta = res.bloqueo ? "pide verificación" : `${res.ediciones.length} ediciones nuevas`;
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}

// lo que encontró cada revisión, para que la Mac sepa que la extensión está trabajando
const resumen = {};
async function revisar(aMano) {
  const h = new Date().getHours();
  if (!aMano && (h < 7 || h >= 22)) return;
  resumen.gaceta = "error"; resumen.corte = "error";
  await revisarGaceta(aMano).catch((e) => { resumen.gaceta = "error: " + e.message; });
  await revisarCorte(aMano).catch((e) => { resumen.corte = "error: " + e.message; });
  await revisarBoletines().catch((e) => { resumen.boletines = "error: " + e.message; });
  await fetch(`${MAC}/extension/latido?gaceta=${encodeURIComponent(resumen.gaceta)}&corte=${encodeURIComponent(resumen.corte)}&boletines=${encodeURIComponent(resumen.boletines || "?")}&a_mano=${aMano ? 1 : 0}`, { method: "POST" }).catch(() => {});
}

async function revisarCorte(aMano) {
  let vistos;
  try { vistos = await (await fetch(MAC + "/judicial/vistos")).json(); }
  catch (e) { if (aMano) avisar("La Mac no responde", "El receptor de la oficina (receptor_gaceta.py) no está encendido."); return; }
  const tab = await abrir(EDICTOS);
  try {
    const t = await chrome.tabs.get(tab.id);
    let res;
    if (!t.url.startsWith(CORTE)) res = { edictos: [], comunicados: [], bloqueo: true };
    else res = await leerEn(tab, recolectar, [EDICTOS, vistos]);
    if (res.bloqueo) {
      await fetch(MAC + "/judicial/alerta?que=corte", { method: "POST" });
      avisar("La Corte pide verificación", "Abre organojudicial.gob.pa en este Chrome y pásala; después sigue sola.");
    }
    for (const e of res.edictos) {
      const bytes = Uint8Array.from(atob(e.pdf), (c) => c.charCodeAt(0));
      await fetch(`${MAC}/judicial/edicto?url=${encodeURIComponent(e.url)}&titulo=${encodeURIComponent(e.titulo)}`, { method: "POST", body: bytes });
    }
    for (const c of res.comunicados) {
      await fetch(`${MAC}/judicial/comunicado?url=${encodeURIComponent(c.url)}&titulo=${encodeURIComponent(c.titulo)}`, { method: "POST", body: c.html });
    }
    if (aMano) avisar("Corte revisada", `${res.edictos.length} edictos y ${res.comunicados.length} comunicados nuevos enviados a la Mac.`);
    resumen.corte = res.bloqueo ? "pide verificación" : `${res.edictos.length} edictos y ${res.comunicados.length} comunicados nuevos`;
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}

// corre DENTRO de la pestaña de la lista de X: espera las publicaciones, baja un poco y las junta (más nuevas primero)
async function recolectarX() {
  const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));
  for (let i = 0; i < 30 && !document.querySelector("article"); i++) {
    if (location.pathname.startsWith("/i/flow/login") || document.querySelector('[data-testid="loginButton"]')) return { bloqueo: true, posts: [] };
    await espera(500);
  }
  const posts = new Map();
  for (let vuelta = 0; vuelta < 6; vuelta++) {
    for (const a of document.querySelectorAll("article")) {
      const t = a.querySelector("time"), enlace = t && t.closest("a");
      if (!enlace) continue;
      const url = enlace.href.split("?")[0], m = /x\.com\/([^/]+)\/status\/(\d+)/.exec(url);
      if (!m || posts.has(m[2])) continue;
      const contexto = a.querySelector('[data-testid="socialContext"]');
      posts.set(m[2], {
        id: m[2], url, cuenta: m[1], fecha: t.getAttribute("datetime"),
        nombre: ((a.querySelector('[data-testid="User-Name"]') || {}).innerText || "").split("\n")[0],
        texto: ((a.querySelector('[data-testid="tweetText"]') || {}).innerText || "").slice(0, 2000),
        repost: contexto ? contexto.innerText : "",
        // fotos en tamaño grande: la Asamblea publica la agenda del día en imágenes (cerebro/agenda_x.py)
        fotos: [...a.querySelectorAll('[data-testid="tweetPhoto"] img')].map((i) => i.src.replace(/name=\w+/, "name=large")),
      });
    }
    window.scrollBy(0, 2500);
    await espera(1500);
  }
  return { bloqueo: false, posts: [...posts.values()] };
}

async function revisarRedes(aMano) {
  const h = new Date().getHours();
  if (!aMano && (h < 6 || h >= 22)) return;
  const partes = [];
  for (const [lista, id] of Object.entries(LISTAS_X)) {
    const tab = await abrir(`https://x.com/i/lists/${id}`);
    try {
      const res = await leerEn(tab, recolectarX, []);
      if (res.bloqueo) {
        await fetch(MAC + "/judicial/alerta?que=x", { method: "POST" }).catch(() => {});
        avisar("X cerró la sesión", "Entra a x.com con la cuenta de la oficina en este Chrome; después sigue sola.");
        partes.push(`${lista}: sin sesión`);
        break;
      }
      const r = await fetch(`${MAC}/redes/posts?lista=${lista}`, { method: "POST", body: JSON.stringify(res.posts) });
      partes.push(`${lista}: ${await r.text()}`);
    } catch (e) {
      partes.push(`${lista}: error ${e.message}`);
    } finally {
      chrome.tabs.remove(tab.id).catch(() => {});
    }
  }
  await fetch(`${MAC}/extension/latido?redes=${encodeURIComponent(partes.join(" · "))}&a_mano=${aMano ? 1 : 0}`, { method: "POST" }).catch(() => {});
  if (aMano) avisar("Redes revisadas", partes.join(" · "));
}

// corre DENTRO de la web de la Asamblea (tiene anti-bots: se abre como una persona): los boletines de prensa recientes
async function recolectarBoletines() {
  const r = await fetch("/Data/Noticias/Client/0/List?page=1&pageSize=30&search=").catch(() => null);
  if (!r || !r.ok) return { bloqueo: true, boletines: [] };
  const datos = await r.json().catch(() => ({}));
  return { bloqueo: false, boletines: (datos.data || []).map((x) => ({ id: String(x.ID), fecha: (x.FechaEdit || "").slice(0, 10),
    titulo: x.Titulo || "", url: "https://www.asamblea.gob.pa/Noticias/Noticias/" + (x.Slug || "") })) };
}

// los boletines de prensa de la Asamblea: la Mac manda cada enlace nuevo al chat de la Asamblea
async function revisarBoletines() {
  const tab = await abrir(ASAMBLEA);
  try {
    const t = await chrome.tabs.get(tab.id);
    const res = t.url.startsWith(ASAMBLEA) ? await leerEn(tab, recolectarBoletines, []) : { bloqueo: true, boletines: [] };
    if (res.bloqueo) { resumen.boletines = "no se pudo leer"; return; }
    const r = await fetch(MAC + "/asamblea/boletines", { method: "POST", body: JSON.stringify(res.boletines) });
    resumen.boletines = await r.text();
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}
