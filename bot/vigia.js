// Vigía externo (Worker aparte, `vigia-panama`): cada 5 minutos mira el último latido de la mesa en D1 (tabla
// `latidos`, la escribe cerebro/mesa.py cada ~20 s en UTC). Si la mesa lleva más de UMBRAL minutos sin latir —PC
// apagada, sin internet, Windows reiniciando o D1 sin escrituras— avisa al grupo de la oficina por Telegram; repite
// cada RECORDAR minutos mientras siga caída y avisa cuando vuelve. No depende de la PC: si la PC muere, esto sigue.
// Se ARMA solo al ver el primer latido fresco (así no grita mientras la mesa todavía no se instaló).
// Estado en la tabla `vigia` (clave, valor): estado = sin_armar | vivo | caido; aviso = último aviso (ISO UTC).
// GET / → estado en JSON (para revisar a mano). Desplegar: python3 bot/desplegar_vigia.py

const UMBRAL = 15;    // minutos sin latido para dar por caída la mesa (tareas largas pueden frenar el latido unos minutos)
const RECORDAR = 120; // minutos entre recordatorios mientras siga caída

function horaPanama(iso) {
  const d = new Date(new Date(iso + "Z").getTime() - 5 * 3600 * 1000); // Panamá = UTC-5, sin horario de verano
  return d.toISOString().slice(8, 10) + "/" + d.toISOString().slice(5, 7) + " " + d.toISOString().slice(11, 16);
}

function duracion(min) {
  min = Math.round(min);
  if (min < 60) return min + " min";
  const h = Math.floor(min / 60), m = min % 60;
  return h + " h" + (m ? " " + m + " min" : "");
}

async function telegram(env, texto) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT, text: texto, disable_web_page_preview: true }),
  });
  if (!r.ok) throw new Error("Telegram " + r.status + " " + (await r.text()).slice(0, 200));
}

async function leer(env) {
  await env.DB.prepare("CREATE TABLE IF NOT EXISTS vigia (clave TEXT PRIMARY KEY, valor TEXT)").run();
  const [lat, est] = await Promise.all([
    env.DB.prepare("SELECT equipo, momento, detalle FROM latidos ORDER BY momento DESC LIMIT 1").first().catch(() => null),
    env.DB.prepare("SELECT clave, valor FROM vigia").all().then((r) => r.results).catch(() => []),
  ]);
  const estado = Object.fromEntries(est.map((x) => [x.clave, x.valor]));
  const edad = lat ? (Date.now() - new Date(lat.momento + "Z").getTime()) / 60000 : Infinity;
  return { lat, edad, estado: estado.estado || "sin_armar", aviso: estado.aviso || null, caida: estado.caida || null };
}

async function guardar(env, valores) {
  await env.DB.batch(Object.entries(valores).map(([k, v]) =>
    env.DB.prepare("INSERT OR REPLACE INTO vigia (clave, valor) VALUES (?, ?)").bind(k, v)));
}

async function revisar(env) {
  const s = await leer(env);
  const ahora = new Date().toISOString().slice(0, 19);
  const viva = s.edad <= UMBRAL;
  if (viva) {
    if (s.estado === "caido") {
      const fuera = (Date.now() - new Date(s.caida + "Z").getTime()) / 60000;
      await telegram(env, `✅ La mesa de la oficina volvió a latir (${s.lat.equipo}). Estuvo sin señal unos ${duracion(fuera + UMBRAL)}.`);
    }
    if (s.estado !== "vivo") await guardar(env, { estado: "vivo" });
    return "vivo";
  }
  if (s.estado === "sin_armar") return "sin_armar"; // nunca la vio viva desde que se instaló: no avisa
  const recordar = s.estado === "caido" && (Date.now() - new Date(s.aviso + "Z").getTime()) / 60000 >= RECORDAR;
  if (s.estado === "vivo" || recordar) {
    const desde = s.lat ? `desde las ${horaPanama(s.lat.momento)} (hace ${duracion(s.edad)})` : "";
    await telegram(env, (recordar ? "🚨 Sigue sin señal" : "🚨 La mesa de la oficina dejó de latir") +
      ` ${desde}. Último estado: «${s.lat?.detalle || "—"}» (${s.lat?.equipo || "—"}).\n` +
      "Puede ser: PC apagada o sin internet, Windows reiniciando, la mesa colgada o D1 sin escrituras. " +
      "Revisar por Tailscale (SSH) o el escritorio remoto.");
    await guardar(env, recordar ? { aviso: ahora } : { estado: "caido", aviso: ahora, caida: ahora });
  }
  return "caido";
}

export default {
  async scheduled(evento, env, ctx) {
    ctx.waitUntil(revisar(env));
  },
  async fetch(req, env) {
    const s = await leer(env);
    return Response.json({
      estado: s.estado, ultimo_latido_utc: s.lat?.momento || null, equipo: s.lat?.equipo || null,
      minutos_sin_latir: Number.isFinite(s.edad) ? Math.round(s.edad) : null, umbral_min: UMBRAL,
      ultimo_aviso_utc: s.aviso,
    });
  },
};
