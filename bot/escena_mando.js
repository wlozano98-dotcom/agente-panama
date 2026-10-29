/* ---------------------------------------------------------------- la oficina como CENTRO DE MANDO (VERSIÓN DE PRUEBA, 2026-10-26)
   Andrés descartó la de frente y la isométrica ("parece un juego") y eligió dejar la metáfora de la oficina: el
   cerebro vivo al centro (la forma ilustrada con los puntos reales del mapa adentro) y los agentes en un anillo, por
   coordinación (legal a la izquierda, política a la derecha, económica arriba), cada uno con su retrato y una línea al
   cerebro por la que viajan señales (más seguido cuando trabaja); el cerebro destella al recibirlas. Kiwi abajo es la
   puerta para preguntarle al cerebro. Los botones de arriba se acercan a una coordinación y apagan las otras. Las
   personas son las de la escena publicada (escena_nueva.js). Se sirve solo en la Mac (bot/prueba_local.py). */
(function escenaMando() {
  var ZW = 1536, ZH = 1024;
  // cómo es cada persona (ficticia): piel, pelo, peinado, ropa
  var LOOK = {
    relatora: { piel: "#d9a27c", pelo: "#1d1712", peinado: "corto", ropa: "#dce8f7", tipo: "camisa" },
    normativa: { piel: "#f1c6a2", pelo: "#5a3218", peinado: "largo", ropa: "#24272f", interior: "#ffffff", tipo: "saco", aretes: true },
    judicial: { piel: "#e6b28b", pelo: "#2a1d16", peinado: "melena", ropa: "#1f5a4a", interior: "#f4f1ea", tipo: "saco", lentes: true },
    regulatoria: { piel: "#efc29c", pelo: "#6b4425", peinado: "corto", ropa: "#1f2a44", interior: "#ffffff", tipo: "sueter", lentes: true },
    agenda: { piel: "#f2c5a0", pelo: "#4a2a17", peinado: "largo", ropa: "#f5f2ec", tipo: "blusa", aretes: true },
    entrevistas: { piel: "#c98d68", pelo: "#151515", peinado: "corto", ropa: "#a9c4ea", tipo: "camisa", audifonos: true },
    medios: { piel: "#f0bf98", pelo: "#6a3a1f", peinado: "largo", ropa: "#e7a3a6", interior: "#ffffff", tipo: "saco", aretes: true },
    politico: { piel: "#cf9670", pelo: "#2b2420", peinado: "corto", ropa: "#f6f3ea", tipo: "guayabera", barba: true },
    perfilador: { piel: "#efc39d", pelo: "#3a2216", peinado: "mono", ropa: "#9aa3ad", interior: "#ffffff", tipo: "saco" },
    cifras: { piel: "#e2ab84", pelo: "#4b2e1d", peinado: "corto", ropa: "#22324f", interior: "#ffffff", tipo: "saco", corbata: true },
    economico: { piel: "#e8b792", pelo: "#2d1c14", peinado: "melena", ropa: "#6f7480", interior: "#ffffff", tipo: "saco" },
  };
  var ICONO = { relatora: "KL", normativa: "KM", judicial: "J", regulatoria: "R", agenda: "A", entrevistas: "E", medios: "M",
    politico: "KP", perfilador: "KF", cifras: "C", economico: "KE" };
  var semilla = 7;
  function azar() { semilla = (semilla * 9301 + 49297) % 233280; return semilla / 233280; }
  function px(z, x) { return ((z * ZW + x) / (3 * ZW) * 100) + "%"; }
  function py(y) { return (y / ZH * 100) + "%"; }

  /* ---------- la ciudad por la ventana */
  function ciudad(x0, x1, base, alto, puente) {
    var s = "";
    // al fondo: torres claras; adelante: torres más oscuras con ventanas que se encienden de noche
    [[.55, "lejos"], [1, "cerca"]].forEach(function (capa) {
      var x = x0 - 10;
      while (x < x1) {
        var w = 16 + azar() * (capa[1] === "cerca" ? 30 : 22), h = alto * capa[0] * (.25 + azar() * .75);
        if (azar() < .18) h *= 1.35;
        s += '<rect class="edif ' + capa[1] + '" x="' + x.toFixed(1) + '" y="' + (base - h).toFixed(1) + '" width="' + w.toFixed(1) + '" height="' + h.toFixed(1) + '"/>';
        if (capa[1] === "cerca") {
          if (azar() < .3) s += '<rect class="edif cerca" x="' + (x + w / 2 - 1.5).toFixed(1) + '" y="' + (base - h - 18).toFixed(1) + '" width="3" height="18"/>';
          s += '<rect class="brillo-edif" x="' + x.toFixed(1) + '" y="' + (base - h).toFixed(1) + '" width="' + (w * .32).toFixed(1) + '" height="' + h.toFixed(1) + '"/>';
          for (var yy = base - h + 8; yy < base - 6; yy += 11) for (var xx = x + 4; xx < x + w - 5; xx += 7) if (azar() < .33)
            s += '<rect class="luz" x="' + xx.toFixed(1) + '" y="' + yy.toFixed(1) + '" width="3" height="4"/>';
        }
        x += w + (capa[1] === "cerca" ? 4 + azar() * 10 : 2 + azar() * 6);
      }
    });
    // el mar, la Cinta Costera y, en la legal, el Puente de las Américas
    s += '<rect class="mar" x="' + x0 + '" y="' + base + '" width="' + (x1 - x0) + '" height="' + 300 + '"/>';
    s += '<path class="costa" d="M' + x0 + ' ' + (base + 2) + ' C ' + (x0 + (x1 - x0) * .35) + ' ' + (base + 6) + ', ' + (x0 + (x1 - x0) * .6) + ' ' + (base + 40) + ', ' + x1 + ' ' + (base + 60) + ' L ' + x1 + ' ' + (base + 74) + ' C ' + (x0 + (x1 - x0) * .6) + ' ' + (base + 54) + ', ' + (x0 + (x1 - x0) * .35) + ' ' + (base + 18) + ', ' + x0 + ' ' + (base + 14) + ' Z"/>';
    s += '<path class="calle" d="M' + x0 + ' ' + (base + 9) + ' C ' + (x0 + (x1 - x0) * .35) + ' ' + (base + 13) + ', ' + (x0 + (x1 - x0) * .6) + ' ' + (base + 47) + ', ' + x1 + ' ' + (base + 67) + '"/>';
    if (puente) {
      var px0 = puente[0], px1 = puente[1], py0 = base + 50, cima = py0 - 62;
      s += '<g class="puente"><path d="M' + px0 + ' ' + py0 + ' Q ' + ((px0 + px1) / 2) + ' ' + (cima - 30) + ' ' + px1 + ' ' + py0 + '" fill="none" stroke-width="6"/>' +
        '<path d="M' + (px0 - 60) + ' ' + (py0 - 8) + ' L ' + (px1 + 60) + ' ' + (py0 - 8) + '" stroke-width="5"/>';
      for (var i = 1; i < 12; i++) { var t = i / 12, bx = px0 + (px1 - px0) * t, by = (1 - t) * (1 - t) * py0 + 2 * (1 - t) * t * (cima - 30) + t * t * py0; s += '<path d="M' + bx.toFixed(1) + ' ' + by.toFixed(1) + ' V ' + (py0 - 8) + '" stroke-width="1.6"/>'; }
      s += '</g>';
    }
    // nubes de día
    for (var n = 0; n < 4; n++) { var cx = x0 + azar() * (x1 - x0), cy = base - alto - 40 - azar() * 90;
      s += '<g class="nube"><ellipse cx="' + cx + '" cy="' + cy + '" rx="46" ry="13"/><ellipse cx="' + (cx + 26) + '" cy="' + (cy - 8) + '" rx="28" ry="12"/><ellipse cx="' + (cx - 22) + '" cy="' + (cy - 4) + '" rx="22" ry="9"/></g>'; }
    return s;
  }
  function ventanal(id, x, y, w, h, columnas, puente) {
    var s = '<clipPath id="v-' + id + '"><rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"/></clipPath>' +
      '<g clip-path="url(#v-' + id + ')"><rect class="cielo" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"/>' +
      '<circle class="luna" cx="' + (x + w * .78) + '" cy="' + (y + 70) + '" r="20"/>' +
      ciudad(x, x + w, y + h * .74, h * .5, puente) + '<rect class="reflejo-vidrio" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"/></g>';
    s += '<rect class="marco" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="4"/>';
    for (var i = 1; i < columnas; i++) s += '<rect class="parante" x="' + (x + w * i / columnas - 5) + '" y="' + y + '" width="10" height="' + h + '"/>';
    return s;
  }
  function listones(x, w, y, h) {
    var s = "";
    for (var i = 0; i * 14 < w; i++) s += '<rect x="' + (x + i * 14) + '" y="' + y + '" width="10" height="' + h + '" fill="' + (i % 2 ? "#c79a6b" : "#d6ab7c") + '"/>';
    return s + '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="url(#sombra-listones)"/>';
  }
  function planta(x, y, s, oscura) {
    var c1 = oscura ? "#2f6b48" : "#3f8a5a", c2 = oscura ? "#24553a" : "#2f7049", hojas = "";
    [[-60, -150, -20], [-30, -175, -8], [5, -185, 4], [40, -165, 16], [65, -130, 26], [-75, -105, -30], [80, -95, 34]].forEach(function (h, i) {
      hojas += '<path d="M0 -40 Q ' + (h[0] * .4) + ' ' + (h[1] * .6) + ' ' + h[0] + ' ' + h[1] + ' Q ' + (h[0] * .7 + 10) + ' ' + (h[1] * .5) + ' 0 -40Z" fill="' + (i % 2 ? c1 : c2) + '"/>';
    });
    return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')">' + hojas +
      '<path d="M-34 -42 L34 -42 L28 0 L-28 0Z" fill="#efe7da"/><rect x="-36" y="-48" width="72" height="9" rx="3" fill="#e2d7c6"/></g>';
  }
  function plantita(x, y) {
    return '<g transform="translate(' + x + ' ' + y + ')"><path d="M-9 -16 Q-14 -34 -2 -38 Q-4 -24 0 -16Z M0 -16 Q2 -40 12 -36 Q8 -24 3 -16Z M-4 -16 Q-22 -26 -18 -32 Q-10 -24 -2 -18Z" fill="#3f8a5a"/>' +
      '<path d="M-10 -17 L10 -17 L8 0 L-8 0Z" fill="#f2ece2"/></g>';
  }
  function lapicero(x, y) {
    return '<g transform="translate(' + x + ' ' + y + ')"><rect x="-8" y="-20" width="16" height="20" rx="2" fill="#2d3340"/><path d="M-4 -20 L-6 -34 M1 -20 L1 -36 M5 -20 L8 -32" stroke="#e8b04a" stroke-width="2.4" stroke-linecap="round"/></g>';
  }

  /* ---------- una persona, de frente, detrás de la mesa (origen: centro, a la altura del borde de la mesa) */
  function persona(id, a) {
    var L = LOOK[id], p = L.piel, pe = L.pelo, s = "";
    // la silla, detrás
    s += '<path d="M-62 -60 L-60 -166 Q-60 -184 -42 -184 L42 -184 Q60 -184 60 -166 L62 -60Z" fill="#2c3038"/>' +
      '<path d="M-50 -66 L-49 -160 Q-49 -172 -36 -172 L36 -172 Q49 -172 49 -160 L50 -66Z" fill="#3a3f49"/>';
    // pelo largo que cae detrás de los hombros
    if (L.peinado === "largo") s += '<path d="M-46 -152 Q-58 -60 -50 -30 L50 -30 Q58 -60 46 -152Z" fill="' + pe + '"/>';
    if (L.peinado === "melena") s += '<path d="M-44 -150 Q-52 -95 -40 -78 L40 -78 Q52 -95 44 -150Z" fill="' + pe + '"/>';
    // torso y brazos apoyados en la mesa
    var torso = '<path d="M-78 0 L-74 -66 Q-70 -92 -40 -100 L-14 -106 L14 -106 L40 -100 Q70 -92 74 -66 L78 0Z" fill="' + L.ropa + '"/>';
    s += torso;
    if (L.tipo === "saco" || L.tipo === "sueter") {
      s += '<path d="M-14 -106 L0 -62 L14 -106Z" fill="' + (L.interior || "#fff") + '"/>';
      if (L.tipo === "saco") s += '<path d="M-14 -106 L-24 -96 L-6 -50 L0 -62Z M14 -106 L24 -96 L6 -50 L0 -62Z" fill="rgba(0,0,0,.18)"/>';
      if (L.tipo === "sueter") s += '<path d="M-14 -106 L-6 -96 L0 -104 L6 -96 L14 -106" fill="none" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>';
      if (L.corbata) s += '<path d="M-4 -98 L4 -98 L6 -70 L0 -60 L-6 -70Z" fill="#9500c5"/>';
    } else if (L.tipo === "camisa") {
      s += '<path d="M-14 -106 L-4 -90 L0 -98 L4 -90 L14 -106 L8 -108 L0 -100 L-8 -108Z" fill="rgba(255,255,255,.75)"/><path d="M0 -98 V 0" stroke="rgba(0,0,0,.08)" stroke-width="2"/>';
    } else if (L.tipo === "guayabera") {
      s += '<path d="M-14 -106 L-4 -92 L0 -98 L4 -92 L14 -106" fill="none" stroke="#e2ddd0" stroke-width="3"/>' +
        '<path d="M-32 -84 V -10 M-24 -84 V -10 M24 -84 V -10 M32 -84 V -10" stroke="#e4ded0" stroke-width="2"/>';
    } else {
      s += '<path d="M-16 -106 Q0 -86 16 -106" fill="none" stroke="rgba(0,0,0,.12)" stroke-width="2.5"/>';
    }
    s += '<path d="M-74 -66 Q-76 -40 -70 0 L-52 0 Q-56 -40 -54 -70Z M74 -66 Q76 -40 70 0 L52 0 Q56 -40 54 -70Z" fill="rgba(0,0,0,.08)"/>';
    // manos sobre la mesa (teclean)
    s += '<g class="mano mi"><ellipse cx="-34" cy="-4" rx="15" ry="9" fill="' + p + '"/></g><g class="mano md"><ellipse cx="34" cy="-4" rx="15" ry="9" fill="' + p + '"/></g>';
    // cuello
    s += '<path d="M-13 -124 L13 -124 L14 -102 Q0 -94 -14 -102Z" fill="' + p + '"/><path d="M-13 -112 Q0 -104 13 -112 L13 -106 Q0 -98 -13 -106Z" fill="rgba(0,0,0,.12)"/>';
    // la cabeza (se mueve sola)
    var c = '<g class="cabeza2">';
    if (L.peinado === "mono") c += '<circle cx="0" cy="-212" r="17" fill="' + pe + '"/>';
    c += '<ellipse cx="-34" cy="-150" rx="7" ry="10" fill="' + p + '"/><ellipse cx="34" cy="-150" rx="7" ry="10" fill="' + p + '"/>';
    c += '<path d="M-33 -168 Q-34 -128 -20 -118 Q0 -106 20 -118 Q34 -128 33 -168 Q30 -196 0 -198 Q-30 -196 -33 -168Z" fill="' + p + '"/>';
    if (L.barba) c += '<path d="M-31 -146 Q-30 -122 -18 -114 Q0 -104 18 -114 Q30 -122 31 -146 Q26 -128 14 -126 Q0 -132 -14 -126 Q-26 -128 -31 -146Z" fill="' + pe + '" opacity=".85"/>';
    // pelo de arriba
    var pelo = {
      corto: "M-35 -160 Q-38 -198 -6 -204 Q30 -208 36 -172 Q36 -158 33 -156 Q28 -182 6 -184 Q-18 -186 -30 -170Z",
      largo: "M-36 -150 Q-42 -204 0 -206 Q42 -204 36 -150 Q32 -178 14 -188 Q-4 -176 -26 -178 Q-34 -168 -36 -150Z",
      melena: "M-38 -146 Q-44 -206 0 -207 Q44 -206 38 -146 Q34 -176 18 -186 Q0 -178 -20 -184 Q-34 -172 -38 -146Z",
      mono: "M-35 -156 Q-38 -202 0 -204 Q38 -202 35 -156 Q30 -184 0 -188 Q-30 -184 -35 -156Z",
    }[L.peinado];
    c += '<path d="' + pelo + '" fill="' + pe + '"/>';
    // la cara: cejas, ojos (miran a la pantalla o al usuario), nariz y boca
    c += '<g class="cara"><path d="M-21 -164 Q-14 -169 -6 -165 M6 -165 Q14 -169 21 -164" stroke="' + pe + '" stroke-width="3" fill="none" stroke-linecap="round"/>' +
      '<g class="ojos"><ellipse cx="-13" cy="-152" rx="4" ry="5" fill="#2a211c"/><ellipse cx="13" cy="-152" rx="4" ry="5" fill="#2a211c"/>' +
      '<circle cx="-11.6" cy="-153.6" r="1.3" fill="#fff"/><circle cx="14.4" cy="-153.6" r="1.3" fill="#fff"/></g>' +
      '<path d="M0 -148 Q-3 -138 2 -136" stroke="rgba(0,0,0,.22)" stroke-width="2" fill="none" stroke-linecap="round"/>' +
      '<ellipse cx="-20" cy="-138" rx="6" ry="3.5" fill="#e98a7a" opacity=".22"/><ellipse cx="20" cy="-138" rx="6" ry="3.5" fill="#e98a7a" opacity=".22"/>' +
      '<path class="boca boca-n" d="M-7 -128 Q0 -125 7 -128" stroke="#9b4f45" stroke-width="2.4" fill="none" stroke-linecap="round"/>' +
      '<path class="boca boca-s" d="M-10 -130 Q0 -119 10 -130 Q0 -125 -10 -130Z" fill="#9b4f45"/></g>';
    if (L.lentes) c += '<g fill="none" stroke="#2b2b2b" stroke-width="2.4"><rect x="-25" y="-160" width="20" height="15" rx="5"/><rect x="5" y="-160" width="20" height="15" rx="5"/><path d="M-5 -154 H5"/></g>';
    if (L.aretes) c += '<circle cx="-34" cy="-138" r="2.6" fill="#e8c26a"/><circle cx="34" cy="-138" r="2.6" fill="#e8c26a"/>';
    if (L.audifonos) c += '<path d="M-38 -150 Q-40 -212 0 -212 Q40 -212 38 -150" fill="none" stroke="#2d3340" stroke-width="5"/><rect x="-44" y="-162" width="12" height="22" rx="5" fill="#9500c5"/><rect x="32" y="-162" width="12" height="22" rx="5" fill="#9500c5"/>';
    c += '</g>';
    s += c;
    return '<g class="persona2 trabaja' + (a.apagado ? " pronto" : "") + '" data-id="' + id + '">' + s + '</g>';
  }

  var retratoViejo = retrato;  // Kiwi y quien no esté en la escena conservan su dibujo
  retrato = function (a) {
    if (!LOOK[a.id]) return retratoViejo(a);
    var id = "recorte-" + a.id;
    return '<svg viewBox="-110 -250 220 220" aria-hidden="true"><defs><clipPath id="' + id + '"><circle cx="0" cy="-140" r="110"/></clipPath></defs>' +
      '<circle cx="0" cy="-140" r="110" fill="#efe4fb"/><g clip-path="url(#' + id + ')">' + persona(a.id, a).replace("persona2 trabaja", "persona2 retrato") + '</g></svg>';
  };
  /* ---------- el centro de mando: el cerebro al centro, los agentes en un anillo por coordinación */
  var VW = 1600, VH = 900, CX = 800, CY = 452, RX = 610, RY = 335;
  var SECTOR = {
    legal: { nombre: "COORDINACIÓN LEGAL", color: "#b48cf2", area: 0, agentes: ["relatora", "normativa", "judicial", "regulatoria"] },
    politica: { nombre: "INTELIGENCIA POLÍTICA", color: "#7fb2ff", area: 1, agentes: ["entrevistas", "medios", "perfilador"] },
    economica: { nombre: "INTELIGENCIA ECONÓMICA", color: "#5fd1a0", area: 2, agentes: ["cifras"] },
  };
  var ANG = { relatora: 217, normativa: 194, judicial: 166, regulatoria: 143, entrevistas: 323, medios: 346, perfilador: 12, cifras: 270 };
  var DE = {}; Object.keys(SECTOR).forEach(function (s) { SECTOR[s].agentes.forEach(function (id) { DE[id] = s; }); });
  function pos(g, f) { var r = g * Math.PI / 180; f = f || 1; return [CX + RX * f * Math.cos(r), CY + RY * f * Math.sin(r)]; }
  function arco(g0, g1, f) {
    var a = pos(g0, f), b = pos(g1, f);
    return "M" + a[0].toFixed(1) + " " + a[1].toFixed(1) + " A" + (RX * f) + " " + (RY * f) + " 0 0 1 " + b[0].toFixed(1) + " " + b[1].toFixed(1);
  }
  var FORMA = "M0 -128 C-34 -150 -104 -150 -136 -112 C-190 -104 -214 -46 -196 6 C-214 56 -168 112 -110 104 C-80 132 -28 128 0 104 " +
    "C28 128 80 132 110 104 C168 112 214 56 196 6 C214 -46 190 -104 136 -112 C104 -150 34 -150 0 -128Z";
  var EB = 1.45;  // escala del cerebro

  var s = '<defs>' +
    '<radialGradient id="m-fondo" cx="50%" cy="48%" r="70%"><stop offset="0" stop-color="#2a2340"/><stop offset=".55" stop-color="#1a1b24"/><stop offset="1" stop-color="#121318"/></radialGradient>' +
    '<radialGradient id="halo-cerebro"><stop offset="0" stop-color="#b48cf2" stop-opacity=".55"/><stop offset=".6" stop-color="#9500c5" stop-opacity=".12"/><stop offset="1" stop-color="#9500c5" stop-opacity="0"/></radialGradient>' +
    '<pattern id="m-puntos" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="rgba(212,187,255,.10)"/></pattern>' +
    '<filter id="m-brillo" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
    '</defs>';
  s += '<rect width="' + VW + '" height="' + VH + '" fill="url(#m-fondo)"/><rect width="' + VW + '" height="' + VH + '" fill="url(#m-puntos)"/>';
  // el anillo y los arcos de cada coordinación
  s += '<ellipse cx="' + CX + '" cy="' + CY + '" rx="' + RX + '" ry="' + RY + '" fill="none" stroke="rgba(212,187,255,.14)" stroke-width="1.5" stroke-dasharray="3 9"/>';
  s += '<ellipse cx="' + CX + '" cy="' + CY + '" rx="' + (RX * .7) + '" ry="' + (RY * .7) + '" fill="none" stroke="rgba(212,187,255,.07)" stroke-width="1"/>';
  [["legal", 128, 232], ["politica", 308, 28], ["economica", 252, 288]].forEach(function (x) {
    s += '<path class="arco-sector" data-sector="' + x[0] + '" d="' + arco(x[1], x[2], 1.0) + '" fill="none" stroke="' + SECTOR[x[0]].color + '" stroke-width="3" stroke-linecap="round" opacity=".55"/>';
  });
  // nombres de las coordinaciones, por fuera del anillo
  [["legal", CX - RX - 6, CY - RY * .74, "start"], ["politica", CX + RX + 6, CY - RY * .74, "end"], ["economica", CX, CY - RY - 74, "middle"]].forEach(function (x) {
    s += '<text class="nombre-sector" data-sector="' + x[0] + '" x="' + x[1] + '" y="' + x[2] + '" text-anchor="' + x[3] + '" font-family="Figtree, sans-serif" font-size="15" font-weight="700" letter-spacing="3" fill="' + SECTOR[x[0]].color + '">' + SECTOR[x[0]].nombre + '</text>';
  });
  // las líneas de cada agente al cerebro (por ahí viajan las señales)
  var LINEA = {};
  AGENTES.forEach(function (a) {
    if (!(a.id in ANG)) return;
    var p = pos(ANG[a.id]), q = [CX + (p[0] - CX) * .36, CY + (p[1] - CY) * .42], c = [(p[0] + q[0]) / 2 + (CY - p[1]) * .08, (p[1] + q[1]) / 2 + (p[0] - CX) * .04];
    LINEA[a.id] = "M" + p[0].toFixed(1) + " " + p[1].toFixed(1) + " Q" + c[0].toFixed(1) + " " + c[1].toFixed(1) + " " + q[0].toFixed(1) + " " + q[1].toFixed(1);
    s += '<path class="linea-agente" data-id="' + a.id + '" data-sector="' + DE[a.id] + '" d="' + LINEA[a.id] + '" fill="none" stroke="' + SECTOR[DE[a.id]].color + '" stroke-width="2" opacity="' + (a.apagado ? .12 : .32) + '"/>';
  });
  // Kiwi, abajo: la puerta de entrada (pregunta al cerebro)
  var pk = pos(90, 1.0), qk = [CX, CY + 150 * EB * .95];
  LINEA.jefe = "M" + pk[0] + " " + (pk[1] - 50) + " L" + qk[0] + " " + qk[1];
  s += '<path class="linea-agente" d="' + LINEA.jefe + '" fill="none" stroke="#9bd14e" stroke-width="2" opacity=".3" stroke-dasharray="4 6"/>';
  // el cerebro
  s += '<g class="cerebro-mando" transform="translate(' + CX + ' ' + (CY - 6) + ') scale(' + EB + ')">' +
    '<ellipse cx="0" cy="0" rx="300" ry="215" fill="url(#halo-cerebro)" class="halo-cerebro"/>' +
    '<clipPath id="clip-cerebro"><path d="' + FORMA + '"/></clipPath>' +
    '<path d="' + FORMA + '" fill="rgba(180,140,242,.10)" stroke="#b48cf2" stroke-width="2" filter="url(#m-brillo)"/>' +
    '<g clip-path="url(#clip-cerebro)"><g id="red-cerebro"></g></g>' +
    '<path d="M0 -128 C-8 -60 8 0 0 104" fill="none" stroke="rgba(212,187,255,.35)" stroke-width="2"/></g>';
  s += '<text id="cifras-cerebro" x="' + CX + '" y="' + (CY + 132 * EB + 30) + '" text-anchor="middle" font-family="Figtree, sans-serif" font-size="14" fill="#a3a3ae"></text>';
  s += '<g class="senales"></g>';
  // los agentes: retrato redondo, anillo del color de su coordinación, nombre y función
  AGENTES.forEach(function (a) {
    if (!(a.id in ANG)) return;
    var p = pos(ANG[a.id]), col = SECTOR[DE[a.id]].color;
    var r = retrato(a).replace("<svg ", '<svg x="-46" y="-46" width="92" height="92" ');
    s += '<g class="agente-mando' + (a.apagado ? " pronto" : "") + '" data-id="' + a.id + '" data-sector="' + DE[a.id] + '" transform="translate(' + p[0].toFixed(1) + ' ' + p[1].toFixed(1) + ')" tabindex="0" role="button" aria-label="' + a.nombre + ': ' + a.rol + '">' +
      '<circle class="aura" r="62" fill="' + col + '" opacity=".14"/>' + r +
      '<circle r="47" fill="none" stroke="' + col + '" stroke-width="3"/>' +
      '<text y="72" text-anchor="middle" font-family="Figtree, sans-serif" font-size="18" font-weight="600" fill="#f2f1f5">' + a.nombre + '</text>' +
      '<text y="92" text-anchor="middle" font-family="Figtree, sans-serif" font-size="12.5" fill="#a3a3ae">' + (a.funcion || "") + '</text></g>';
  });
  s += '<g class="agente-mando kiwi-mando" data-id="jefe" transform="translate(' + pk[0] + ' ' + (pk[1] + 8) + ')" tabindex="0" role="button" aria-label="Kiwi: pregúntale al cerebro">' +
    '<circle class="aura" r="58" fill="#9bd14e" opacity=".14"/><g transform="translate(-40 -112) scale(.9)">' + kiwiCuerpo("kmando") + '</g>' +
    '<text y="60" text-anchor="middle" font-family="Figtree, sans-serif" font-size="18" font-weight="600" fill="#f2f1f5">Kiwi</text>' +
    '<text y="80" text-anchor="middle" font-family="Figtree, sans-serif" font-size="12.5" fill="#a3a3ae">Pregúntale al cerebro</text></g>';
  // el hemiciclo de la Asamblea, dentro del sector legal
  var ph = pos(180, .66);
  s += '<g class="hemi-mando" data-sector="legal" transform="translate(' + ph[0] + ' ' + ph[1] + ')" tabindex="0" role="button" aria-label="Asamblea Nacional 2024-2029: ver los diputados">' +
    '<rect x="-70" y="-46" width="140" height="92" rx="14" fill="rgba(255,255,255,.04)" stroke="rgba(180,140,242,.35)"/><g class="puntos-hemi"></g>' +
    '<text y="36" text-anchor="middle" font-family="Figtree, sans-serif" font-size="11" fill="#a3a3ae">Asamblea 2024-2029</text></g>';

  oficina.classList.add("ilustrada", "mando");
  var capa = el("div", "escena-mando");
  capa.innerHTML = '<svg class="dibujo-mando" viewBox="0 0 ' + VW + ' ' + VH + '" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg"><g class="camara-mando">' + s + '</g></svg>';
  oficina.prepend(capa);
  var svg = capa.querySelector("svg"), camaraG = capa.querySelector(".camara-mando"), senales = capa.querySelector(".senales");
  var logo = el("img", "logo-mando"); logo.alt = "Keyword"; logo.src = (document.querySelector(".logo-para-oscuro") || {}).src || ""; capa.append(logo);

  // los avisos (números) van en HTML encima de cada retrato
  function enPct(x, y) { return [(x / VW * 100) + "%", (y / VH * 100) + "%"]; }
  AGENTES.forEach(function (a) {
    if (!(a.id in ANG)) return;
    var g = capa.querySelector('.agente-mando[data-id="' + a.id + '"]'), p = pos(ANG[a.id]), q = enPct(p[0] + 34, p[1] - 40);
    avisos[a.id] = el("span", "aviso-num aviso-mando"); avisos[a.id].style.left = q[0]; avisos[a.id].style.top = q[1];
    capa.append(avisos[a.id]); puestos[a.id] = g;
    g.addEventListener("click", function () { if (!a.apagado) abrirMesa(a.id); });
    g.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && !a.apagado) { e.preventDefault(); abrirMesa(a.id); } });
    var tip = el("title"); tip.textContent = a.que; g.prepend(tip);
  });
  var gk = capa.querySelector(".kiwi-mando");
  gk.addEventListener("click", function () { abrirChat(); });
  gk.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrirChat(); } });
  var gc = capa.querySelector(".cerebro-mando"); gc.addEventListener("click", abrirCerebro);
  var gh = capa.querySelector(".hemi-mando"); gh.addEventListener("click", function () { abrirMesa("hemiciclo"); });
  function pintarHemi() {
    if (!estado.actores.length) { setTimeout(pintarHemi, 1500); return; }
    var t = "";
    curules(0, 18, 22, 8).forEach(function (c) { t += '<circle cx="' + c.x.toFixed(1) + '" cy="' + c.y.toFixed(1) + '" r="2.7" fill="' + (c.dip ? colorPartido(c.dip.partido) : "#555") + '"/>'; });
    gh.querySelector(".puntos-hemi").innerHTML = t;
  }
  pintarHemi();

  // señales: cada agente manda cada tanto una señal al cerebro (más seguido si está trabajando); el cerebro destella
  var NS = "http://www.w3.org/2000/svg", guias = {};
  Object.keys(LINEA).forEach(function (id) { var p = document.createElementNS(NS, "path"); p.setAttribute("d", LINEA[id]); guias[id] = p; });
  function senal(id) {
    var g = guias[id], largo = g.getTotalLength(), c = document.createElementNS(NS, "circle"), t0 = performance.now(), dur = 1500;
    var col = id === "jefe" ? "#c9ee86" : SECTOR[DE[id]].color;
    c.setAttribute("r", "4.5"); c.setAttribute("fill", "#fff"); c.setAttribute("stroke", col); c.setAttribute("stroke-width", "2.5"); c.setAttribute("filter", "url(#m-brillo)");
    senales.append(c);
    (function paso(t) {
      var k = Math.min(1, (t - t0) / dur), pt = g.getPointAtLength(largo * (id === "jefe" ? 1 - k : k));
      c.setAttribute("cx", pt.x.toFixed(1)); c.setAttribute("cy", pt.y.toFixed(1));
      if (k < 1) requestAnimationFrame(paso);
      else { c.remove(); if (id !== "jefe") { gc.classList.remove("destello"); void gc.getBBox(); gc.classList.add("destello"); } }
    })(t0);
  }
  if (!reducir) AGENTES.forEach(function (a) {
    if (!(a.id in ANG) || a.apagado) return;
    (function ciclo() {
      var g = puestos[a.id], ocupado = g && g.classList.contains("trabaja");
      setTimeout(function () { if (!document.hidden) senal(a.id); ciclo(); }, ocupado ? 700 + Math.random() * 900 : 3500 + Math.random() * 6000);
    })();
  });
  if (!reducir) (function cicloKiwi() { setTimeout(function () { if (!document.hidden) senal("jefe"); cicloKiwi(); }, 6000 + Math.random() * 6000); })();

  // arriba: toda la oficina o una coordinación (se acerca a ella y se apagan las otras)
  var FOCO = { 3: [CX, CY, 1], 0: [CX - RX * .62, CY, 1.55], 1: [CX + RX * .62, CY, 1.55], 2: [CX, CY - RY * .62, 1.55] };
  var nombreArea = { 0: "legal", 1: "politica", 2: "economica" };
  function irA(i) {
    var f = FOCO[i];
    camaraG.style.transform = "translate(" + (VW / 2 - f[0] * f[2]) + "px," + (VH / 2 - f[1] * f[2]) + "px) scale(" + f[2] + ")";
    capa.dataset.foco = nombreArea[i] || "";
    marcarArea(i);
  }
  var nav = document.querySelector("nav.coordinaciones");
  nav.innerHTML = "";
  [[3, "Toda la oficina"], [0, "Coordinación legal"], [1, "Coordinación de inteligencia política"], [2, "Coordinación de inteligencia económica"]].forEach(function (b) {
    var n = el("button", null, b[1]); n.type = "button"; n.setAttribute("role", "tab"); n.dataset.coord = b[0];
    n.setAttribute("aria-selected", String(b[0] === 3)); n.addEventListener("click", function () { irA(b[0]); });
    nav.append(n);
  });
  capa.addEventListener("click", function (e) { if (e.target === svg || e.target.tagName === "rect") irA(3); });
  setTimeout(function () { irA(3); }, 30);
  fetch(api("/oficina/grafo")).then(function (r) { return r.json(); }).then(function (g) {
    var t = capa.querySelector("#cifras-cerebro");
    t.textContent = "El cerebro de Keyword · " + g.nodos.length.toLocaleString("es") + " puntos · " + g.lineas.length.toLocaleString("es") + " conexiones · tócalo para explorarlo";
  }).catch(function () {});

  function abrirCerebro() {
    var fondo = el("div", "velo-cerebro"), caja2 = el("div", "caja-cerebro"), cerrar = el("button", "cerrar-cerebro", "×");
    cerrar.type = "button"; cerrar.setAttribute("aria-label", "Cerrar el mapa");
    var marco = document.createElement("iframe"); marco.src = api("/oficina/mapa"); marco.title = "Mapa del cerebro";
    caja2.append(marco, cerrar); fondo.append(caja2); document.body.append(fondo);
    function fuera() { fondo.remove(); removeEventListener("keydown", tecla); }
    function tecla(e) { if (e.key === "Escape") fuera(); }
    cerrar.onclick = fuera; fondo.addEventListener("click", function (e) { if (e.target === fondo) fuera(); });
    addEventListener("keydown", tecla);
  }
  // la red de adentro: los puntos más conectados del mapa real, acomodados dentro de los hemisferios; se mueven suave
  // y cada tanto una señal recorre una línea (como una sinapsis)
  var COLORES = { persona: "#c77dff", institucion: "#7fb2ff", comision: "#d4bbff", partido: "#f2b35a", proyecto: "#5fd1a0", documento: "#8a8d96" };
  function conD3(fn) {
    if (window.d3) return fn();
    var sc = document.createElement("script"); sc.src = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"; sc.onload = fn; document.head.append(sc);
  }
  fetch(api("/oficina/grafo")).then(function (r) { return r.json(); }).then(function (g) { conD3(function () { pintarRed(g); }); }).catch(function () {});
  function pintarRed(g) {
    var NS = "http://www.w3.org/2000/svg", raiz = capa.querySelector("#red-cerebro");
    var nodos = g.nodos.slice().sort(function (a, b) { return b.grado - a.grado; }).slice(0, 260);
    var ids = {}; nodos.forEach(function (n) { ids[n.id] = n; n.r = 2.4 + Math.sqrt(n.grado) * .55; });
    var lineas = g.lineas.filter(function (l) { return ids[l.a] && ids[l.b]; }).map(function (l) { return { source: l.a, target: l.b }; });
    // izquierda: los actores (personas, comisiones, partidos); derecha: lo que hacen y dicen (documentos, proyectos, instituciones)
    var IZQ = { persona: 1, comision: 1, partido: 1 };
    nodos.forEach(function (n) { n.x = (IZQ[n.tipo] ? -100 : 100) + (Math.random() - .5) * 120; n.y = -10 + (Math.random() - .5) * 160; });
    var dentro = function (n) {  // dentro de su hemisferio (aprox.: una elipse por lado)
      var lado = IZQ[n.tipo] ? -1 : 1, ex = (n.x - lado * 100) / 92, ey = (n.y + 10) / 108, d = Math.hypot(ex, ey);
      if (d > 1) { n.x = lado * 100 + ex / d * 92; n.y = -10 + ey / d * 108; }
      if (lado * n.x < 8) n.x = lado * 8;
    };
    var sim = d3.forceSimulation(nodos).force("l", d3.forceLink(lineas).id(function (n) { return n.id; }).distance(30).strength(.04))
      .force("c", d3.forceManyBody().strength(-16).distanceMax(120)).force("k", d3.forceCollide().radius(function (n) { return n.r + 2; }))
      .force("x", d3.forceX(function (n) { return IZQ[n.tipo] ? -100 : 100; }).strength(.05)).force("y", d3.forceY(-10).strength(.05)).stop();
    for (var i = 0; i < 260; i++) { sim.tick(); nodos.forEach(dentro); }
    var gl = document.createElementNS(NS, "g"), gn = document.createElementNS(NS, "g"), gs = document.createElementNS(NS, "g");
    lineas.forEach(function (l) {
      var p = document.createElementNS(NS, "line"); p.setAttribute("stroke", "rgba(212,187,255,.16)"); p.setAttribute("stroke-width", ".7"); l.el = p; gl.append(p);
    });
    nodos.forEach(function (n) {
      n.bx = n.x; n.by = n.y; n.fase = Math.random() * 6.3; n.vel = .4 + Math.random() * .6;
      var c = document.createElementNS(NS, "circle"); c.setAttribute("r", n.r.toFixed(1)); c.setAttribute("fill", COLORES[n.tipo] || "#8a8d96"); n.el = c; gn.append(c);
    });
    raiz.append(gl, gn, gs);
    var senales = [];
    function cuadro(t) {
      t = t / 1000;
      nodos.forEach(function (n) { n.x = n.bx + Math.sin(t * n.vel + n.fase) * 2.2; n.y = n.by + Math.cos(t * n.vel * .8 + n.fase) * 1.8;
        n.el.setAttribute("cx", n.x.toFixed(1)); n.el.setAttribute("cy", n.y.toFixed(1)); });
      lineas.forEach(function (l) { l.el.setAttribute("x1", l.source.x.toFixed(1)); l.el.setAttribute("y1", l.source.y.toFixed(1));
        l.el.setAttribute("x2", l.target.x.toFixed(1)); l.el.setAttribute("y2", l.target.y.toFixed(1)); });
      if (lineas.length && Math.random() < .12 && senales.length < 10) {
        var c = document.createElementNS(NS, "circle"); c.setAttribute("r", "2.6"); c.setAttribute("fill", "#ffffff"); c.setAttribute("stroke", "#9500c5"); c.setAttribute("stroke-width", "1");
        gs.append(c); senales.push({ l: lineas[Math.floor(Math.random() * lineas.length)], t0: t, el: c });
      }
      senales = senales.filter(function (x) {
        var k = (t - x.t0) / .9; if (k >= 1) { x.el.remove(); return false; }
        x.el.setAttribute("cx", (x.l.source.x + (x.l.target.x - x.l.source.x) * k).toFixed(1));
        x.el.setAttribute("cy", (x.l.source.y + (x.l.target.y - x.l.source.y) * k).toFixed(1));
        return true;
      });
      if (!reducir) requestAnimationFrame(cuadro);
    }
    requestAnimationFrame(cuadro);
  }
  if (typeof pintarTodo === "function") pintarTodo();
})();
