// Kiwi, el asistente del Agente Panamá (Cloudflare Worker).
//
// - /oficina?k=<OFICINA_CLAVE> sirve la oficina virtual y su API. Kiwi responde ahí con los datos de la base D1
//   (binding DB): fichas del Seguimiento Legislativo, historial de etapas, impacto por sector y proponentes, más el
//   análisis completo (.md) de Drive de las fichas que toque la pregunta.
// - Telegram (webhook): en un chat privado responde que se pregunte en la oficina. En los GRUPOS (chat de doble vía,
//   2026-10-26) deja en chat_entrada lo que va dirigido a un agente; la Mac (cerebro/chat.py) lo contesta.
//
// Secretos (los sube bot/desplegar.py): TELEGRAM_TOKEN, WEBHOOK_SECRET, AUTORIZADOS (IDs de Telegram separados por
// coma), GEMINI_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, OFICINA_CLAVE, MATRIZ_ID.

const MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"];
// para decidir qué buscar (elegir fichas y filtros del índice) basta un modelo liviano y mucho más rápido
const MODELOS_RAPIDOS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.8-flash"];
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
    const msg = update.message || (update.my_chat_member && { chat: update.my_chat_member.chat });
    if (msg && msg.chat && msg.chat.type !== "private") {
      // anota en qué grupos está el bot (así se saca su chat id para mandarle avisos)
      if (update.my_chat_member) {
        await env.DB.prepare("INSERT OR REPLACE INTO config (clave, valor, actualizado) VALUES (?, ?, ?)")
          .bind("grupo_telegram:" + msg.chat.id, String(msg.chat.title || ""), new Date().toISOString().slice(0, 19)).run().catch(() => {});
      }
      // chat de doble vía: lo dirigido a un agente (por su nombre al comienzo, respondiendo a un mensaje del bot o
      // nombrándolo con @) queda en chat_entrada; la Mac lo contesta. Lo demás que conversa el equipo no se guarda.
      const t = String(msg.text || ""), citado = msg.reply_to_message;
      const nombre = sinTildes((t.match(/^\s*@?([\p{L}]+)/u) || [])[1] || "");
      if (t && (AGENTES_CHAT.includes(nombre) || (citado && citado.from && citado.from.is_bot) || t.includes("@"))) {
        await env.DB.prepare("INSERT OR IGNORE INTO chat_entrada (id, chat, mensaje, texto, citado_id, citado_texto, citado_bot, estado, creado) " +
          "VALUES (?, ?, ?, ?, ?, ?, ?, 'nuevo', ?)").bind(`${msg.chat.id}:${msg.message_id}`, String(msg.chat.id), msg.message_id, t.slice(0, 2000),
          citado ? citado.message_id : null, citado ? String(citado.text || citado.caption || "").slice(0, 2500) : null,
          citado && citado.from && citado.from.is_bot ? 1 : 0, new Date().toISOString().slice(0, 19)).run().catch((e) => console.log("chat", e));
      }
      return new Response("ok");
    }
    if (!msg || !msg.text) return new Response("ok");

    // En Panamá el bot de Telegram es solo de notificaciones (decisión de Andrés, 2026-10-08): a Kiwi se le pregunta
    // en la oficina. A cualquier mensaje se le contesta lo mismo, sin gastar Gemini.
    await enviar(env, msg.chat.id,
      "Hola 🥝 Este canal es solo de notificaciones: aquí llegan los anteproyectos nuevos y los avances de la Asamblea " +
      "Nacional de Panamá. Para preguntarle algo a Kiwi, entra a la oficina virtual.");
    return new Response("ok");
  },
};

// ------------------------------------------------------------------ datos (D1)

const ORDEN_IMP = { alto: 0, medio: 1, bajo: 2, ninguno: 3 };
const AGENTES_CHAT = ["kiwi", "fernando", "ines", "elena", "mateo", "sofia", "diego", "paula", "tomas"];
const memo = { t: 0, datos: null };

// Todas las fichas en forma compacta (para el índice) más listas de proponentes, comisiones y sectores.
// Se guardan 5 minutos en memoria para cuidar las lecturas de D1.
async function datos(env) {
  if (memo.datos && Date.now() - memo.t < 300000) return memo.datos;
  const [fichas, principales, personas, ultimos] = (await env.DB.batch([
    env.DB.prepare("SELECT ficha, proyecto, anteproyecto, COALESCE(titulo, titulo_oficial) AS titulo, titulo_corto, fecha_presentacion, " +
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
    f.titulo = oracion(f.titulo);
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

// Los títulos sin analizar llegan en MAYÚSCULAS desde el sistema: se pasan a oración para leerlos mejor.
const PALABRAS_PROPIAS = { panama: "Panamá", republica: "República", asamblea: "Asamblea", nacional: "Nacional", canal: "Canal",
  colon: "Colón", chiriqui: "Chiriquí", veraguas: "Veraguas", darien: "Darién", cocle: "Coclé", herrera: "Herrera", "los santos": "Los Santos" };
function oracion(t) {
  t = String(t || "");
  const letras = t.replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ]/g, "");
  const mayus = letras.replace(/[^A-ZÁÉÍÓÚÑ]/g, "").length;
  if (!letras || mayus / letras.length < 0.8) return t; // ya viene legible (análisis de Gemini); tolera erratas como "lOS"
  let s = t.toLowerCase().replace(/\s+/g, " ").trim();
  s = s.replace(/(^|[^a-zñáéíóú])(panam[aá]|rep[uú]blica|asamblea nacional|col[oó]n|chiriqu[ií]|veraguas|dari[eé]n|cocl[eé])(?![a-zñáéíóú])/g,
    (m, antes, p) => antes + p.split(" ").map((w) => PALABRAS_PROPIAS[w.normalize("NFD").replace(/[\u0300-\u036f]/g, "")] || w).join(" "));
  s = s.replace(/\b(ley|decreto|codigo|código)( \d)/g, (m, a, b) => a.charAt(0).toUpperCase() + a.slice(1) + b);
  return s.charAt(0).toUpperCase() + s.slice(1);
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
  const [p, evs, ags, imps, props] = (await env.DB.batch([
    env.DB.prepare("SELECT * FROM proyectos WHERE ficha = ?").bind(ficha),
    env.DB.prepare("SELECT fecha, etapa, texto FROM eventos WHERE ficha = ? ORDER BY fecha DESC, id ASC").bind(ficha),
    env.DB.prepare(SQL_AGENDA_FICHA).bind(ficha),
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
    `Historial de etapas y noticias de la Asamblea (más reciente primero):\n${evs.map((e) => `- ${dma(e.fecha)} · ${e.etapa}: ${e.texto}`).join("\n") || "- sin historial todavía"}`,
    `En la agenda de comisiones:\n${ags.map((a) => `- ${dma(a.fecha)} ${a.hora} · ${a.comision}: ${a.descripcion.replace(/\s+/g, " ").slice(0, 300)}`).join("\n") || "- no aparece en la agenda reciente"}`,
    `Texto oficial: https://sistemas.asamblea.gob.pa/segLegis/Documents/${f.ficha}.pdf`,
  ].join("\n") + await vidaNorma(env, f);
  const carpeta = (String(f.carpeta_url || "").match(/folders\/([\w-]+)/) || [])[1];
  if (carpeta && token) {
    try {
      const md = (await archivosMd(token, carpeta))[0]; // el más reciente (los nombres empiezan con la fecha)
      if (md) texto += `\n\n### Análisis completo (${md.name})\n\n` + (await leerArchivo(token, md.id)).slice(0, MAX_CARACTERES_MD);
    } catch (e) { console.log("drive", e); }
  }
  return texto;
}

// La vida de una ley DESPUÉS de la Asamblea: la ley publicada en la Gaceta cierra con "Proyecto 234 de 2025 aprobado
// en tercer debate…" (así se une con su ficha) y después se buscan en el cerebro los documentos que la citan
// ("Ley 561"): reglamentos y reformas en la Gaceta, resoluciones de reguladores, fallos y comunicados de la Corte.
async function vidaNorma(env, f) {
  if (f.etapa !== "Ley" || !f.proyecto || f.proyecto === "0") return "";
  const leyes = (await env.DB.prepare("SELECT d.id, d.titulo, d.fecha, d.url, f.texto, n.tipo, n.numero, n.edicion FROM fragmentos f " +
    "JOIN documentos d ON d.id = f.documento LEFT JOIN normas n ON n.archivo = d.titulo || '.pdf' " +
    "WHERE fragmentos MATCH ? AND d.fuente = 'gaceta_texto' LIMIT 6").bind(`"proyecto ${f.proyecto} de"`).all().catch(() => ({ results: [] }))).results;
  const anio = Number(String(f.fecha_presentacion || "").slice(0, 4));
  const ley = leyes.find((x) => {
    const a = Number((x.texto.match(new RegExp(`Proyecto\\s+${f.proyecto}\\s+de\\s+(\\d{4})`, "i")) || [])[1]);
    return !a || !anio || a >= anio; // la numeración de proyectos es por año: el año del proyecto no es anterior a la ficha
  });
  if (!ley) return "\n\nDespués de la Asamblea:\n- La ley publicada todavía no está en el cerebro (la Gaceta se lee completa desde octubre de 2026).";
  const numero = ley.numero || (ley.texto.match(/LEY\s+N?[°º.o\s]*(\d+)/i) || [])[1];
  let t = `\n\nDespués de la Asamblea:\n- ${dma(ley.fecha)} · Publicada en la Gaceta Oficial${ley.edicion ? " " + ley.edicion : ""} como ${ley.tipo || "Ley"} ${numero || ""} (${ley.url || ""})`;
  if (!numero) return t;
  const citan = (await env.DB.prepare("SELECT d.titulo, d.fecha, d.fuente, d.url, snippet(fragmentos, 2, '', '', '…', 24) AS trozo FROM fragmentos f " +
    "JOIN documentos d ON d.id = f.documento WHERE fragmentos MATCH ? AND d.id != ? AND d.fecha >= ? AND d.fuente != 'gaceta' ORDER BY d.fecha LIMIT 10")
    .bind(`"ley ${numero}"`, ley.id, ley.fecha || "").all().catch(() => ({ results: [] }))).results;
  t += citan.length ? "\n" + citan.map((x) => `- ${dma(x.fecha)} · ${FUENTES[x.fuente] || x.fuente}: ${x.titulo} — «${x.trozo}» ${x.url || ""}`).join("\n")
    : "\n- Todavía nada en el cerebro la cita (reglamentos, resoluciones de reguladores ni fallos de la Corte).";
  return t;
}

// Cuánto suele tardar cada paso, con el historial de etapas de todas las fichas (primera fecha en que cada ficha llegó
// a cada etapa). Medianas y rango típico (25-75 %), en días corridos, en total y por comisión. Se guarda una hora.
const PASOS = ["Preliminar", "Prohijado", "Primer Debate", "Segundo Debate", "Tercer Debate", "Enviado al Ejecutivo", "Ley"];
const memoTiempos = { t: 0, datos: null };
async function tiemposTramite(env, d, elegidas = []) {
  if (!memoTiempos.datos || Date.now() - memoTiempos.t > 3600000) {
    const filas = (await env.DB.prepare(`SELECT ficha, etapa, MIN(substr(fecha, 1, 10)) AS fecha FROM eventos WHERE etapa IN (${PASOS.map(() => "?").join(",")}) GROUP BY ficha, etapa`)
      .bind(...PASOS).all()).results;
    const porFicha = {};
    for (const x of filas) (porFicha[x.ficha] = porFicha[x.ficha] || {})[x.etapa] = x.fecha;
    const tramos = {}; // "A → B" → {todos: [días], comisiones: {comisión: [días]}, llegaron: n que llegaron a A}
    const dias = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
    for (const [ficha, e] of Object.entries(porFicha)) {
      const f = d.porFicha.get(Number(ficha));
      if (!e.Preliminar && f && f.fecha_presentacion) e.Preliminar = String(f.fecha_presentacion).slice(0, 10);
      for (let i = 0; i < PASOS.length - 1; i++) {
        const a = PASOS[i], b = PASOS[i + 1], clave = `${a} → ${b}`;
        if (!e[a]) continue;
        const tr = (tramos[clave] = tramos[clave] || { todos: [], comisiones: {}, llegaron: 0 });
        tr.llegaron++;
        if (e[b] && e[b] >= e[a]) {
          const n = dias(e[a], e[b]);
          tr.todos.push(n);
          if (f && f.comision) (tr.comisiones[f.comision] = tr.comisiones[f.comision] || []).push(n);
        }
      }
      if (e.Preliminar && e.Ley && e.Ley >= e.Preliminar) {
        const tr = (tramos["Presentado → Ley"] = tramos["Presentado → Ley"] || { todos: [], comisiones: {}, llegaron: 0 });
        tr.todos.push(dias(e.Preliminar, e.Ley));
      }
    }
    memoTiempos.datos = { tramos, porFicha };
    memoTiempos.t = Date.now();
  }
  const { tramos, porFicha } = memoTiempos.datos;
  const q = (v, p) => { const o = [...v].sort((a, b) => a - b); return o[Math.min(o.length - 1, Math.floor(p * (o.length - 1) + 0.5))]; };
  const linea = (v) => `mediana ${q(v, 0.5)} días (típico ${q(v, 0.25)}-${q(v, 0.75)}; ${v.length} casos)`;
  let t = "Tiempos de trámite (calculados con el historial de etapas del período desde 02/07/2024; días corridos desde que " +
    "el proyecto llegó a una etapa hasta que llegó a la siguiente; los que todavía no avanzan no cuentan en la mediana):";
  for (const [clave, tr] of Object.entries(tramos)) {
    if (!tr.todos.length) continue;
    t += `\n- ${clave}: ${linea(tr.todos)}` + (tr.llegaron ? `; de ${tr.llegaron} que llegaron a ${clave.split(" → ")[0]}, ${tr.todos.length} ya avanzaron.` : ".");
  }
  for (const clave of ["Prohijado → Primer Debate", "Primer Debate → Segundo Debate"]) {
    const c = Object.entries((tramos[clave] || {}).comisiones || {}).filter(([, v]) => v.length >= 3).sort((a, b) => q(a[1], 0.5) - q(b[1], 0.5));
    if (c.length) t += `\nPor comisión (${clave}):\n` + c.map(([k, v]) => `  - ${k}: ${linea(v)}`).join("\n");
  }
  const hoy = hoyPanama();
  for (const n of elegidas) {
    const f = d.porFicha.get(n), e = porFicha[n] || {};
    if (!f) continue;
    const i = PASOS.indexOf(f.etapa);
    if (i < 0 || i === PASOS.length - 1) continue;
    const desde = e[f.etapa], clave = `${f.etapa} → ${PASOS[i + 1]}`, tr = tramos[clave];
    const suya = tr && f.comision && tr.comisiones[f.comision];
    t += `\n- ${f.numero} (ficha ${f.ficha}): en ${f.etapa}${desde ? ` desde el ${dma(desde)} (${Math.round((Date.parse(hoy) - Date.parse(desde)) / 864e5)} días)` : ""}` +
      (tr && tr.todos.length ? `; ${clave} en general: ${linea(tr.todos)}` : "") + (suya && suya.length >= 3 ? `; en ${f.comision}: ${linea(suya)}` : "") + ".";
  }
  return t;
}

// Agenda de comisiones de hoy a 7 días, compacta, para que Kiwi pueda contestar "qué se ve esta semana".
async function agendaProxima(env, d) {
  const hoy = hoyPanama(), hasta = new Date(Date.parse(hoy + "T12:00:00Z") + 7 * 864e5).toISOString().slice(0, 10);
  try {
    const { results } = await env.DB.prepare("SELECT fecha, hora, comision, descripcion, fichas FROM agenda WHERE fecha BETWEEN ? AND ? ORDER BY fecha, hora")
      .bind(hoy, hasta).all();
    if (!results.length) return "";
    return "Agenda de comisiones (hoy y próximos 7 días):\n" + results.map((a) => {
      const fs = (a.fichas ? a.fichas.split(",") : []).map((n) => d.porFicha.get(Number(n))).filter(Boolean);
      return `- ${dma(a.fecha)} ${a.hora} · ${a.comision}: ${a.descripcion.replace(/\s+/g, " ").slice(0, 220)}` +
        (fs.length ? ` [fichas: ${fs.map((f) => `${f.numero} (ficha ${f.ficha}, impacto ${f.impacto || "sin analizar"})`).join("; ")}]` : "");
    }).join("\n");
  } catch (e) { return ""; }
}

// ------------------------------------------------------------------ cerebro de Kiwi

const REGLAS =
  "- Responde en español, directo y breve: primero la respuesta, después el detalle necesario.\n" +
  "- Cita el número (Proyecto N o Anteproyecto N), la etapa y las fechas cuando hables de un proyecto.\n" +
  "- En Panamá los proyectos pasan por prohijamiento, primer debate (en comisión), segundo y tercer debate (en el Pleno), " +
  "y luego sanción u objeción del Ejecutivo.\n" +
  "- Usa SOLO la información entregada. Si algo no está, dilo claramente; nunca inventes.\n" +
  "- Para cantidades usa los Totales del listado; no cuentes filas tú mismo.\n" +
  "- Al listar proyectos di de qué trata cada uno en pocas palabras (no solo su número y etapa). Si son muchos, agrupa o " +
  "muestra los más relevantes (primero los de mayor impacto o más avanzados) y di cuántos quedan.\n" +
  "- La bitácora suma las noticias oficiales de la Asamblea (etapa \"Noticia\") y la agenda de comisiones: úsalas para " +
  "contar en qué va un proyecto y cuándo se discute.\n" +
  "- Si un proyecto aún no tiene análisis de impacto, dilo (el agente los va analizando de a poco).\n" +
  "- Texto plano: sin Markdown, sin asteriscos ni almohadillas. Usa guiones para listas.\n" +
  "- Desde el chat no puedes cambiar datos: nunca digas que actualizaste o corregiste algo; sugiere anotarlo en la columna Notas de la matriz.\n" +
  "- Si citas lo que alguien dijo en una sesión o entrevista transcrita, di quién, el minuto y el enlace al video en ese " +
  "momento (el número después de | en la marca de tiempo son los segundos: https://youtu.be/<id>?t=<segundos>). Las " +
  "transcripciones automáticas pueden escribir mal los nombres.\n" +
  "- Para tiempos usa SOLO los Tiempos de trámite entregados: son medianas del período legislativo actual, no promesas; di " +
  "en cuántos casos se basa y que es una estimación. Si hay pocos casos (menos de 5), dilo.\n" +
  "- La vida de una ley después de la Asamblea (Gaceta, reglamentos, resoluciones, fallos que la citan) está en \"Después " +
  "de la Asamblea\": cuéntala en orden de fechas.";

const ESQUEMA_PLAN = {
  type: "OBJECT", required: ["fichas", "filtros", "busqueda", "tiempos"],
  properties: {
    tiempos: { type: "BOOLEAN", description: "true si preguntan cuánto tarda o suele tardar un proyecto o una etapa, " +
      "cuándo podría avanzar, aprobarse o ser ley, o qué tan rápido trabaja una comisión." },
    busqueda: { type: "STRING", description: "2 a 6 palabras clave (sin tildes) para buscar en el cerebro: transcripciones " +
      "de sesiones, Gaceta Oficial, perfiles de actores, Keylaw y Keymonitor. Nombres propios y temas; vacío si no aplica." },
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
// opciones (chat de Telegram, cerebro/chat.py): persona {nombre, funcion} = el agente al que le hablaron; citado = el
// mensaje al que responden ("¿dónde dijo esto?").
async function responder(env, pregunta, historial = [], seguirEscribiendo = async () => {}, opciones = {}) {
  const d = await datos(env);
  if (opciones.citado) pregunta = `${pregunta}\n(Responde a este mensaje del chat: «${opciones.citado}»)`;
  const previo = historial.slice(-6).filter((h) => h && h.texto)
    .map((h) => `${h.rol === "yo" ? "Usuario" : "Kiwi"}: ${String(h.texto).slice(0, 600)}`).join("\n");
  const plan = JSON.parse(await gemini(env, {
    systemInstruction: { parts: [{ text:
      "Eres el buscador del seguimiento legislativo de la Asamblea Nacional de Panamá. Recibes el índice de fichas " +
      "(ficha | número | etapa | impacto | comisión | título), las listas de proponentes, comisiones, etapas y sectores, " +
      "y una pregunta. Decide qué fichas hay que leer completas (las que la pregunta nombra o describe) y, si la pregunta " +
      "pide un listado, qué filtros aplicar. Usa los valores exactos de las listas. Además, si la pregunta trata de " +
      "personas, sesiones, normas o temas, da palabras clave para buscar en el cerebro. Hoy es " + hoyPanama() + "." }] },
    contents: [{ role: "user", parts: [{ text:
      `Índice de fichas (novedad más reciente primero):\n${d.fichas.map(lineaIndice).join("\n")}\n\n` +
      `Proponentes: ${d.personas.map((p) => p.nombre).join("; ")}\n\nComisiones: ${d.comisiones.join("; ")}\n\n` +
      `Etapas: ${d.etapas.join("; ")}\n\nSectores: ${SECTORES.join("; ")}\n\n` +
      (previo ? `Conversación previa:\n${previo}\n\n` : "") + `Pregunta: ${pregunta}` }] }],
    generationConfig: { responseMimeType: "application/json", responseSchema: ESQUEMA_PLAN },
  }, MODELOS_RAPIDOS));
  await seguirEscribiendo();

  const elegidas = (plan.fichas || []).filter((n) => d.porFicha.has(n)).slice(0, MAX_FICHAS);
  const lista = await listado(env, d, plan.filtros || {});
  const token = elegidas.length ? await googleToken(env).catch(() => null) : null;
  const completas = await Promise.all(elegidas.map((n) => fichaCompleta(env, n, token)));
  let contexto = "";
  if (lista) contexto += lista + "\n\n";
  if (completas.length) contexto += "Fichas relacionadas:\n\n" + completas.join("\n\n---\n\n");
  if (plan.tiempos) contexto += "\n\n" + await tiemposTramite(env, d, elegidas);
  const proximas = await agendaProxima(env, d);
  if (!contexto) {
    const resumen = d.fichas.filter((f) => f.en_seguimiento).slice(0, MAX_LISTA);
    contexto = `Fichas en seguimiento (con impacto), novedad más reciente primero:\n${resumen.map(lineaLista).join("\n") || "(ninguna todavía)"}\n\n` +
      `Total de fichas en el Seguimiento Legislativo: ${d.fichas.length}; analizadas: ${d.fichas.filter((f) => f.impacto).length}.`;
  }
  if (proximas) contexto += "\n\n" + proximas;
  contexto += await contextoCerebro(env, plan.busqueda || "");
  const contents = historial.slice(-8).filter((h) => h && h.texto && (h.rol === "yo" || h.rol === "agente"))
    .map((h) => ({ role: h.rol === "yo" ? "user" : "model", parts: [{ text: String(h.texto).slice(0, 2000) }] }));
  contents.push({ role: "user", parts: [{ text: `${contexto}\n\nPregunta: ${pregunta}` }] });
  while (contents.length && contents[0].role !== "user") contents.shift();
  const respuesta = await gemini(env, {
    systemInstruction: { parts: [{ text:
      "Eres Kiwi, el asistente de la oficina de Keyword en Panamá: sabes lo que pasa en la Asamblea Nacional (proyectos, " +
      "sesiones transcritas, Keylaw), en la Gaceta Oficial (normas, Keymonitor) y quiénes son los actores. Hablas con calidez y en pocas líneas, como un colega; sin saludos ni " +
      `frases de entrada: la primera frase ya es la respuesta. Hoy es ${hoyPanama()}.\nReglas:\n${REGLAS}` +
      (opciones.persona ? `\n- Esta vez contestas en el chat de Telegram del equipo como ${opciones.persona.nombre} (${opciones.persona.funcion}), ` +
        "un colega de la oficina; tu nombre ya aparece antes del mensaje: no te presentes. Sé todavía más breve." : "") }] },
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
  // los totales van contados aquí (Gemini no debe contar filas): por rol, por etapa y por impacto
  const contar = (clave) => Object.entries(fichas.reduce((c, f) => ((c[f[clave] || "sin analizar"] = (c[f[clave] || "sin analizar"] || 0) + 1), c), {}))
    .sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k}: ${n}`).join("; ");
  let totales = `Totales: ${total} fichas${sinAnalizar ? ` (${sinAnalizar} todavía sin análisis de impacto)` : ""}.\n` +
    `Por etapa: ${contar("etapa")}.\nPor impacto: ${contar("impacto")}.`;
  if (filtros.proponente) totales += `\nPor rol: ${contar("rol")}.`;
  const tope = filtros.proponente ? 200 : MAX_LISTA;
  fichas = [...fichas].sort((a, b) => (a.rol === "principal" ? 0 : 1) - (b.rol === "principal" ? 0 : 1) ||
    (ORDEN_IMP[a.impacto] ?? 4) - (ORDEN_IMP[b.impacto] ?? 4) || b.ultima.localeCompare(a.ultima));
  return `Listado (${desc.join(", ")}).\n${totales}\n` +
    `${total > tope ? `Se muestran las primeras ${tope} filas (los totales de arriba cuentan todas).\n` : ""}` +
    fichas.slice(0, tope).map((f) => lineaLista(f) + (f.rol ? ` · como ${f.rol}` : "")).join("\n");
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

async function gemini(env, cuerpo, modelos = MODELOS) {
  let ultimo = "";
  for (const modelo of modelos) {
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

// Búsqueda por SIGNIFICADO (cerebro/vectores.py): la pregunta se convierte en embedding de Gemini y Vectorize devuelve
// los trozos más parecidos en sentido (ids = rowid de fragmentos). Si algo falla, queda solo la búsqueda por palabras.
async function porSignificado(env, texto, n = 8) {
  if (!env.VECTORES) return [];
  try {
    const r = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent", {
      method: "POST", headers: { "x-goog-api-key": env.GEMINI_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ content: { parts: [{ text: String(texto).slice(0, 2000) }] }, taskType: "RETRIEVAL_QUERY", outputDimensionality: 768 }),
    });
    if (!r.ok) return [];
    const v = (await r.json()).embedding.values;
    const m = (await env.VECTORES.query(v, { topK: n })).matches.filter((x) => x.score > 0.55);
    if (!m.length) return [];
    const filas = (await env.DB.prepare(`SELECT f.rowid AS id, d.titulo, d.fecha, d.fuente, d.url, f.texto FROM fragmentos f JOIN documentos d ON d.id = f.documento WHERE f.rowid IN (${m.map(() => "?").join(",")})`)
      .bind(...m.map((x) => Number(x.id))).all()).results;
    const orden = Object.fromEntries(m.map((x, i) => [x.id, i]));
    return filas.sort((a, b) => orden[a.id] - orden[b.id]);
  } catch (e) {
    console.log("vectores", e.stack || e);
    return [];
  }
}

// Lo que el cerebro sabe de la pregunta: trozos de texto completo (sesiones, Gaceta, perfiles) y los últimos productos.
// Búsqueda MIXTA: por palabras (FTS5: lo exacto, "Ley 644") y por significado (Vectorize: el tema aunque se diga
// distinto); se intercalan los resultados de las dos y se quitan los repetidos.
async function contextoCerebro(env, busqueda) {
  const palabras = sinTildes(busqueda).replace(/[^a-z0-9ñ\s]/g, " ").split(/\s+/).filter((w) => w.length > 2).slice(0, 8);
  const [exactos, parecidos, prods] = await Promise.all([
    palabras.length ? env.DB.prepare("SELECT f.rowid AS id, d.titulo, d.fecha, d.fuente, d.url, f.texto FROM fragmentos f JOIN documentos d ON d.id = f.documento " +
      "WHERE fragmentos MATCH ? ORDER BY rank LIMIT 8").bind(palabras.map((w) => `"${w}"`).join(" OR ")).all()
      .then((r) => r.results).catch(() => []) : [],
    porSignificado(env, busqueda),
    env.DB.prepare("SELECT tipo, titulo, estado, creado FROM productos WHERE tipo IN ('keylaw', 'keymonitor') ORDER BY creado DESC LIMIT 12")
      .all().then((r) => r.results).catch(() => []),
  ]);
  const vistos = new Set(), trozos = [];
  for (let i = 0; i < Math.max(exactos.length, parecidos.length) && trozos.length < 10; i++)
    for (const x of [exactos[i], parecidos[i]]) if (x && !vistos.has(x.id)) { vistos.add(x.id); trozos.push(x); }
  let t = "";
  if (prods.length) t += "\n\nÚltimos reportes de la oficina:\n" + prods.map((p) => `- ${p.creado.slice(0, 10)} ${p.titulo} (${p.estado})`).join("\n");
  if (trozos.length) t += "\n\nDel cerebro (texto de las fuentes):\n\n" + trozos.map((x) => {
    // transcripciones: cada marca [hh:mm:ss] lleva sus segundos ([00:12:34|754]) para enlazar el video en ese minuto
    const video = (String(x.url || "").match(/(?:v=|youtu\.be\/|live\/)([\w-]{11})/) || [])[1];
    const texto = video ? x.texto.replace(/\[(\d{1,2}):(\d{2}):(\d{2})\]/g, (m, h, mi, se) => `[${h}:${mi}:${se}|${h * 3600 + mi * 60 + Number(se)}]`) : x.texto;
    return `[${FUENTES[x.fuente] || x.fuente} · ${x.titulo || ""} · ${x.fecha || ""}${video ? ` · video https://youtu.be/${video}` : x.url ? ` · ${x.url}` : ""}]\n${texto}`;
  }).join("\n\n---\n\n");
  return t;
}
const FUENTES = { youtube_asamblea: "Sesión transcrita", gaceta: "Gaceta Oficial", gaceta_norma: "Norma de la Gaceta",
  gaceta_texto: "Norma de la Gaceta", investigacion: "Investigación", investigacion_perfil: "Perfil investigado",
  seglegis: "Seguimiento Legislativo", regulador: "Ente regulador", oj_edicto: "Edicto de la Corte",
  oj_comunicado: "Comunicado de la Corte", entrevista: "Entrevista transcrita", inec: "INEC", energia: "Secretaría de Energía" };
const sinTildes = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

async function oficina(request, env, url) {
  if (!env.OFICINA_CLAVE || url.searchParams.get("k") !== env.OFICINA_CLAVE) return new Response("No autorizado", { status: 403 });
  const json = (d, status = 200) => new Response(JSON.stringify(d), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  if (url.pathname === "/oficina/datos") return json(await datosOficina(env));
  if (url.pathname === "/oficina/ficha") {
    const n = Number(url.searchParams.get("n"));
    return json(await fichaOficina(env, n));
  }
  // el cerebro (cerebro/esquema.sql): directorio de actores, ficha de cada actor, buscador y productos
  if (url.pathname === "/oficina/actores") return json(await actoresOficina(env));
  if (url.pathname === "/oficina/img") {
    // ilustraciones de la oficina (bot/imagenes.py), guardadas en D1
    const f = await env.DB.prepare("SELECT tipo, datos FROM imagenes WHERE nombre = ?").bind(url.searchParams.get("n") || "").first();
    if (!f) return new Response("", { status: 404 });
    return new Response(Uint8Array.from(atob(f.datos), (c) => c.charCodeAt(0)), { headers: { "Content-Type": f.tipo, "Cache-Control": "private, max-age=86400" } });
  }
  if (url.pathname === "/oficina/imagenes") {
    const filas = (await env.DB.prepare("SELECT nombre, info FROM imagenes WHERE nombre LIKE 'p\\_%' ESCAPE '\\'").all()).results;
    return json(Object.fromEntries(filas.map((f) => [f.nombre, parse(f.info, {})])));
  }
  if (url.pathname === "/oficina/keyperfil") return keyperfilPagina(env, url.searchParams.get("id") || "");
  if (url.pathname === "/oficina/transcripcion") {
    const [d, f] = (await env.DB.batch([
      env.DB.prepare("SELECT titulo, fecha, url FROM documentos WHERE id = ? AND fuente = 'youtube_asamblea'").bind(url.searchParams.get("id") || ""),
      env.DB.prepare("SELECT texto FROM fragmentos WHERE documento = ? ORDER BY CAST(n AS INTEGER)").bind(url.searchParams.get("id") || ""),
    ])).map((x) => x.results);
    if (!d[0]) return json({ error: "No encontré esa transcripción." }, 404);
    return json({ ...d[0], texto: f.map((x) => x.texto).join("\n") });
  }
  if (url.pathname === "/oficina/subir-gaceta" && request.method === "POST") {
    const numero = (url.searchParams.get("numero") || "").toUpperCase().replace("-", "_");
    if (!/^\d{5}(_[A-Z])?$/.test(numero)) return json({ error: "Escribe el número de la edición, p. ej. 30641 o 30641-A." }, 400);
    const datos = new Uint8Array(await request.arrayBuffer());
    if (datos.length < 1000 || String.fromCharCode(...datos.slice(0, 4)) !== "%PDF") return json({ error: "El archivo no es un PDF." }, 400);
    const id = crypto.randomUUID(), trozo = 600000, filas = [];
    for (let i = 0, n = 0; i < datos.length; i += trozo, n++) {
      let bin = ""; const parte = datos.subarray(i, i + trozo);
      for (let j = 0; j < parte.length; j += 8192) bin += String.fromCharCode(...parte.subarray(j, j + 8192));
      filas.push(env.DB.prepare("INSERT INTO subidas (id, n, datos) VALUES (?, ?, ?)").bind(id, n, btoa(bin)));
    }
    for (let i = 0; i < filas.length; i += 4) await env.DB.batch(filas.slice(i, i + 4));
    await env.DB.prepare("INSERT INTO tareas (id, agente, tipo, ref, estado, detalle, creado) VALUES (?, 'vigia', 'subida', ?, 'pendiente', ?, ?)")
      .bind(crypto.randomUUID(), id, numero, new Date().toISOString().slice(0, 19)).run();
    return json({ ok: true });
  }
  if (url.pathname === "/oficina/revisar" && request.method === "POST") {
    // revisión de ortografía con IA: corrige la forma, nunca el contenido (sirve para perfiles y reportes)
    const { textos } = await request.json();
    const claves = Object.keys(textos || {}).filter((k) => typeof textos[k] === "string" && textos[k].trim()).slice(0, 8);
    if (!claves.length) return json({ textos: {} });
    try {
      const r = await gemini(env, {
        systemInstruction: { parts: [{ text: "Eres corrector de estilo de Keyword, consultora de asuntos públicos en Panamá. Corrige SOLO ortografía, " +
          "tildes, puntuación, mayúsculas, concordancia y errores de tipeo, en español formal. No cambies el contenido, los datos, " +
          "las cifras, los nombres propios ni el orden; no agregues ni quites ideas; respeta cada salto de línea (mismo número de " +
          "líneas). Si un texto está bien, devuélvelo igual." }] },
        contents: [{ role: "user", parts: [{ text: JSON.stringify(Object.fromEntries(claves.map((k) => [k, String(textos[k]).slice(0, 12000)]))) }] }],
        generationConfig: { temperature: 0, responseMimeType: "application/json", responseSchema: { type: "object",
          properties: Object.fromEntries(claves.map((k) => [k, { type: "string" }])), required: claves } },
      }, MODELOS_RAPIDOS);
      return json({ textos: JSON.parse(r) });
    } catch (e) {
      return json({ error: "La IA de Google no respondió; prueba en un minuto." }, 502);
    }
  }
  if (url.pathname === "/oficina/foto" && request.method === "POST") {
    const d = await request.json();
    if (!/^data:image\/(jpeg|png|webp);base64,/.test(d.foto || "") || d.foto.length > 400000) return json({ error: "La foto no es válida o es muy grande." }, 400);
    await env.DB.prepare("UPDATE entidades SET datos = json_set(COALESCE(datos, '{}'), '$.foto', ?) WHERE id = ?").bind(d.foto, d.id || "").run();
    return json({ ok: true });
  }
  if (url.pathname === "/oficina/expediente" && request.method === "POST") {
    // cambios hechos a mano en la mesa del Perfilador (reemplazan esas secciones del expediente)
    const d = await request.json();
    const fila = await env.DB.prepare("SELECT contenido FROM expedientes WHERE entidad = ?").bind(d.id || "").first();
    if (!fila) return json({ error: "Esa persona todavía no tiene perfil." }, 404);
    const exp = parse(fila.contenido, {});
    const lineas = (t) => (Array.isArray(t) ? t : String(t || "").split("\n")).map(limpiarHtml).filter(Boolean);
    exp.cargo = String(d.cargo || "").trim() || exp.cargo;
    exp.estudios = lineas(d.estudios);
    exp.experiencia = lineas(d.trabajos).map((l) => { const m = l.replace(/^<b>([^<:]{1,40}):?<\/b>:?/, "$1:").match(/^([^:<]{1,40}):\s*(.+)$/); return m ? { periodo: m[1].trim(), cargo: m[2].trim() } : { periodo: "", cargo: l }; });
    exp.resumen = ""; exp.posturas = [];
    exp.datos_interes = lineas(d.datos).map((t) => ({ texto: t, fuentes: [] }));
    exp.editado = new Date().toISOString().slice(0, 19);
    await env.DB.prepare("UPDATE expedientes SET contenido = ?, actualizado = ? WHERE entidad = ?").bind(JSON.stringify(exp), exp.editado, d.id).run();
    return json({ ok: true });
  }
  if (url.pathname === "/oficina/perfiles") return json(await buscarPerfiles(env, url.searchParams.get("q") || ""));
  if (url.pathname === "/oficina/perfil-nuevo" && request.method === "POST") {
    const d = await request.json();
    const datos = Object.fromEntries(["nombre", "cargo", "institucion", "notas"].map((k) => [k, String(d[k] || "").trim().slice(0, k === "notas" ? 12000 : 200)]));
    if (!datos.nombre) return json({ error: "Falta el nombre." }, 400);
    await env.DB.prepare("INSERT INTO tareas (id, agente, tipo, ref, estado, detalle, creado) VALUES (?, 'perfilador', 'nuevo', ?, 'pendiente', ?, ?)")
      .bind(crypto.randomUUID(), datos.nombre, JSON.stringify(datos), new Date().toISOString().slice(0, 19)).run();
    return json({ ok: true });
  }
  if (url.pathname === "/oficina/actor") return json(await actorOficina(env, url.searchParams.get("id") || ""));
  if (url.pathname === "/oficina/buscar") return json(await buscarCerebro(env, url.searchParams.get("q") || ""));
  if (url.pathname === "/oficina/productos") return json(await productosOficina(env));
  if (url.pathname === "/oficina/gaceta") return json(await gacetaOficina(env));
  if (url.pathname === "/oficina/entrevistas") {
    // Diego (cerebro/entrevistas.py): entrevistas y noticieros escuchados; Paula (cerebro/monitor.py): enlaces enviados
    const [e, m] = (await env.DB.batch([
      env.DB.prepare("SELECT id, tipo, titulo, medio, url, fecha, quien, resumen, temas, importante, producto, creado FROM entrevistas ORDER BY creado DESC LIMIT 60"),
      env.DB.prepare("SELECT medio, titulo, url, creado FROM monitor_vistos WHERE enviado = 1 ORDER BY creado DESC LIMIT 80"),
    ]).catch(() => [{ results: [] }, { results: [] }])).map((r) => r.results);
    // invitados y apariciones anunciados en X (cerebro/redes.py), de ayer y hoy
    const a = (await env.DB.prepare("SELECT id, lista, cuenta, fecha, quien, cargo, medio, programa, cuando, estado, url, texto, entidad, seguir, video " +
      "FROM medios_agenda WHERE fecha >= date('now', '-5 hours', '-1 day') ORDER BY fecha DESC LIMIT 100").all().catch(() => ({ results: [] }))).results;
    return json({ entrevistas: e.map((x) => ({ ...x, temas: parse(x.temas, []) })), enviados: m, agenda: a });
  }
  if (url.pathname === "/oficina/seguir" && request.method === "POST") {
    // Diego: escuchar (o dejar de escuchar) una entrevista anunciada en X de alguien que no está en el directorio
    const { id, seguir } = await request.json();
    await env.DB.prepare("UPDATE medios_agenda SET seguir = ? WHERE id = ? AND seguir IN (0, 1)").bind(seguir ? 1 : 0, String(id)).run();
    return json({ ok: true });
  }
  if (url.pathname === "/oficina/judiciales") {
    // Órgano Judicial (cerebro/judicial.py): notas y comunicados de los últimos 45 días
    const filas = (await env.DB.prepare("SELECT id, canal, fuente, titulo, descripcion, url, fecha, es_decision, tribunal, proceso, nombre, resumen, sectores, impacto, producto, creado " +
      "FROM judiciales WHERE creado >= date('now', '-45 days') ORDER BY fecha DESC, creado DESC LIMIT 300").all().catch(() => ({ results: [] }))).results;
    return json(filas.map((f) => ({ ...f, sectores: parse(f.sectores, []) })));
  }
  if (url.pathname === "/oficina/cifras") {
    // Tomás (cerebro/cifras.py): publicaciones económicas del INEC y su Keyeconomics
    const filas = (await env.DB.prepare("SELECT id, indicador, nombre, titulo, url, pagina, publicado, periodo, dato, cifras, producto, estado " +
      "FROM cifras ORDER BY publicado DESC LIMIT 60").all().catch(() => ({ results: [] }))).results;
    return json(filas.map((f) => ({ ...f, cifras: parse(f.cifras, []) })));
  }
  if (url.pathname === "/oficina/regulatorias") {
    // Entes Reguladores (cerebro/reguladores.py): lo analizado de los últimos 45 días
    const filas = (await env.DB.prepare("SELECT id, fuente, ente, tipo, titulo, nombre, descripcion, url, fecha, resumen, sectores, impacto, plazo, producto, creado " +
      "FROM regulatorias WHERE impacto != 'base' AND creado >= date('now', '-45 days') ORDER BY creado DESC, fecha DESC LIMIT 300").all().catch(() => ({ results: [] }))).results;
    return json(filas.map((f) => ({ ...f, sectores: parse(f.sectores, []) })));
  }
  if (url.pathname === "/oficina/normas") return json(await normasOficina(env));
  if (url.pathname === "/oficina/sesiones") return json(await sesionesOficina(env));
  // decisiones humanas: ¿Keylaw de esta sesión? ¿edición de la Gaceta ya revisada?
  if (url.pathname === "/oficina/decision" && request.method === "POST") {
    const { ref, decision } = await request.json();
    if (!/^(agenda:\d+|gaceta:[0-9a-f]+)$/.test(String(ref)) || !["", "keylaw", "guardar", "revisada"].includes(decision)) return json({ error: "Decisión no válida." }, 400);
    if (decision) await env.DB.prepare("INSERT OR REPLACE INTO decisiones (ref, decision, creado) VALUES (?, ?, ?)").bind(ref, decision, new Date().toISOString().slice(0, 19)).run();
    else await env.DB.prepare("DELETE FROM decisiones WHERE ref = ?").bind(ref).run();
    return json({ ok: true });
  }
  // la persona revisa el borrador: lo corrige, lo marca revisado o enviado
  if (url.pathname === "/oficina/producto" && request.method === "POST") {
    const { id, estado, contenido } = await request.json();
    if (estado && !["borrador", "revisado", "enviado", "archivado"].includes(estado)) return json({ error: "Estado no válido." }, 400);
    if (contenido != null) {
      // aprendizaje nivel 2: la versión del agente queda en `original` y cada corrección del equipo en `correcciones`;
      // los siguientes reportes del mismo tipo se escriben viéndolas (cerebro.aprendido)
      // apagado hasta el lanzamiento (Andrés, 2026-10-26): cerebro/aprendizaje.py encender
      const p = await env.DB.prepare("SELECT tipo, agente, contenido, original FROM productos WHERE id = ?").bind(String(id)).first();
      const nuevo = String(contenido).slice(0, 20000);
      if (p && (await aprendizajeActivo(env)) && nuevo.trim() !== String(p.contenido || "").trim()) {
        const original = p.original || p.contenido || "";
        await env.DB.batch([
          env.DB.prepare("UPDATE productos SET original = ? WHERE id = ? AND original IS NULL").bind(original, String(id)),
          env.DB.prepare("INSERT OR REPLACE INTO correcciones (producto, tipo, agente, original, corregido, actualizado) VALUES (?, ?, ?, ?, ?, ?)")
            .bind(String(id), p.tipo, p.agente, original, nuevo, new Date().toISOString().slice(0, 19)),
        ]);
      }
    }
    await env.DB.prepare("UPDATE productos SET estado = COALESCE(?, estado), contenido = COALESCE(?, contenido), actualizado = ? WHERE id = ?")
      .bind(estado || null, contenido == null ? null : String(contenido).slice(0, 20000), new Date().toISOString().slice(0, 19), String(id)).run();
    return json({ ok: true });
  }
  // la mesa de tareas: lo que alguien pide en la oficina y la Mac de la oficina hace (cerebro/mesa.py)
  if (url.pathname === "/oficina/tareas") return json(await tareasOficina(env));
  if (url.pathname === "/oficina/tarea" && request.method === "POST") {
    const { agente, tipo, ref, detalle } = await request.json();
    if (!TAREAS_PERMITIDAS[agente] || !TAREAS_PERMITIDAS[agente].includes(tipo)) return json({ error: "Esa tarea no existe." }, 400);
    const id = crypto.randomUUID();
    await env.DB.prepare("INSERT INTO tareas (id, agente, tipo, ref, estado, detalle, creado) VALUES (?, ?, ?, ?, 'pendiente', ?, ?)")
      .bind(id, agente, tipo, String(ref || "").slice(0, 300), String(detalle || "").slice(0, 300), new Date().toISOString().slice(0, 19)).run();
    return json({ id });
  }
  if (url.pathname === "/oficina/kiwi" && request.method === "POST") {
    try {
      const { mensaje, historial, persona, citado } = await request.json();
      if (!mensaje) return json({ error: "Falta el mensaje." }, 400);
      return json(await responder(env, String(mensaje).slice(0, 1000), historial || [], undefined,
        { persona, citado: String(citado || "").slice(0, 2500) }));
    } catch (e) {
      console.log("kiwi", e.stack || e);
      return json({ error: "No pude responder ahora; la IA de Google puede estar saturada. Prueba en un minuto." }, 502);
    }
  }
  if (url.pathname === "/oficina/grafo") {
    const { nodos, lineas } = await mapaCerebro(env);
    const grado = {};
    for (const l of lineas) { grado[l.a] = (grado[l.a] || 0) + 1; grado[l.b] = (grado[l.b] || 0) + 1; }
    return json({ nodos: nodos.map((n) => ({ id: n.id, tipo: n.tipo, grado: grado[n.id] || 0 })), lineas: lineas.map((l) => ({ a: l.a, b: l.b })) });
  }
  if (url.pathname === "/oficina/mapa") {
    const { nodos, lineas } = await mapaCerebro(env);
    const datos = { nodos, lineas, relacion: RELACION_MAPA, fecha: new Date(Date.now() + HORA_PANAMA * 3600000).toISOString().slice(0, 16).replace("T", " ") };
    return new Response(PAGINA_MAPA.replace("__DATOS__", () => JSON.stringify(datos).replace(/</g, "\\u003c")),
      { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
  }
  if (url.pathname === "/oficina/aprendizaje") {  // pestaña "Aprendizaje" de la ventana del cerebro
    const datos = await aprendizajeDatos(env);
    return new Response(PAGINA_APRENDIZAJE.replace("__DATOS__", () => JSON.stringify(datos).replace(/</g, "\\u003c")),
      { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
  }
  if (url.pathname === "/oficina/previa" && PAGINA_PREVIA) return new Response(PAGINA_PREVIA, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  return new Response(PAGINA_OFICINA, { headers: { "Content-Type": "text/html; charset=utf-8" } });
}

// Lo que la página necesita de una vez: fichas (compactas), novedades de los últimos 14 días, proponentes y comisiones.
async function datosOficina(env) {
  const d = await datos(env);
  const desde = new Date(Date.now() + HORA_PANAMA * 3600 * 1000 - 14 * 86400000).toISOString().slice(0, 10);
  const [novedades, props, act, agenda] = (await env.DB.batch([
    env.DB.prepare("SELECT ficha, fecha, etapa, texto, fuente, url FROM eventos WHERE fecha >= ? ORDER BY fecha DESC, id ASC").bind(desde),
    env.DB.prepare("SELECT ficha, nombre, principal FROM proponentes WHERE tipo IN ('Diputado', 'Suplente')"),
    // cuándo trabajó el equipo por última vez (UTC): la oficina pone a teclear a quien trabajó hace poco
    env.DB.prepare("SELECT (SELECT MAX(actualizado) FROM proyectos) AS corrida, (SELECT MAX(actualizado) FROM impactos) AS analisis"),
    // agenda de comisiones (la lee la Cronista, prensa.py): de dos semanas atrás en adelante
    env.DB.prepare("SELECT id, fecha, hora, comision, lugar, organizador, descripcion, fichas FROM agenda WHERE fecha >= ? ORDER BY fecha, hora").bind(desde),
  ])).map((r) => r.results);
  // proponentes como {nombre: [[ficha, principal], ...]} (más liviano que una fila por objeto)
  const porPersona = {};
  for (const x of props) (porPersona[x.nombre] = porPersona[x.nombre] || []).push([x.ficha, x.principal]);
  return {
    hoy: hoyPanama(), matriz: env.MATRIZ_ID ? `https://docs.google.com/spreadsheets/d/${env.MATRIZ_ID}` : "",
    fichas: d.fichas.map((f) => ({ ficha: f.ficha, numero: f.numero, titulo: f.titulo, corto: f.titulo_corto || "", etapa: f.etapa, comision: f.comision,
      impacto: f.impacto || "", sectores: f.sectores || "", proponente: f.proponente, presentado: f.fecha_presentacion,
      ultima: f.ultima, seguimiento: f.en_seguimiento, carpeta: f.carpeta_url || "" })),
    novedades, personas: d.personas, porPersona, comisiones: d.comisiones,
    ahora: new Date().toISOString().slice(0, 19), actividad: act[0] || {},
    agenda: agenda.map((a) => ({ ...a, fichas: a.fichas ? a.fichas.split(",").map(Number) : [] })),
  };
}

const SQL_AGENDA_FICHA = "SELECT a.id, a.fecha, a.hora, a.comision, a.lugar, a.descripcion FROM agenda a " +
  "JOIN agenda_fichas x ON x.agenda_id = a.id WHERE x.ficha = ? ORDER BY a.fecha DESC, a.hora DESC LIMIT 12";

async function fichaOficina(env, n) {
  const [p, evs, ags, imps, props] = (await env.DB.batch([
    env.DB.prepare("SELECT * FROM proyectos WHERE ficha = ?").bind(n),
    env.DB.prepare("SELECT fecha, etapa, texto, url FROM eventos WHERE ficha = ? ORDER BY fecha DESC, id ASC").bind(n),
    env.DB.prepare(SQL_AGENDA_FICHA).bind(n),
    env.DB.prepare("SELECT sector, nivel, razon FROM impactos WHERE ficha = ?").bind(n),
    env.DB.prepare("SELECT nombre, tipo, principal FROM proponentes WHERE ficha = ? ORDER BY orden").bind(n),
  ])).map((r) => r.results);
  if (!p[0]) return { error: "No encontré esa ficha." };
  imps.sort((a, b) => ORDEN_IMP[a.nivel] - ORDEN_IMP[b.nivel]);
  let disposiciones = [];
  try { disposiciones = JSON.parse(p[0].disposiciones || "[]"); } catch (e) { /* vacío */ }
  return { ...p[0], numero: numero(p[0]), disposiciones, eventos: evs, agenda: ags, impactos: imps, proponentes: props,
    pdf: `https://sistemas.asamblea.gob.pa/segLegis/Documents/${n}.pdf` };
}

// ------------------------------------------------------------------ el cerebro

const parse = (t, porDefecto) => { try { return JSON.parse(t || ""); } catch (e) { return porDefecto; } };

// Directorio: personas, instituciones, comisiones y partidos, con lo justo para la lista y los filtros.
async function actoresOficina(env) {
  const [ents, cuentas, perfiles] = (await env.DB.batch([
    env.DB.prepare("SELECT id, tipo, subtipo, nombre, cargo, json_extract(datos, '$.partido') AS partido, " +
      "json_extract(datos, '$.comisiones') AS comisiones, json_extract(datos, '$.foto') AS foto FROM entidades ORDER BY nombre"),
    env.DB.prepare("SELECT entidad, COUNT(*) AS n FROM declaraciones GROUP BY entidad"),
    env.DB.prepare("SELECT entidad, actualizado AS creado FROM expedientes"),
  ])).map((r) => r.results);
  const decl = Object.fromEntries(cuentas.map((c) => [c.entidad, c.n]));
  const kp = Object.fromEntries(perfiles.map((p) => [p.entidad, { fecha: p.creado }]));
  return ents.map((e) => ({ ...e, comisiones: parse(e.comisiones, []), declaraciones: decl[e.id] || 0, keyperfil: kp[e.id] || null }));
}

// Buscador del Perfilador: por nombre, cargo, institución, comisión, partido o grupo ("diputados", "gabinete"),
// en cualquier combinación. Cada palabra tiene que aparecer (sin tildes, por el comienzo de la palabra; femenino y
// plural cuentan igual). Si la búsqueda nombra una institución o comisión, sus integrantes salen primero y se dice
// qué papel tiene cada uno.
const SIN_PESO = new Set(["de", "del", "la", "las", "el", "los", "y", "en", "para", "por", "a", "al", "con", "e"]);
const SINONIMOS = { congreso: "asamblea", parlamento: "asamblea", legislador: "diputado", legisladora: "diputado",
  diputada: "diputado", diputados: "diputado", diputadas: "diputado", ministra: "ministro", viceministra: "viceministro",
  ministerio: "minist", canciller: "relaciones exteriores", cancilleria: "relaciones exteriores", mef: "economia finanzas",
  presidenta: "presidente", gabinete: "gabinete" };
const GRUPO = { diputado: "diputado asamblea nacional", suplente: "diputado suplente asamblea nacional",
  ministro: "ministro gabinete ejecutivo", viceministro: "viceministro gabinete ejecutivo", presidente: "presidente republica gabinete ejecutivo",
  autoridad: "autoridad", lider_gremial: "gremio gremial empresarial" };
const ROL = { integra: "Integra", preside: "Preside", dirige: "Dirige", pertenece_a: "", junta_directiva: "Junta directiva de" };
function plano(t) { return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function raiz(w) { return w.length > 4 ? w.replace(/(as|os|es|a|o|s)$/, "") : w; }
async function buscarPerfiles(env, q) {
  const palabras = plano(q).split(" ").filter((w) => w && !SIN_PESO.has(w))
    .flatMap((w) => plano(SINONIMOS[w] || w).split(" ")).map(raiz);
  if (!palabras.length) return { resultados: [] };
  const [ents, rels, perfiles] = (await env.DB.batch([
    env.DB.prepare("SELECT id, nombre, cargo, subtipo, json_extract(datos, '$.partido') AS partido, json_extract(datos, '$.foto') AS foto, " +
      "json_extract(datos, '$.institucion') AS institucion FROM entidades WHERE tipo = 'persona'"),
    env.DB.prepare("SELECT r.origen, r.tipo, d.nombre, d.tipo AS clase FROM relaciones r JOIN entidades d ON d.id = r.destino " +
      "WHERE d.tipo != 'persona'"),
    env.DB.prepare("SELECT entidad, actualizado AS creado FROM expedientes"),
  ])).map((r) => r.results);
  const porPersona = {};
  for (const r of rels) (porPersona[r.origen] = porPersona[r.origen] || []).push(r);
  const kp = Object.fromEntries(perfiles.map((p) => [p.entidad, { fecha: p.creado }]));
  const calza = (texto) => { const ws = plano(texto).split(" ").map(raiz); return (w) => ws.some((x) => (w.length >= 5 ? x.includes(w) : x.startsWith(w))); };
  const resultados = [];
  for (const e of ents) {
    const enNombre = calza(e.nombre), enCargo = calza([e.cargo, e.institucion, GRUPO[e.subtipo], e.partido].join(" "));
    const relaciones = porPersona[e.id] || [];
    const enRel = relaciones.map((r) => ({ r, f: calza(r.nombre + " " + (r.clase === "partido" ? "partido" : "")) }));
    if (!palabras.every((w) => enNombre(w) || enCargo(w) || enRel.some((x) => x.f(w)))) continue;
    // el papel que explica el resultado: la relación que calza con todo lo que no está en el nombre
    const resto = palabras.filter((w) => !enNombre(w));
    let calzan = enRel.filter((x) => resto.length && resto.every((w) => x.f(w)));
    const entera = calzan.length > 0;
    if (!entera) calzan = enRel.filter((x) => palabras.some((w) => x.f(w)));
    calzan.sort((x, y) => (y.r.tipo === "preside" || y.r.tipo === "dirige") - (x.r.tipo === "preside" || x.r.tipo === "dirige"));
    const roles = calzan.map((x) => ((ROL[x.r.tipo] ?? "") + " " + x.r.nombre).trim());
    const puntos = palabras.filter(enNombre).length * 3 + palabras.filter(enCargo).length * 2 + (entera ? 4 : 0) +
      (entera && calzan.some((x) => x.r.tipo === "preside" || x.r.tipo === "dirige") ? 3 : 0) + (kp[e.id] ? 1 : 0);
    resultados.push({ id: e.id, nombre: e.nombre, cargo: e.cargo, partido: e.partido, foto: e.foto, roles, keyperfil: kp[e.id] || null, puntos });
  }
  resultados.sort((a, b) => b.puntos - a.puntos || a.nombre.localeCompare(b.nombre));
  return { total: resultados.length, resultados: resultados.slice(0, 80) };
}

// El Keyperfil con el modelo de Keyword (la tira vertical de sus Keyperfil reales), armado al vuelo con el expediente:
// no se guardan PDF (Andrés, 2026-10-25). "Descargar PDF" imprime la página a PDF desde el navegador.
const KP_ACTIVOS = __KP_ACTIVOS__;
function rico(t) { return escapar(t).replace(/&lt;(\/?)(b|strong|i|em|u)&gt;/g, "<$1$2>"); }
function limpiarHtml(t) { return String(t || "").replace(/<(?!\/?(b|strong|i|em|u)>)[^>]*>/gi, "").replace(/&nbsp;/g, " ").trim(); }
function escapar(t) { return String(t || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]); }
function ordenTrabajo(x, cargo) {
  const anos = (x.periodo || "").match(/\d{4}/g) || [];
  const hasta = !anos.length || /presente|actual/i.test(x.periodo || "") ? 9999 : +anos[anos.length - 1];
  return [x.cargo === cargo ? 1 : 0, hasta, anos.length ? +anos[0] : 0];
}
async function keyperfilPagina(env, id) {
  const [e, x] = (await env.DB.batch([
    env.DB.prepare("SELECT nombre, cargo, json_extract(datos, '$.foto') AS foto FROM entidades WHERE id = ?").bind(id),
    env.DB.prepare("SELECT contenido FROM expedientes WHERE entidad = ?").bind(id),
  ])).map((r) => r.results);
  if (!e[0] || !x[0]) return new Response("Todavía no hay Keyperfil de esa persona.", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  const exp = parse(x[0].contenido, {}), nombre = exp.nombre || e[0].nombre, cargo = exp.cargo || e[0].cargo || "";
  const icono = (n) => KP_ACTIVOS[n] ? `<img class="icono" alt="" src="${KP_ACTIVOS[n]}">` : "";
  const trabajos = (exp.experiencia || []).slice().sort((a, b) => {
    const p = ordenTrabajo(a, exp.cargo), q = ordenTrabajo(b, exp.cargo);
    return q[0] - p[0] || q[1] - p[1] || q[2] - p[2];
  });
  const datos = [exp.resumen, ...(exp.datos_interes || []).map((d) => d.texto), ...(exp.posturas || []).map((d) => `${d.tema}: ${d.postura}`)]
    .filter(Boolean).map((t) => String(t).replace(/\s*\[NV\]/g, ""));
  const iniciales = nombre.split(" ").filter((w) => /^[A-ZÁÉÍÓÚÑ]/.test(w)).slice(0, 2).map((w) => w[0]).join("");
  const partes = [];
  if ((exp.estudios || []).length) partes.push(`<section class="tarjeta">${icono("birrete")}<h2>Principales estudios:</h2>` +
    exp.estudios.map((t) => `<div class="hito">${rico(t)}</div>`).join("") + "</section>");
  if (trabajos.length) partes.push(`<section class="tarjeta">${icono("foco")}<h2>Principales trabajos:</h2>` +
    trabajos.map((t) => `<div class="hito">${t.periodo ? `<b>${escapar(t.periodo)}:</b> ` : ""}${rico(t.cargo)}</div>`).join("") + "</section>");
  if (datos.length) partes.push(`<section class="tarjeta">${icono("info")}<h2>Datos de Interés</h2><ul>` +
    datos.map((t) => `<li>${rico(t)}</li>`).join("") + "</ul></section>");
  const archivo = `${new Date(Date.now() + HORA_PANAMA * 3600000).toISOString().slice(2, 10).replace(/-/g, "")} Keyperfil ${nombre}`;
  const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapar(archivo)}</title>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@600;700&family=Montserrat:wght@300&family=Open+Sans:wght@400;700&display=swap" rel="stylesheet">
<style>
:root { --titulo: #6552e6; --texto: #3c3d4a; }
* { box-sizing: border-box; }
html { background: #d9dcef; scrollbar-gutter: stable; }
body { margin: 0; padding: 24px 0; }
body.vista { padding: 0; background: #e7eaff; overflow-x: hidden; }
body.vista #hoja { margin: 0; transform-origin: top left; }
#hoja { margin: 0 auto; width: 560px; font-family: "Open Sans", Arial, sans-serif; color: var(--texto); font-size: 11.5px; line-height: 1.5;
  background: linear-gradient(180deg, #e7eaff 0%, #eef0ff 45%, #f3f3ff 100%); padding: 26px 24px 30px; -webkit-print-color-adjust: exact; print-color-adjust: exact; transform-origin: top center; }
.antetitulo { font-family: Montserrat, sans-serif; font-weight: 300; font-size: 12px; letter-spacing: .32em; color: #4b4f8a; margin: 0 0 14px 6px; }
.persona { display: flex; align-items: center; gap: 22px; margin: 0 6px 22px; }
.foto { width: 96px; height: 96px; border-radius: 50%; overflow: hidden; flex: none; background: #d4d8f5; border: 3px solid #fff;
  box-shadow: 0 6px 16px rgba(60, 60, 120, .18); display: flex; align-items: center; justify-content: center; font: 700 30px Figtree, sans-serif; color: var(--titulo); }
.foto img { width: 100%; height: 100%; object-fit: cover; object-position: center 18%; }
.nombre { flex: 1; background: #fff; border-radius: 10px; box-shadow: 0 6px 18px rgba(60, 60, 120, .08); text-align: center; padding: 12px 14px 0; }
.nombre h1 { font: 700 16.5px/1.25 Figtree, sans-serif; color: #15162a; margin: 0 0 9px; }
.nombre .cargo { border-top: 1px solid #e6e6f2; padding: 7px 0 9px; font-size: 11.5px; color: #6d6f86; }
.tarjeta { position: relative; border-radius: 16px; padding: 26px 34px 22px; margin-bottom: 20px; break-inside: avoid;
  background: linear-gradient(180deg, rgba(255, 255, 255, .92), rgba(244, 245, 255, .92)); box-shadow: 0 10px 28px rgba(70, 70, 140, .10); }
.tarjeta h2 { font: 700 20px/1.2 Figtree, sans-serif; color: var(--titulo); margin: 4px 0 20px; }
.tarjeta .icono { position: absolute; top: 14px; right: 26px; width: 74px; }
.hito { position: relative; padding-left: 18px; margin: 0 0 13px; text-align: justify; }
.hito::before { content: ""; position: absolute; left: 0; top: 2px; bottom: 2px; width: 4px; background: linear-gradient(#9a6af6, #7f9cf8); }
.hito b { color: #111; }
ul { list-style: none; padding: 0; margin: 0; }
li { position: relative; padding-left: 22px; margin: 0 0 13px; text-align: justify; }
li::before { content: ""; position: absolute; left: 2px; top: 6px; width: 7px; height: 7px; border-radius: 50%; background: #7a68ee; }
.logo { display: block; margin: 26px auto 0; width: 112px; height: auto; }
.logo path, .logo rect, .logo circle, .logo polygon { fill: #2e3566; }
.descargar { position: fixed; top: 16px; right: 16px; font: 600 14px Figtree, sans-serif; border: 0; border-radius: 99px; padding: 10px 18px;
  background: #18191f; color: #fff; cursor: pointer; box-shadow: 0 6px 18px rgba(0, 0, 0, .2); }
.vista .descargar { display: none; }
/* al pasar a PDF: colores lisos y sin sombras (el conversor dibuja mal los degradados y las sombras) */
#hoja.captura { background: #eceefe; }
#hoja.captura .tarjeta { background: #f9f9ff; box-shadow: none; border: 1px solid #e3e5fa; }
#hoja.captura .nombre, #hoja.captura .foto { box-shadow: none; }
#hoja.captura .nombre { border: 1px solid #e3e5fa; }
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script></head><body>
<button class="descargar" type="button" onclick="descargar()">Descargar PDF</button>
<div id="hoja">
<div class="antetitulo">PERFIL</div>
<div class="persona"><div class="foto">${e[0].foto ? `<img alt="" crossorigin="anonymous" src="${escapar(e[0].foto)}">` : escapar(iniciales)}</div>
  <div class="nombre"><h1>${escapar(nombre)}</h1><div class="cargo">${escapar(cargo)}</div></div></div>
${partes.join("\n")}
${KP_ACTIVOS.logo ? `<img class="logo" alt="Keyword" src="${KP_ACTIVOS.logo}">` : ""}
</div>
<script>
// en pantalla, la hoja se agranda para leerla bien; en la vista de la mesa, ocupa el ancho del recuadro
var hoja = document.getElementById("hoja"), vista = /[?&]vista=1/.test(location.search);
if (vista) document.body.classList.add("vista");
var zoom = 0;
function ajustar() {
  var ancho = document.documentElement.clientWidth;
  var z = vista ? ancho / 560 : Math.max(1, Math.min(1.6, (ancho - 60) / 560));
  if (Math.abs(z - zoom) < 0.01) return;  // sin esto, la barra de desplazamiento hacía parpadear la vista
  zoom = z; hoja.style.transform = "scale(" + z + ")";
  document.body.style.height = (hoja.offsetHeight * z + (vista ? 0 : 48)) + "px";
}
addEventListener("resize", ajustar); addEventListener("load", ajustar); ajustar();
// PDF de una sola página del alto del contenido, como el modelo (se baja directo, sin imprimir)
function descargar() {
  var b = document.querySelector(".descargar"); b.disabled = true; b.textContent = "Preparando…";
  var t = hoja.style.transform; hoja.style.transform = "none"; hoja.classList.add("captura");
  html2pdf().set({ margin: 0, filename: ${JSON.stringify(archivo + ".pdf")}, image: { type: "jpeg", quality: 0.96 },
    html2canvas: { scale: 3, useCORS: true, backgroundColor: "#eceefe" }, pagebreak: { mode: [] },
    jsPDF: { unit: "px", format: [560, hoja.scrollHeight + 12], orientation: "portrait", hotfixes: ["px_scaling"] } })
    .from(hoja).save().then(function () { hoja.classList.remove("captura"); hoja.style.transform = t; b.disabled = false; b.textContent = "Descargar PDF"; });
}
</script></body></html>`;
  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
}

// Ficha del actor: lo del directorio, sus relaciones, su expediente (Perfilador), lo que ha dicho y dónde aparece.
async function actorOficina(env, id) {
  const [e, rel, inv, exp, decl, menc, prods] = (await env.DB.batch([
    env.DB.prepare("SELECT * FROM entidades WHERE id = ?").bind(id),
    env.DB.prepare("SELECT r.tipo, r.detalle, r.destino AS id, d.nombre, d.tipo AS clase FROM relaciones r " +
      "JOIN entidades d ON d.id = r.destino WHERE r.origen = ?").bind(id),
    env.DB.prepare("SELECT r.tipo, r.detalle, r.origen AS id, o.nombre, o.tipo AS clase, o.cargo FROM relaciones r " +
      "JOIN entidades o ON o.id = r.origen WHERE r.destino = ? ORDER BY r.tipo DESC, o.nombre").bind(id),
    env.DB.prepare("SELECT contenido, actualizado FROM expedientes WHERE entidad = ?").bind(id),
    env.DB.prepare("SELECT d.fecha, d.tema, d.cita, d.postura, o.titulo, o.url, o.fuente FROM declaraciones d " +
      "JOIN documentos o ON o.id = d.documento WHERE d.entidad = ? ORDER BY d.fecha DESC LIMIT 40").bind(id),
    env.DB.prepare("SELECT o.titulo, o.fecha, o.fuente, o.url, m.cita FROM menciones m JOIN documentos o ON o.id = m.documento " +
      "WHERE m.entidad = ? ORDER BY o.fecha DESC LIMIT 20").bind(id),
    env.DB.prepare("SELECT id, tipo, titulo, estado, creado FROM productos WHERE entidad = ? ORDER BY creado DESC LIMIT 20").bind(id),
  ])).map((r) => r.results);
  if (!e[0]) return { error: "No encontré a ese actor." };
  const datos = parse(e[0].datos, {});
  let proyectos = [];
  if (datos.nombre_en_proyectos) {
    proyectos = (await env.DB.prepare("SELECT p.ficha, p.proyecto, p.anteproyecto, COALESCE(p.titulo_corto, p.titulo, p.titulo_oficial) AS titulo, " +
      "p.etapa, p.impacto, p.fecha_presentacion, x.principal FROM proponentes x JOIN proyectos p ON p.ficha = x.ficha " +
      "WHERE x.nombre = ? ORDER BY p.fecha_presentacion DESC").bind(datos.nombre_en_proyectos).all()).results
      .map((p) => ({ ...p, titulo: oracion(p.titulo) }));
  }
  return { ...e[0], datos, relaciones: rel, vinculados: inv, expediente: exp[0] ? { ...parse(exp[0].contenido, {}),
    actualizado: exp[0].actualizado } : null, declaraciones: decl, menciones: menc, productos: prods, proyectos };
}

// Búsqueda de texto completo en todo lo que entró al cerebro (sin tildes; palabras sueltas o "frase exacta").
async function buscarCerebro(env, q) {
  const limpia = q.replace(/[^\p{L}\p{N}\s"*]/gu, " ").trim();
  if (limpia.length < 3) return [];
  return (await env.DB.prepare("SELECT f.documento, d.titulo, d.fecha, d.fuente, d.url, " +
    "snippet(fragmentos, 2, '«', '»', '…', 28) AS trozo FROM fragmentos f JOIN documentos d ON d.id = f.documento " +
    "WHERE fragmentos MATCH ? ORDER BY rank LIMIT 30").bind(limpia).all()).results;
}

async function aprendizajeActivo(env) {
  const f = await env.DB.prepare("SELECT valor FROM config WHERE clave = 'aprendizaje'").first().catch(() => null);
  return !!(f && parse(f.valor, {}).activo);
}

// Cómo avanza el aprendizaje de toda la oficina, por semana (últimas 8): reacciones 👍/👎 del equipo a cada agente,
// cuánto corrige el equipo cada reporte, cuánto tiene que corregir Kiwi al revisarlos y cuánto coincide Inés con las
// normas que el equipo elige para Keymonitor. Se guarda 5 minutos.
const memoAprendizaje = { t: 0, datos: null };
async function aprendizajeDatos(env) {
  if (memoAprendizaje.datos && Date.now() - memoAprendizaje.t < 300000) return memoAprendizaje.datos;
  const lunes = (iso) => { const d = new Date(String(iso).slice(0, 10) + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7)); return d.toISOString().slice(0, 10); };
  const semanas = [];
  for (let i = 7; i >= 0; i--) semanas.push(lunes(new Date(Date.now() - i * 7 * 864e5).toISOString()));
  const desde = semanas[0];
  const leer = (sql, ...b) => env.DB.prepare(sql).bind(...b).all().then((r) => r.results).catch(() => []);
  const [estado, porAgente, reacciones, enviados, correcciones, revisados, normas] = await Promise.all([
    env.DB.prepare("SELECT valor FROM config WHERE clave = 'aprendizaje'").first().then((f) => parse(f && f.valor, {})).catch(() => ({})),
    leer("SELECT substr(clave, 13) AS agente, valor FROM config WHERE clave LIKE 'aprendizaje:%'"),
    leer("SELECT agente, valor, creado FROM reacciones WHERE creado >= ?", desde),
    leer("SELECT agente, creado FROM chat_mensajes WHERE creado >= ? AND agente IS NOT NULL", desde),
    leer("SELECT tipo, original, corregido, actualizado FROM correcciones WHERE actualizado >= ? LIMIT 400", desde),
    leer("SELECT tipo, editora, creado FROM productos WHERE editora IS NOT NULL AND creado >= ?", desde),
    leer("SELECT fecha, impacto, producto FROM normas WHERE fecha >= ? AND producto IS NOT NULL", desde),
  ]);
  const vacias = () => semanas.map(() => null);
  const idx = (iso) => semanas.indexOf(lunes(iso));
  // 1) parte de lo que manda cada agente que recibe 👎
  const malas = {}, mandados = {};
  for (const m of enviados) { const i = idx(m.creado); if (i >= 0) ((mandados[m.agente] = mandados[m.agente] || semanas.map(() => 0))[i]++); }
  for (const r of reacciones) { const i = idx(r.creado); if (i >= 0 && r.valor < 0 && r.agente) ((malas[r.agente] = malas[r.agente] || semanas.map(() => 0))[i]++); }
  const pctMalas = {};
  for (const a of Object.keys(malas)) pctMalas[a] = semanas.map((_, i) => (mandados[a] && mandados[a][i] ? Math.min(100, 100 * malas[a][i] / mandados[a][i]) : null));
  // 2) cuánto cambia el equipo cada reporte: palabras distintas entre la versión del agente y la corregida (barato:
  //    por conteo de palabras, sin alinear textos; alcanza para ver la tendencia)
  const palabras = (t) => { const c = {}; for (const w of sinTildes(t).split(/[^a-z0-9ñ]+/).filter(Boolean)) c[w] = (c[w] || 0) + 1; return c; };
  const cambio = (a, b) => {
    const x = palabras(a), y = palabras(b); let dif = 0, tot = 0;
    for (const w of new Set([...Object.keys(x), ...Object.keys(y)])) { dif += Math.abs((x[w] || 0) - (y[w] || 0)); tot += (x[w] || 0) + (y[w] || 0); }
    return tot ? 100 * dif / tot : 0;
  };
  const sumaCambio = {}, casosCambio = {};
  for (const c of correcciones) {
    const i = idx(c.actualizado); if (i < 0) continue;
    (sumaCambio[c.tipo] = sumaCambio[c.tipo] || semanas.map(() => [])).at(i).push(cambio(c.original, c.corregido));
    casosCambio[c.tipo] = (casosCambio[c.tipo] || 0) + 1;
  }
  const promedio = (v) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
  const pctCambio = Object.fromEntries(Object.entries(sumaCambio).map(([k, v]) => [k, v.map(promedio)]));
  // 3) cambios que Kiwi tuvo que hacer por reporte, por clase (datos, formato, redacción)
  const kiwi = { dato: semanas.map(() => []), formato: semanas.map(() => []), redaccion: semanas.map(() => []) };
  for (const p of revisados) {
    const i = idx(p.creado), r = parse(p.editora, null); if (i < 0 || !r) continue;
    for (const k of Object.keys(kiwi)) kiwi[k][i].push((r.observaciones || []).filter((o) => o.tipo === k).length);
  }
  const porKiwi = Object.fromEntries(Object.entries(kiwi).map(([k, v]) => [k, v.map(promedio)]));
  // 4) de las normas que el equipo eligió para Keymonitor, cuántas ya había marcado Inés como alto o medio
  const ines = semanas.map(() => [0, 0]);
  for (const n of normas) { const i = idx(n.fecha); if (i >= 0) { ines[i][1]++; if (n.impacto === "alto" || n.impacto === "medio") ines[i][0]++; } }
  // 5) cómo crece el cerebro desde el primer día: los mismos puntos y conexiones de la pantalla de la entrada. El
  //    directorio y los proyectos cuentan desde el primer día; cada documento y sus menciones, desde el día que entró.
  const mapa = await mapaCerebro(env).catch(() => ({ nodos: [], lineas: [] }));
  const diaDoc = {};
  for (const n of mapa.nodos) if (n.tipo === "documento" && n.dia) diaDoc[n.id] = n.dia;
  const dias = [];
  const primero = Object.values(diaDoc).sort()[0];
  if (primero) for (let d = new Date(primero + "T12:00:00Z"); d.toISOString().slice(0, 10) <= hoyPanama(); d.setUTCDate(d.getUTCDate() + 1)) dias.push(d.toISOString().slice(0, 10));
  const acumula = (fechas, base) => dias.map((d) => base + fechas.filter((f) => f <= d).length);
  const crecimiento = { dias, series: {
    puntos: acumula(Object.values(diaDoc), mapa.nodos.filter((n) => !diaDoc[n.id]).length),
    conexiones: acumula(mapa.lineas.map((l) => diaDoc[l.b]).filter(Boolean), mapa.lineas.filter((l) => !diaDoc[l.b]).length),
  } };
  const datos = {
    crecimiento,
    estado: { activo: !!estado.activo, desde: estado.desde || "",
      agentes: porAgente.map((a) => ({ agente: a.agente, ...parse(a.valor, {}) })).filter((a) => a.activo) }, semanas,
    fecha: new Date(Date.now() + HORA_PANAMA * 3600000).toISOString().slice(0, 16).replace("T", " "),
    totales: [
      { valor: reacciones.filter((r) => r.valor > 0).length, texto: "👍 del equipo en el chat" },
      { valor: reacciones.filter((r) => r.valor < 0).length, texto: "👎 del equipo en el chat" },
      { valor: correcciones.length, texto: "reportes corregidos por el equipo" },
      { valor: revisados.length, texto: "reportes revisados por Kiwi" },
      { valor: normas.length, texto: "normas elegidas para Keymonitor" },
    ],
    graficos: [
      { titulo: "Avisos que no le sirvieron al equipo", pct: true, bien: "baja", series: pctMalas,
        explica: "Por agente, parte de lo que manda al chat que recibe 👎.",
        vacio: "Todavía no hay 👎 del equipo. Para que cuenten, el bot tiene que ser administrador del grupo." },
      { titulo: "Cuánto corrige el equipo cada reporte", pct: true, bien: "baja", series: pctCambio, casos: casosCambio,
        explica: "Parte del texto que el equipo cambia antes de enviar (Keylaw, Keymonitor, Keyeconomics, bola roja).",
        vacio: "Todavía no hay reportes corregidos con el aprendizaje encendido." },
      { titulo: "Lo que Kiwi tiene que arreglar al revisar", pct: false, bien: "baja", series: porKiwi,
        explica: "Cambios por reporte cuando Kiwi lo revisa contra sus fuentes, antes de que lo vea el equipo.",
        vacio: "Todavía no hay reportes revisados por Kiwi (necesita Gemini con cuota)." },
      { titulo: "Inés frente al criterio del equipo", pct: true, bien: "sube",
        series: { normativa: ines.map(([a, t]) => (t ? 100 * a / t : null)) }, casos: { normativa: normas.length },
        explica: "De las normas que el equipo eligió para Keymonitor, las que Inés ya había marcado como de impacto alto o medio.",
        vacio: "Todavía no hay normas elegidas para Keymonitor en estas semanas." },
    ],
  };
  memoAprendizaje.datos = datos;
  memoAprendizaje.t = Date.now();
  return datos;
}

async function productosOficina(env) {
  const filas = (await env.DB.prepare("SELECT p.id, p.tipo, p.titulo, p.entidad, p.contenido, p.estado, p.agente, p.creado, p.actualizado, " +
    "p.original IS NOT NULL AS corregido, p.editora, d.fecha, d.url, d.titulo AS fuente, e.nombre AS sobre FROM productos p " +
    "LEFT JOIN documentos d ON d.id = json_extract(p.fuentes, '$[0]') LEFT JOIN entidades e ON e.id = p.entidad " +
    "ORDER BY p.creado DESC LIMIT 60").all()).results;
  // aprendizaje nivel 2: cuántas correcciones del equipo tiene cada tipo de reporte
  const n = {};
  ((await env.DB.prepare("SELECT tipo, COUNT(*) AS n FROM correcciones GROUP BY tipo").all().catch(() => ({ results: [] }))).results)
    .forEach((x) => { n[x.tipo] = x.n; });
  const activo = await aprendizajeActivo(env);
  return filas.map((f) => ({ ...f, editora: parse(f.editora, null), aprendio: n[f.tipo] || 0, aprende: activo }));
}

// El mapa del cerebro (la pantalla de la entrada y su ventana; misma lógica que cerebro/mapa.py): puntos = actores,
// documentos donde aparecen y proyectos que presentó cada diputado; líneas = relaciones, menciones y proponentes.
// Se guarda 10 minutos en memoria para cuidar las lecturas de D1.
const RELACION_MAPA = { integra: "integra", preside: "preside", pertenece_a: "pertenece a", suplente_de: "suplente de",
  dirige: "dirige", junta_directiva: "junta directiva", presento: "presentó", menciona: "aparece en" };
const FUENTE_MAPA = { youtube_asamblea: ["Sesión transcrita", "legal"], gaceta: ["Gaceta Oficial", "legal"], gaceta_norma: ["Norma de la Gaceta", "legal"],
  gaceta_texto: ["Norma de la Gaceta", "legal"], oj_edicto: ["Edicto de la Corte", "legal"], oj_comunicado: ["Comunicado de la Corte", "legal"],
  regulador: ["Ente regulador", "legal"], entrevista: ["Entrevista", "politica"], investigacion: ["Investigación", "politica"],
  investigacion_perfil: ["Perfil investigado", "politica"], inec: ["INEC", "economica"], energia: ["Secretaría de Energía", "economica"] };
const memoMapa = { t: 0, datos: null };
async function mapaCerebro(env) {
  if (memoMapa.datos && Date.now() - memoMapa.t < 600000) return memoMapa.datos;
  const [ents, rels, mens, filas] = (await env.DB.batch([
    env.DB.prepare("SELECT id, tipo, subtipo, nombre, cargo, datos FROM entidades"),
    env.DB.prepare("SELECT origen, tipo, destino, detalle FROM relaciones"),
    env.DB.prepare("SELECT m.documento, m.entidad, d.fuente, d.titulo, d.fecha, d.url, d.creado FROM menciones m JOIN documentos d ON d.id = m.documento"),
    env.DB.prepare("SELECT p.ficha, p.titulo, p.titulo_corto, p.etapa, p.fecha_presentacion, x.nombre FROM proponentes x " +
      "JOIN proyectos p ON p.ficha = x.ficha WHERE x.principal = 1 ORDER BY p.fecha_presentacion DESC"),
  ])).map((r) => r.results);
  const nodos = new Map(), lineas = [], porNombre = {};
  for (const e of ents) {
    const d = parse(e.datos, {});
    nodos.set(e.id, { id: e.id, tipo: e.tipo, sub: e.subtipo || "", nombre: e.nombre, cargo: e.cargo || "", partido: d.partido || "", area: "actores" });
    if (e.tipo === "persona" && d.nombre_en_proyectos) porNombre[d.nombre_en_proyectos] = e.id;
  }
  for (const r of rels) if (nodos.has(r.origen) && nodos.has(r.destino)) lineas.push({ a: r.origen, b: r.destino, t: r.tipo, d: r.detalle || "" });
  const hoy = hoyPanama();
  for (const m of mens) {
    if (!nodos.has(m.entidad)) continue;
    if (!nodos.has(m.documento)) {
      const [etiqueta, area] = FUENTE_MAPA[m.fuente] || [m.fuente, "legal"];
      nodos.set(m.documento, { id: m.documento, tipo: "documento", sub: etiqueta, nombre: m.titulo || etiqueta, cargo: String(m.fecha || "").slice(0, 10),
        url: m.url || "", area, nuevo: String(m.creado || "") >= hoy, dia: String(m.creado || "").slice(0, 10) });
    }
    lineas.push({ a: m.entidad, b: m.documento, t: "menciona", d: "" });
  }
  let n = 0;
  for (const f of filas) {
    const actor = porNombre[f.nombre];
    if (!actor || n >= 350) continue;
    const pid = "proyecto:" + f.ficha;
    if (!nodos.has(pid)) {
      nodos.set(pid, { id: pid, tipo: "proyecto", sub: f.etapa || "", area: "legal", nombre: f.titulo_corto || String(f.titulo || "").slice(0, 90),
        cargo: String(f.fecha_presentacion || "").slice(0, 10) });
      n++;
    }
    lineas.push({ a: actor, b: pid, t: "presento", d: "" });
  }
  const usados = new Set(lineas.flatMap((l) => [l.a, l.b])); // los actores sueltos no aportan al dibujo
  memoMapa.datos = { nodos: [...nodos.values()].filter((x) => usados.has(x.id)), lineas };
  memoMapa.t = Date.now();
  return memoMapa.datos;
}

// Ediciones de la Gaceta que bajó el Vigía (receptor local), con el comienzo de su texto (la tabla de contenido).
// Se guarda 10 minutos: la subconsulta del comienzo del texto recorre la tabla de fragmentos (FTS, documento sin
// índice) y era la consulta que más filas leía de D1 (1,2 millones en 12 horas el 26/10).
const memoGaceta = { t: 0, datos: null };
async function gacetaOficina(env) {
  if (memoGaceta.datos && Date.now() - memoGaceta.t < 600000) return memoGaceta.datos;
  memoGaceta.datos = await gacetaLeer(env);
  memoGaceta.t = Date.now();
  return memoGaceta.datos;
}
async function gacetaLeer(env) {
  return (await env.DB.prepare("SELECT d.id, d.titulo, d.fecha, d.url, d.largo, " +
    "(SELECT decision FROM decisiones WHERE ref = 'gaceta:' || d.id) AS decision, " +
    "(SELECT substr(f.texto, 1, 1500) FROM fragmentos f WHERE f.documento = d.id AND f.n = 0) AS inicio " +
    "FROM documentos d WHERE d.fuente = 'gaceta' ORDER BY d.fecha DESC, d.titulo DESC LIMIT 30").all()).results;
}

// Normas de las últimas ediciones leídas por la Analista normativa, con su Keymonitor si lo tiene.
async function normasOficina(env) {
  return (await env.DB.prepare("SELECT n.id, n.gaceta, n.edicion, n.fecha, n.entidad, n.tipo, n.numero, n.titulo, n.resumen, n.sectores, " +
    "n.impacto, n.paginas, n.producto, n.nombre, n.archivo, n.pdf FROM normas n WHERE n.gaceta IN (SELECT id FROM documentos WHERE fuente = 'gaceta' " +
    "ORDER BY fecha DESC, titulo DESC LIMIT 15) ORDER BY n.fecha DESC, n.edicion, n.rowid").all().catch(() => ({ results: [] }))).results
    .map((n) => ({ ...n, sectores: parse(n.sectores, []) }));
}

const TAREAS_PERMITIDAS = { relatora: ["transcribir", "keylaw"], vigia: ["gaceta"], perfilador: ["keyperfil"], normativa: ["keymonitor"], regulatoria: ["keymonitor", "revisar"], judicial: ["keymonitor", "revisar"], entrevistas: ["escuchar", "bola"], cifras: ["revisar", "keyeconomics"] };

// Sesiones de comisión (agenda de una semana atrás a dos adelante) con la decisión de la oficina, y las sesiones ya
// transcritas con sus Keylaw (los "archivado" son Keylaw escritos pero no pedidos: la oficina puede pedirlos).
async function sesionesOficina(env) {
  const hoy = new Date(Date.now() + HORA_PANAMA * 3600 * 1000);
  const desde = new Date(hoy - 7 * 86400000).toISOString().slice(0, 10), hasta = new Date(+hoy + 14 * 86400000).toISOString().slice(0, 10);
  const [agenda, docs, prods, canal] = (await env.DB.batch([
    env.DB.prepare("SELECT a.id, a.fecha, a.hora, a.comision, a.lugar, a.fichas, a.descripcion, x.decision FROM agenda a " +
      "LEFT JOIN decisiones x ON x.ref = 'agenda:' || a.id WHERE a.fecha BETWEEN ? AND ? ORDER BY a.fecha, a.hora").bind(desde, hasta),
    env.DB.prepare("SELECT id, titulo, fecha, url, largo FROM documentos WHERE fuente = 'youtube_asamblea' ORDER BY fecha DESC, creado DESC LIMIT 200"),
    env.DB.prepare("SELECT id, estado, json_extract(fuentes, '$[0]') AS doc FROM productos WHERE tipo = 'keylaw'"),
    env.DB.prepare("SELECT valor FROM config WHERE clave = 'canal_asamblea'"),
  ])).map((r) => r.results);
  // botón «Ver sesión»: las sesiones de hoy se enlazan con la transmisión en vivo o programada del canal que lleva el
  // nombre de la comisión (la Mac anota el canal cada 3 min); si no hay, la oficina abre el canal
  let vivas = [];
  try { vivas = JSON.parse((canal[0] || {}).valor || "[]"); } catch (e) { /* sin canal anotado */ }
  const plano = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
  const hoyTxt = hoy.toISOString().slice(0, 10);
  const videoDe = (a) => {
    if (a.fecha !== hoyTxt) return null;
    const c = plano(/^Pleno/.test(a.comision || "") ? "Pleno de la Asamblea" : a.comision);
    const v = c && vivas.find((x) => plano(x.titulo).includes(c) || c.includes(plano(x.titulo)));
    return v ? { id: v.id, vivo: v.estado === "is_live" } : null;
  };
  return { agenda: agenda.map((a) => ({ ...a, pleno: /^Pleno/.test(a.comision || ""), video: videoDe(a),
    descripcion: /^Pleno/.test(a.comision || "") ? (a.descripcion || "").split("\n").length + " puntos en el Orden del Día" : a.descripcion })),
  transcritas: docs.map((d) => {
    const keylaw = prods.filter((p) => p.doc === d.id).map((p) => ({ id: p.id, estado: p.estado }));
    const video = ((d.url || "").match(/(?:v=|youtu\.be\/|live\/)([\w-]{11})/) || [])[1] || null;
    return { ...d, titulo: (d.titulo || "").replace(/\s*\(\d{4}-\d{2}-\d{2}\)$/, ""), keylaw, video,
      pedir: keylaw.every((k) => k.estado === "archivado") };
  }) };
}

// Tareas recientes y si la Mac de la oficina está encendida (su último latido).
async function tareasOficina(env) {
  const [t, l] = await Promise.all([
    env.DB.prepare("SELECT id, agente, tipo, ref, estado, detalle, creado, hecho FROM tareas ORDER BY creado DESC LIMIT 30").all()
      .then((r) => r.results).catch(() => []),
    env.DB.prepare("SELECT equipo, momento, detalle FROM latidos").all().then((r) => r.results).catch(() => []),
  ]);
  return { tareas: t, latidos: l, ahora: new Date().toISOString().slice(0, 19) };
}

const PAGINA_MAPA = __PAGINA_MAPA__;
const PAGINA_APRENDIZAJE = __PAGINA_APRENDIZAJE__;
const PAGINA_OFICINA = __PAGINA_OFICINA__;
const PAGINA_PREVIA = __PAGINA_PREVIA__;
