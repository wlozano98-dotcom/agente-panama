// Kiwi, el asistente del Agente Panamá (Cloudflare Worker).
//
// - Telegram envía cada mensaje a este Worker (webhook). Si quien escribe está autorizado, Kiwi responde con los
//   datos de la base D1 (binding DB): fichas del Seguimiento Legislativo, historial de etapas, impacto por sector y
//   proponentes, más el análisis completo (.md) de Drive de las fichas que toque la pregunta.
// - /oficina?k=<OFICINA_CLAVE> sirve la oficina virtual y su API (mismo cerebro).
//
// Secretos (los sube bot/desplegar.py): TELEGRAM_TOKEN, WEBHOOK_SECRET, AUTORIZADOS (IDs de Telegram separados por
// coma), GEMINI_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, OFICINA_CLAVE, MATRIZ_ID.

const MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"];
const MAX_FICHAS = 5;          // fichas que se leen completas por pregunta
const MAX_LISTA = 60;          // filas que se le pasan a Gemini cuando la pregunta es un listado
const MAX_CARACTERES_MD = 25000;
const HORA_PANAMA = -5;        // UTC-5 todo el año

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/oficina")) return oficina(request, env, url);
    if (request.method !== "POST") return new Response("Agente Panamá: Kiwi activo");
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return new Response("no autorizado", { status: 403 });
    }
    const update = await request.json();
    const msg = update.message;
    if (!msg || !msg.text || msg.chat.type !== "private") return new Response("ok");

    const autorizados = (env.AUTORIZADOS || "").split(",").map((s) => s.trim());
    if (!autorizados.includes(String(msg.from.id))) {
      await enviar(env, msg.chat.id,
        `No tienes acceso a este bot. Si deberías tenerlo, pásale este número a Andrés: ${msg.from.id}`);
      return new Response("ok");
    }
    const texto = msg.text.trim();
    if (texto === "/start" || texto === "/ayuda") {
      await enviar(env, msg.chat.id,
        "Hola, soy Kiwi 🥝 Te ayudo con el seguimiento de la Asamblea Nacional de Panamá. Por ejemplo:\n\n" +
        "• ¿Qué proyectos de impacto alto avanzaron esta semana?\n" +
        "• ¿Qué proyectos presentó Janine Prado?\n" +
        "• ¿En qué va el proyecto de inteligencia artificial?\n" +
        "• ¿Qué hay para el sector financiero en segundo debate?");
      return new Response("ok");
    }
    // Se responde dentro de la misma petición: Telegram espera y no reenvía el mensaje.
    try {
      await accion(env, msg.chat.id);
      const r = await responder(env, texto, [], () => accion(env, msg.chat.id));
      await enviar(env, msg.chat.id, r.respuesta);
    } catch (e) {
      console.log("error", e.stack || e);
      await enviar(env, msg.chat.id, "No pude responder ahora (la IA de Google puede estar saturada). Intenta de nuevo en un minuto.");
    }
    return new Response("ok");
  },
};

// ------------------------------------------------------------------ datos (D1)

const ORDEN_IMP = { alto: 0, medio: 1, bajo: 2, ninguno: 3 };
const memo = { t: 0, datos: null };

// Todas las fichas en forma compacta (para el índice) más listas de proponentes, comisiones y sectores.
// Se guardan 5 minutos en memoria para cuidar las lecturas de D1.
async function datos(env) {
  if (memo.datos && Date.now() - memo.t < 300000) return memo.datos;
  const [fichas, principales, personas, ultimos] = (await env.DB.batch([
    env.DB.prepare("SELECT ficha, proyecto, anteproyecto, COALESCE(titulo, titulo_oficial) AS titulo, fecha_presentacion, " +
      "comision, etapa, impacto, sectores, en_seguimiento, carpeta_url FROM proyectos"),
    env.DB.prepare("SELECT ficha, nombre, (SELECT COUNT(*) FROM proponentes y WHERE y.ficha = x.ficha) AS n " +
      "FROM proponentes x WHERE principal = 1"),
    env.DB.prepare("SELECT nombre, tipo, COUNT(*) AS n FROM proponentes WHERE tipo IN ('Diputado', 'Suplente') GROUP BY nombre, tipo"),
    env.DB.prepare("SELECT ficha, MAX(fecha) AS fecha FROM eventos GROUP BY ficha"),
  ])).map((r) => r.results);
  const princ = new Map(principales.map((p) => [p.ficha, p]));
  const ult = new Map(ultimos.map((u) => [u.ficha, u.fecha]));
  for (const f of fichas) {
    const p = princ.get(f.ficha);
    f.proponente = p ? (p.n > 1 ? `${p.nombre} y ${p.n - 1} más` : p.nombre) : "";
    f.ultima = ult.get(f.ficha) || f.fecha_presentacion || "";
    f.numero = numero(f);
  }
  fichas.sort((a, b) => b.ultima.localeCompare(a.ultima));
  memo.datos = {
    fichas, porFicha: new Map(fichas.map((f) => [f.ficha, f])),
    personas: personas.sort((a, b) => b.n - a.n),
    comisiones: [...new Set(fichas.map((f) => f.comision).filter(Boolean))].sort(),
    etapas: [...new Set(fichas.map((f) => f.etapa).filter(Boolean))].sort(),
  };
  memo.t = Date.now();
  return memo.datos;
}

function numero(f) {
  if (f.proyecto && f.proyecto !== "0") return `Proyecto ${f.proyecto}`;
  if (f.anteproyecto && f.anteproyecto !== "0") return `Anteproyecto ${f.anteproyecto}`;
  return `Ficha ${f.ficha}`;
}

const dma = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || ""); return m ? `${m[3]}/${m[2]}/${m[1]}` : iso || ""; };
const hoyPanama = () => new Date(Date.now() + HORA_PANAMA * 3600 * 1000).toISOString().slice(0, 10);

function lineaIndice(f) {
  return `${f.ficha} | ${f.numero} | ${f.etapa} | ${f.impacto || "sin analizar"} | ${f.comision || "—"} | ${f.titulo.slice(0, 140)}`;
}

// Ficha completa: datos, impacto por sector, proponentes, historial y análisis .md de Drive.
async function fichaCompleta(env, ficha, token) {
  const [p, evs, imps, props] = (await env.DB.batch([
    env.DB.prepare("SELECT * FROM proyectos WHERE ficha = ?").bind(ficha),
    env.DB.prepare("SELECT fecha, etapa, texto FROM eventos WHERE ficha = ? ORDER BY fecha DESC, id ASC").bind(ficha),
    env.DB.prepare("SELECT sector, nivel, razon FROM impactos WHERE ficha = ?").bind(ficha),
    env.DB.prepare("SELECT nombre, tipo, principal FROM proponentes WHERE ficha = ? ORDER BY orden").bind(ficha),
  ])).map((r) => r.results);
  const f = p[0];
  if (!f) return "";
  imps.sort((a, b) => ORDEN_IMP[a.nivel] - ORDEN_IMP[b.nivel]);
  let texto = [
    `## ${f.titulo || f.titulo_oficial} (${numero(f)}, ficha ${f.ficha})`,
    `Título oficial: ${f.titulo_oficial}`,
    `Presentado: ${dma(f.fecha_presentacion)} | Comisión: ${f.comision || "—"} | Etapa actual: ${f.etapa}`,
    `Proponentes: ${props.map((x) => x.nombre + (x.tipo === "Suplente" ? " (suplente)" : "") + (x.principal ? " [principal]" : "")).join("; ") || "—"}`,
    `Impacto: ${f.impacto || "sin analizar todavía"}${f.sectores ? ` | Sectores: ${f.sectores}` : ""}`,
    ...(imps.length ? [`Impacto por sector:\n${imps.map((i) => `- ${i.sector}: ${i.nivel} (${i.razon})`).join("\n")}`] : []),
    `Resumen: ${f.resumen || "—"}`, `Por qué: ${f.razon || "—"}`, `Notas del equipo: ${f.notas || "—"}`,
    `Historial de etapas (más reciente primero):\n${evs.map((e) => `- ${dma(e.fecha)} · ${e.etapa}: ${e.texto}`).join("\n") || "- sin historial todavía"}`,
    `Texto oficial: https://sistemas.asamblea.gob.pa/segLegis/Documents/${f.ficha}.pdf`,
  ].join("\n");
  const carpeta = (String(f.carpeta_url || "").match(/folders\/([\w-]+)/) || [])[1];
  if (carpeta && token) {
    try {
      const md = (await archivosMd(token, carpeta))[0]; // el más reciente (los nombres empiezan con la fecha)
      if (md) texto += `\n\n### Análisis completo (${md.name})\n\n` + (await leerArchivo(token, md.id)).slice(0, MAX_CARACTERES_MD);
    } catch (e) { console.log("drive", e); }
  }
  return texto;
}

// ------------------------------------------------------------------ cerebro de Kiwi

const REGLAS =
  "- Responde en español, directo y breve: primero la respuesta, después el detalle necesario.\n" +
  "- Cita el número (Proyecto N o Anteproyecto N), la etapa y las fechas cuando hables de un proyecto.\n" +
  "- En Panamá los proyectos pasan por prohijamiento, primer debate (en comisión), segundo y tercer debate (en el Pleno), " +
  "y luego sanción u objeción del Ejecutivo.\n" +
  "- Usa SOLO la información entregada. Si algo no está, dilo claramente; nunca inventes.\n" +
  "- Si un proyecto aún no tiene análisis de impacto, dilo (el agente los va analizando de a poco).\n" +
  "- Texto plano: sin Markdown, sin asteriscos ni almohadillas. Usa guiones para listas.\n" +
  "- Desde el chat no puedes cambiar datos: nunca digas que actualizaste o corregiste algo; sugiere anotarlo en la columna Notas de la matriz.";

const ESQUEMA_PLAN = {
  type: "OBJECT", required: ["fichas", "filtros"],
  properties: {
    fichas: { type: "ARRAY", items: { type: "INTEGER" }, description: `Fichas concretas que hay que leer completas (máximo ${MAX_FICHAS}).` },
    filtros: {
      type: "OBJECT", description: "Para preguntas de listado (por diputado, sector, comisión, etapa, impacto o fecha). Vacíos si no aplica.",
      properties: {
        proponente: { type: "STRING", description: "Nombre exacto de la lista de proponentes, o vacío." },
        solo_principal: { type: "BOOLEAN", description: "true si preguntan solo por los que presentó como principal." },
        sector: { type: "STRING", description: "Sector exacto de la lista, o vacío." },
        comision: { type: "STRING", description: "Comisión exacta de la lista, o vacío." },
        etapa: { type: "STRING", description: "Etapa exacta de la lista, o vacío." },
        impacto_minimo: { type: "STRING", enum: ["ninguno", "alto", "medio", "bajo"],
          description: "Impacto mínimo pedido; 'ninguno' si no filtran por impacto." },
        desde: { type: "STRING", description: "AAAA-MM-DD: solo fichas con novedad desde esa fecha (p. ej. 'esta semana'), o vacío." },
      },
    },
  },
};
const SECTORES = ["ALIMENTOS", "BANANERO", "CAMARONERO Y PESQUERO", "CEMENTERAS", "EXTRACTIVO", "FINANCIERO", "INDUSTRIAS",
  "OTROS", "PETRÓLEO", "SALUD", "SEGUROS", "TRANSPORTE", "TURISMO", "TODAS LAS EMPRESAS"];

// Paso 1: Gemini decide qué fichas leer y qué filtros aplicar. Paso 2: se arma el contexto con la base.
// Paso 3: Gemini responde como Kiwi. Devuelve {respuesta, fichas}.
async function responder(env, pregunta, historial = [], seguirEscribiendo = async () => {}) {
  const d = await datos(env);
  const previo = historial.slice(-6).filter((h) => h && h.texto)
    .map((h) => `${h.rol === "yo" ? "Usuario" : "Kiwi"}: ${String(h.texto).slice(0, 600)}`).join("\n");
  const plan = JSON.parse(await gemini(env, {
    systemInstruction: { parts: [{ text:
      "Eres el buscador del seguimiento legislativo de la Asamblea Nacional de Panamá. Recibes el índice de fichas " +
      "(ficha | número | etapa | impacto | comisión | título), las listas de proponentes, comisiones, etapas y sectores, " +
      "y una pregunta. Decide qué fichas hay que leer completas (las que la pregunta nombra o describe) y, si la pregunta " +
      "pide un listado, qué filtros aplicar. Usa los valores exactos de las listas. Hoy es " + hoyPanama() + "." }] },
    contents: [{ role: "user", parts: [{ text:
      `Índice de fichas (novedad más reciente primero):\n${d.fichas.map(lineaIndice).join("\n")}\n\n` +
      `Proponentes: ${d.personas.map((p) => p.nombre).join("; ")}\n\nComisiones: ${d.comisiones.join("; ")}\n\n` +
      `Etapas: ${d.etapas.join("; ")}\n\nSectores: ${SECTORES.join("; ")}\n\n` +
      (previo ? `Conversación previa:\n${previo}\n\n` : "") + `Pregunta: ${pregunta}` }] }],
    generationConfig: { responseMimeType: "application/json", responseSchema: ESQUEMA_PLAN },
  }));
  await seguirEscribiendo();

  const elegidas = (plan.fichas || []).filter((n) => d.porFicha.has(n)).slice(0, MAX_FICHAS);
  const lista = await listado(env, d, plan.filtros || {});
  const token = elegidas.length ? await googleToken(env).catch(() => null) : null;
  const completas = await Promise.all(elegidas.map((n) => fichaCompleta(env, n, token)));
  let contexto = "";
  if (lista) contexto += lista + "\n\n";
  if (completas.length) contexto += "Fichas relacionadas:\n\n" + completas.join("\n\n---\n\n");
  if (!contexto) {
    const resumen = d.fichas.filter((f) => f.en_seguimiento).slice(0, MAX_LISTA);
    contexto = `Fichas en seguimiento (con impacto), novedad más reciente primero:\n${resumen.map(lineaLista).join("\n") || "(ninguna todavía)"}\n\n` +
      `Total de fichas en el Seguimiento Legislativo: ${d.fichas.length}; analizadas: ${d.fichas.filter((f) => f.impacto).length}.`;
  }
  const contents = historial.slice(-8).filter((h) => h && h.texto && (h.rol === "yo" || h.rol === "agente"))
    .map((h) => ({ role: h.rol === "yo" ? "user" : "model", parts: [{ text: String(h.texto).slice(0, 2000) }] }));
  contents.push({ role: "user", parts: [{ text: `${contexto}\n\nPregunta: ${pregunta}` }] });
  while (contents.length && contents[0].role !== "user") contents.shift();
  const respuesta = await gemini(env, {
    systemInstruction: { parts: [{ text:
      "Eres Kiwi, la mascota y jefe de la oficina virtual del Agente Panamá, que hace seguimiento legislativo de la Asamblea " +
      "Nacional de Panamá para el equipo de Keyword. Hablas con calidez y en pocas líneas, como un colega; sin saludos ni " +
      `frases de entrada: la primera frase ya es la respuesta. Hoy es ${hoyPanama()}.\nReglas:\n${REGLAS}` }] },
    contents,
  });
  return { respuesta, fichas: elegidas };
}

function lineaLista(f) {
  return `- ${f.numero} (ficha ${f.ficha}) · ${f.etapa} · impacto ${f.impacto || "sin analizar"}` +
    `${f.sectores ? ` (${f.sectores})` : ""} · ${f.comision || "—"} · ${f.proponente || "—"} · última novedad ${dma(f.ultima)} · ${f.titulo.slice(0, 160)}`;
}

// Listado filtrado con la base (para "¿qué presentó X?", "¿qué hay de impacto alto en FINANCIERO?", etc.).
async function listado(env, d, filtros) {
  if (filtros.impacto_minimo === "ninguno") delete filtros.impacto_minimo; // Gemini no admite "" en un enum
  const activos = Object.entries(filtros).filter(([k, v]) => v && k !== "solo_principal");
  if (!activos.length) return "";
  let fichas = d.fichas;
  const desc = [];
  if (filtros.proponente) {
    const q = filtros.solo_principal ? " AND principal = 1" : "";
    const r = await env.DB.prepare(`SELECT ficha, principal FROM proponentes WHERE nombre = ?${q}`).bind(filtros.proponente).all();
    const suyas = new Map(r.results.map((x) => [x.ficha, x.principal]));
    fichas = fichas.filter((f) => suyas.has(f.ficha)).map((f) => ({ ...f, rol: suyas.get(f.ficha) ? "principal" : "coproponente" }));
    desc.push(`proponente ${filtros.proponente}${filtros.solo_principal ? " (solo como principal)" : ""}`);
  }
  if (filtros.sector) {
    const r = await env.DB.prepare("SELECT ficha, nivel FROM impactos WHERE sector = ?").bind(filtros.sector).all();
    const niv = new Map(r.results.map((x) => [x.ficha, x.nivel]));
    fichas = fichas.filter((f) => niv.has(f.ficha)).map((f) => ({ ...f, impacto: niv.get(f.ficha) }));
    desc.push(`sector ${filtros.sector} (impacto para ese sector)`);
  }
  if (filtros.comision) { fichas = fichas.filter((f) => f.comision === filtros.comision); desc.push(filtros.comision); }
  if (filtros.etapa) { fichas = fichas.filter((f) => f.etapa === filtros.etapa); desc.push(`etapa ${filtros.etapa}`); }
  if (filtros.impacto_minimo) {
    fichas = fichas.filter((f) => f.impacto && ORDEN_IMP[f.impacto] <= ORDEN_IMP[filtros.impacto_minimo]);
    desc.push(`impacto ${filtros.impacto_minimo} o más`);
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(filtros.desde || "")) { fichas = fichas.filter((f) => f.ultima >= filtros.desde); desc.push(`con novedad desde ${dma(filtros.desde)}`); }
  const total = fichas.length;
  const sinAnalizar = fichas.filter((f) => !f.impacto).length;
  fichas = [...fichas].sort((a, b) => (ORDEN_IMP[a.impacto] ?? 4) - (ORDEN_IMP[b.impacto] ?? 4) || b.ultima.localeCompare(a.ultima));
  return `Listado (${desc.join(", ")}): ${total} fichas${sinAnalizar ? `, ${sinAnalizar} todavía sin análisis de impacto` : ""}` +
    `${total > MAX_LISTA ? `; se muestran ${MAX_LISTA}` : ""}.\n` +
    fichas.slice(0, MAX_LISTA).map((f) => lineaLista(f) + (f.rol ? ` · como ${f.rol}` : "")).join("\n");
}

// ------------------------------------------------------------------ Google (Drive)

async function googleToken(env) {
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET,
      refresh_token: env.GOOGLE_REFRESH_TOKEN, grant_type: "refresh_token" }),
  });
  const d = await r.json();
  if (!d.access_token) throw new Error("Google: " + JSON.stringify(d));
  return d.access_token;
}

async function google(token, url) {
  const r = await fetch(url, { headers: { Authorization: "Bearer " + token } });
  if (!r.ok) throw new Error(`Google ${r.status}: ${await r.text()}`);
  return r;
}

async function archivosMd(token, carpeta) {
  const q = encodeURIComponent(`'${carpeta}' in parents and name contains '.md' and trashed = false`);
  const url = `https://www.googleapis.com/drive/v3/files?q=${q}&fields=files(id,name)&orderBy=name desc&pageSize=10`;
  return (await (await google(token, url)).json()).files || [];
}

async function leerArchivo(token, id) {
  return await (await google(token, `https://www.googleapis.com/drive/v3/files/${id}?alt=media`)).text();
}

// ------------------------------------------------------------------ Gemini

async function gemini(env, cuerpo) {
  let ultimo = "";
  for (const modelo of MODELOS) {
    for (let intento = 0; intento < 2; intento++) {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
        method: "POST", headers: { "x-goog-api-key": env.GEMINI_KEY, "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo) });
      if (r.ok) {
        const d = await r.json();
        const texto = (d.candidates?.[0]?.content?.parts || []).filter((p) => !p.thought).map((p) => p.text || "").join("").trim();
        if (texto) return texto;
        ultimo = `${modelo}: respuesta vacía`;
        break;
      }
      ultimo = `${modelo}: HTTP ${r.status}`;
      if (![429, 500, 503].includes(r.status)) break; // modelo retirado u otro error: siguiente
      await new Promise((ok) => setTimeout(ok, 3000));
    }
  }
  throw new Error("Gemini no respondió: " + ultimo);
}

// ------------------------------------------------------------------ Telegram

async function enviar(env, chat, texto) {
  for (let i = 0; i < texto.length; i += 4000) { // Telegram corta en 4.096 caracteres
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chat, text: texto.slice(i, i + 4000), disable_web_page_preview: true }),
    });
  }
}

async function accion(env, chat) {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendChatAction`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chat, action: "typing" }),
  });
}

// ------------------------------------------------------------------ oficina virtual

async function oficina(request, env, url) {
  if (!env.OFICINA_CLAVE || url.searchParams.get("k") !== env.OFICINA_CLAVE) return new Response("No autorizado", { status: 403 });
  const json = (d, status = 200) => new Response(JSON.stringify(d), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  if (url.pathname === "/oficina/datos") return json(await datosOficina(env));
  if (url.pathname === "/oficina/ficha") {
    const n = Number(url.searchParams.get("n"));
    return json(await fichaOficina(env, n));
  }
  if (url.pathname === "/oficina/kiwi" && request.method === "POST") {
    try {
      const { mensaje, historial } = await request.json();
      if (!mensaje) return json({ error: "Falta el mensaje." }, 400);
      return json(await responder(env, String(mensaje).slice(0, 1000), historial || []));
    } catch (e) {
      console.log("kiwi", e.stack || e);
      return json({ error: "No pude responder ahora; la IA de Google puede estar saturada. Prueba en un minuto." }, 502);
    }
  }
  return new Response(PAGINA_OFICINA, { headers: { "Content-Type": "text/html; charset=utf-8" } });
}

// Lo que la página necesita de una vez: fichas (compactas), novedades de los últimos 14 días, proponentes y comisiones.
async function datosOficina(env) {
  const d = await datos(env);
  const desde = new Date(Date.now() + HORA_PANAMA * 3600 * 1000 - 14 * 86400000).toISOString().slice(0, 10);
  const novedades = (await env.DB.prepare(
    "SELECT e.ficha, e.fecha, e.etapa, e.texto FROM eventos e WHERE e.fecha >= ? ORDER BY e.fecha DESC, e.id ASC").bind(desde).all()).results;
  return {
    hoy: hoyPanama(), matriz: env.MATRIZ_ID ? `https://docs.google.com/spreadsheets/d/${env.MATRIZ_ID}` : "",
    fichas: d.fichas.map((f) => ({ ficha: f.ficha, numero: f.numero, titulo: f.titulo, etapa: f.etapa, comision: f.comision,
      impacto: f.impacto || "", sectores: f.sectores || "", proponente: f.proponente, presentado: f.fecha_presentacion,
      ultima: f.ultima, seguimiento: f.en_seguimiento, carpeta: f.carpeta_url || "" })),
    novedades, personas: d.personas, comisiones: d.comisiones,
  };
}

async function fichaOficina(env, n) {
  const [p, evs, imps, props] = (await env.DB.batch([
    env.DB.prepare("SELECT * FROM proyectos WHERE ficha = ?").bind(n),
    env.DB.prepare("SELECT fecha, etapa, texto FROM eventos WHERE ficha = ? ORDER BY fecha DESC, id ASC").bind(n),
    env.DB.prepare("SELECT sector, nivel, razon FROM impactos WHERE ficha = ?").bind(n),
    env.DB.prepare("SELECT nombre, tipo, principal FROM proponentes WHERE ficha = ? ORDER BY orden").bind(n),
  ])).map((r) => r.results);
  if (!p[0]) return { error: "No encontré esa ficha." };
  imps.sort((a, b) => ORDEN_IMP[a.nivel] - ORDEN_IMP[b.nivel]);
  let disposiciones = [];
  try { disposiciones = JSON.parse(p[0].disposiciones || "[]"); } catch (e) { /* vacío */ }
  return { ...p[0], numero: numero(p[0]), disposiciones, eventos: evs, impactos: imps, proponentes: props,
    pdf: `https://sistemas.asamblea.gob.pa/segLegis/Documents/${n}.pdf` };
}

const PAGINA_OFICINA = __PAGINA_OFICINA__;
