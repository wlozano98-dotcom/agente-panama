/* ---------------------------------------------------------------- la oficina ISOMÉTRICA (VERSIÓN DE PRUEBA, 2026-10-26)
   Pedido de Andrés: un piso que se recorra "más 3D". Todo el piso visto en diagonal desde arriba, como una maqueta: al
   fondo la coordinación económica, a la izquierda la legal, a la derecha la política, al centro el cerebro (la forma
   ilustrada con los puntos reales del mapa adentro) y adelante la entrada, con el pórtico y el mostrador de Kiwi con
   el logo de Keyword. La cámara se mueve: arrastrar, pellizcar (o Ctrl + rueda), +/− y los botones de arriba, que
   la llevan a cada área. Las personas y la ciudad son las de la escena publicada (escena_nueva.js). Se sirve solo en
   la Mac (bot/prueba_local.py). */
(function escenaIso() {
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

  /* ---------- el piso en isométrica: un cuadrado de N x N metros visto en diagonal desde arriba
     Ejes: x hacia abajo a la derecha, y hacia abajo a la izquierda, z hacia arriba. Esquina de atrás (0,0): la
     económica; izquierda (0,N): la legal; derecha (N,0): la política; adelante (N,N): la entrada; al centro, el cerebro. */
  var U = 60, C30 = Math.cos(Math.PI / 6), N = 24, H = 4.2;
  function P(x, y, z) { return [(x - y) * C30 * U, (x + y) * .5 * U - (z || 0) * U]; }
  function pts(arr) { return arr.map(function (p) { var q = P(p[0], p[1], p[2]); return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" "); }
  function poly(arr, fill, extra) { return '<polygon points="' + pts(arr) + '" fill="' + fill + '"' + (extra || "") + '/>'; }
  // una caja: se ven la tapa, la cara de x1 (abajo a la derecha) y la de y1 (abajo a la izquierda)
  function caja(x0, x1, y0, y1, z0, z1, arriba, ladoX, ladoY) {
    return poly([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], arriba) +
      poly([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]], ladoX) +
      poly([[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]], ladoY);
  }
  // matrices para dibujar algo plano sobre el piso o sobre una pared (u hacia la derecha del plano, v hacia abajo)
  function enPiso(x, y, svg) { var o = P(x, y, 0); return '<g transform="matrix(' + C30 + ' .5 ' + (-C30) + ' .5 ' + o[0] + ' ' + o[1] + ')">' + svg + '</g>'; }
  function enParedY(x, z, svg) { var o = P(x, 0, z); return '<g transform="matrix(' + C30 + ' .5 0 1 ' + o[0] + ' ' + o[1] + ')">' + svg + '</g>'; }
  function enParedX(y, z, svg) { var o = P(0, y, z); return '<g transform="matrix(' + (-C30) + ' .5 0 1 ' + o[0] + ' ' + o[1] + ')">' + svg + '</g>'; }
  // de frente al que mira (plano vertical a lo largo de la diagonal): sirve para carteles que se leen derechos
  function deFrente(x, y, z, svg, s) { var o = P(x, y, z); return '<g transform="translate(' + o[0].toFixed(1) + ' ' + o[1].toFixed(1) + ') scale(' + (s || 1) + ')">' + svg + '</g>'; }

  var logoBlanco = (document.querySelector(".logo-para-oscuro") || {}).src || "", logoNegro = (document.querySelector(".logo-para-claro") || {}).src || "";
  var MIN = P(0, N, 0)[0] - 40, MAXX = P(N, 0, 0)[0] + 40, TOPE = P(0, 0, H)[1] - 40, FONDO = P(N, N, 0)[1] + 60;
  var W = MAXX - MIN, HH = FONDO - TOPE;
  var objetos = [];  // {d: profundidad (x + y del frente), s: svg}; se dibujan de atrás hacia adelante
  function poner(d, s) { objetos.push({ d: d, s: s }); }

  // el piso: madera clara con tablones, y una alfombra por coordinación con su nombre
  var piso = poly([[0, 0, 0], [N, 0, 0], [N, N, 0], [0, N, 0]], "#e6d6bf");
  for (var t = 1; t < N; t++) piso += '<polyline points="' + pts([[t, 0, 0], [t, N, 0]]) + '" stroke="rgba(150,115,75,.12)" stroke-width="2" fill="none"/>';
  function alfombra(x0, x1, y0, y1, color, nombre) {
    var r = poly([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]], color) +
      '<polyline points="' + pts([[x0 + .25, y0 + .25, 0], [x1 - .25, y0 + .25, 0], [x1 - .25, y1 - .25, 0], [x0 + .25, y1 - .25, 0], [x0 + .25, y0 + .25, 0]]) + '" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="3"/>';
    if (nombre) r += enPiso(x0 + .6, y1 - .5, '<text x="0" y="0" font-family="Figtree, sans-serif" font-size="26" font-weight="700" letter-spacing="3" fill="rgba(24,25,31,.42)">' + nombre + '</text>');
    return r;
  }
  piso += alfombra(.8, 9.2, 13.6, 23.2, "#e6dcf4", "COORDINACIÓN LEGAL");
  piso += alfombra(13.6, 23.2, .8, 9.6, "#dde8f2", "COORDINACIÓN POLÍTICA");
  piso += alfombra(.8, 8.4, .8, 8.4, "#dfeee3", "COORDINACIÓN ECONÓMICA");
  // la entrada: una alfombra azul marino por la diagonal, desde adelante hasta el cerebro
  var w = 1.35, k = Math.SQRT1_2;
  piso += poly([[16.2 + w * k, 16.2 - w * k, 0], [N + w * k, N - w * k, 0], [N - w * k, N + w * k, 0], [16.2 - w * k, 16.2 + w * k, 0]], "#2e3566") +
    '<polyline points="' + pts([[16.4 + (w - .2) * k, 16.4 - (w - .2) * k, 0], [N + (w - .2) * k, N - (w - .2) * k, 0]]) + '" stroke="#d4bbff" stroke-width="3" fill="none"/>' +
    '<polyline points="' + pts([[16.4 - (w - .2) * k, 16.4 + (w - .2) * k, 0], [N - (w - .2) * k, N + (w - .2) * k, 0]]) + '" stroke="#d4bbff" stroke-width="3" fill="none"/>';

  // las dos paredes de atrás, con ventanales a la ciudad y la pantalla del hemiciclo (en la legal)
  var paredes = poly([[0, 0, 0], [N, 0, 0], [N, 0, H], [0, 0, H]], "#efe8dd") + poly([[0, 0, 0], [0, N, 0], [0, N, H], [0, 0, H]], "#e4dacb") +
    poly([[0, -.35, H], [N, -.35, H], [N, 0, H], [0, 0, H]], "#d9ccb9") + poly([[-.35, 0, H], [-.35, N, H], [0, N, H], [0, 0, H]], "#cfc1ad") +
    poly([[0, 0, 0], [N, 0, 0], [N, 0, .25], [0, 0, .25]], "#d8c9b4") + poly([[0, 0, 0], [0, N, 0], [0, N, .25], [0, 0, .25]], "#cdbda6");
  function ventanalY(a, b, id, puente) { return enParedY(a, 3.7, ventanal(id, 0, 0, (b - a) * U, 2.7 * U, Math.max(2, Math.round((b - a) / 2.5)), puente)); }
  function ventanalX(a, b, id) { return enParedX(a, 3.7, ventanal(id, 0, 0, (b - a) * U, 2.7 * U, Math.max(2, Math.round((b - a) / 2.5)))); }
  paredes += ventanalY(1, 8.2, "iy1") + ventanalY(9.6, 23.2, "iy2", [300, 620]) + ventanalX(1, 8.2, "ix1") + ventanalX(9.6, 15.2, "ix2");
  paredes += enParedX(16.2, 3.6, '<rect x="0" y="0" width="' + (5.6 * U) + '" height="' + (2.3 * U) + '" rx="10" fill="#1d2027"/><g class="hemiciclo-iso"></g>');
  // letreros en la pared de cada coordinación
  paredes += enParedY(14.2, 4.05, '<text x="0" y="0" font-family="Figtree, sans-serif" font-size="22" font-weight="600" fill="#6b6e78">Inteligencia política</text>');
  paredes += enParedY(1.2, 4.05, '<text x="0" y="0" font-family="Figtree, sans-serif" font-size="22" font-weight="600" fill="#6b6e78">Inteligencia económica</text>');

  // cada puesto: la persona (de frente) y su escritorio delante; "y" = el escritorio a su derecha-abajo, "x" = a su izquierda-abajo
  var SITIO = {
    relatora: [2.6, 16, "y"], normativa: [2.6, 20.4, "y"], judicial: [6.4, 16, "y"], regulatoria: [6.4, 20.4, "y"],
    entrevistas: [15.8, 2.6, "x"], medios: [20.2, 2.6, "x"], perfilador: [18, 6.4, "x"], cifras: [4.4, 4.4, "y"],
  };
  var ESC = .52;
  function escritorio(px, py, o) {
    var e, mon;
    if (o === "y") { e = caja(px + .5, px + 1.3, py - 1.15, py + 1.15, 0, .74, "#f3eadb", "#d8c7ad", "#e6d8c2");
      mon = caja(px + .62, px + .72, py - .35, py + .35, .74, 1.3, "#c9ced6", "#b9c0ca", "#dfe3e9"); }
    else { e = caja(px - 1.15, px + 1.15, py + .5, py + 1.3, 0, .74, "#f3eadb", "#d8c7ad", "#e6d8c2");
      mon = caja(px - .35, px + .35, py + .62, py + .72, .74, 1.3, "#c9ced6", "#dfe3e9", "#b9c0ca"); }
    return e + mon;
  }
  AGENTES.forEach(function (a) {
    var s = SITIO[a.id]; if (!s) return;
    var base = s[2] === "y" ? P(s[0] + .45, s[1], .74) : P(s[0], s[1] + .45, .74);
    poner(s[0] + s[1], '<g transform="translate(' + base[0].toFixed(1) + ' ' + base[1].toFixed(1) + ') scale(' + ESC + ')">' + persona(a.id, a) + '</g>');
    poner(s[0] + s[1] + 1.4, escritorio(s[0], s[1], s[2]));
  });

  // al centro: el cerebro sobre una plataforma redonda (la red real adentro la pinta pintarRed)
  var FORMA = "M0 -128 C-34 -150 -104 -150 -136 -112 C-190 -104 -214 -46 -196 6 C-214 56 -168 112 -110 104 C-80 132 -28 128 0 104 " +
    "C28 128 80 132 110 104 C168 112 214 56 196 6 C214 -46 190 -104 136 -112 C104 -150 34 -150 0 -128Z";
  var cc = P(12, 12, 0), rx = 3.4 * U * C30 * Math.SQRT2, ry = 3.4 * U * .5 * Math.SQRT2;
  var cerebro = '<ellipse cx="' + cc[0] + '" cy="' + (cc[1] + 6) + '" rx="' + (rx + 10) + '" ry="' + (ry + 6) + '" fill="rgba(0,0,0,.07)"/>' +
    '<path d="M' + (cc[0] - rx) + ' ' + cc[1] + ' A' + rx + ' ' + ry + ' 0 0 0 ' + (cc[0] + rx) + ' ' + cc[1] + ' L' + (cc[0] + rx) + ' ' + (cc[1] - 22) + ' A' + rx + ' ' + ry + ' 0 0 1 ' + (cc[0] - rx) + ' ' + (cc[1] - 22) + 'Z" fill="#d9ccb9"/>' +
    '<ellipse cx="' + cc[0] + '" cy="' + (cc[1] - 22) + '" rx="' + rx + '" ry="' + ry + '" fill="#f6f1e8"/>' +
    '<ellipse cx="' + cc[0] + '" cy="' + (cc[1] - 22) + '" rx="' + (rx * .78) + '" ry="' + (ry * .78) + '" fill="none" stroke="#d4bbff" stroke-width="4"/>' +
    '<g transform="translate(' + cc[0] + ' ' + (cc[1] - 205) + ') scale(1.2)">' +
    '<ellipse cx="0" cy="0" rx="250" ry="185" fill="url(#halo-cerebro)" class="halo-cerebro"/>' +
    '<path d="M-14 100 Q0 140 14 100 L16 158 L-16 158Z" fill="#b48cf2"/>' +
    '<clipPath id="clip-cerebro"><path d="' + FORMA + '"/></clipPath>' +
    '<path d="' + FORMA + '" fill="rgba(212,187,255,.4)" stroke="#9500c5" stroke-width="3"/>' +
    '<g clip-path="url(#clip-cerebro)"><g id="red-cerebro"></g></g>' +
    '<path d="M0 -128 C-8 -60 8 0 0 104" fill="none" stroke="rgba(149,0,197,.45)" stroke-width="3"/>' +
    '<path d="M-150 -96 Q-90 -132 -30 -122" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="6" stroke-linecap="round"/></g>';
  poner(24.5, cerebro);

  // la recepción: el mostrador oscuro con el logo de Keyword en el frente y Kiwi detrás
  var kx = 20.4, ky = 15.6;
  var kb = P(kx, ky, .9);
  poner(kx + ky, '<g transform="translate(' + (kb[0] - 72).toFixed(1) + ' ' + (kb[1] - 150).toFixed(1) + ') scale(1.55)">' + kiwiCuerpo("kiso") + '</g>');
  var mostrador = caja(kx + .3, kx + 1.2, ky - 1.6, ky + 1.6, 0, 1.05, "#f3eee6", "#18191f", "#2a2c35") +
    poly([[kx + 1.2, ky - 1.6, .92], [kx + 1.2, ky + 1.6, .92], [kx + 1.2, ky + 1.6, 1.0], [kx + 1.2, ky - 1.6, 1.0]], "#9500c5");
  // el logo en la cara de adelante del mostrador (plano x = kx + 1.2), derecho al leer
  var o = P(kx + 1.2, ky - 1.2, .78);
  mostrador += '<g transform="matrix(' + (-C30) + ' .5 0 1 ' + o[0] + ' ' + o[1] + ')"><image href="' + logoBlanco + '" x="' + (-2.6 * U) + '" y="0" width="' + (2.3 * U) + '" height="' + (.55 * U) + '" preserveAspectRatio="xMidYMid meet" transform="scale(-1 1)"/></g>';
  poner(kx + ky + 2.2, mostrador);

  // la entrada: un pórtico con el logo de Keyword, adelante, sobre la alfombra
  var pa = [N - .2 + 2.1 * k, N - .2 - 2.1 * k], pb = [N - .2 - 2.1 * k, N - .2 + 2.1 * k];
  function pilar(x, y) { return caja(x - .25, x + .25, y - .25, y + .25, 0, 3.2, "#2a2c35", "#18191f", "#23252d"); }
  var dintel = poly([[pa[0], pa[1], 2.7], [pb[0], pb[1], 2.7], [pb[0], pb[1], 3.5], [pa[0], pa[1], 3.5]], "#18191f");
  var centroDintel = P((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, 3.1);
  dintel += '<rect x="' + (centroDintel[0] - 150) + '" y="' + (centroDintel[1] - 22) + '" width="300" height="44" rx="6" fill="#18191f"/>' +
    '<image href="' + logoBlanco + '" x="' + (centroDintel[0] - 120) + '" y="' + (centroDintel[1] - 17) + '" width="240" height="34" preserveAspectRatio="xMidYMid meet"/>' +
    '<rect x="' + (centroDintel[0] - 150) + '" y="' + (centroDintel[1] + 22) + '" width="300" height="5" fill="#9500c5"/>';
  poner(pa[0] + pa[1] + 1, pilar(pa[0], pa[1]) + pilar(pb[0], pb[1]) + dintel);

  // plantas en las esquinas
  function plantaIso(x, y, s) { var q = P(x, y, 0); return '<g transform="translate(' + q[0] + ' ' + q[1] + ') scale(' + (s || .55) + ')">' + planta(0, 0, 1) + '</g>'; }
  poner(1.6, plantaIso(.9, .9)); poner(N - 1, plantaIso(N - 1, .9)); poner(N - 1, plantaIso(.9, N - 1));
  poner(N + 6, plantaIso(N - 3.5, 13, .5)); poner(N + 6, plantaIso(13, N - 3.5, .5));

  objetos.sort(function (a, b) { return a.d - b.d; });
  var defs = '<defs>' +
    '<linearGradient id="g-cielo" x1="0" y1="0" x2="0" y2="1"><stop class="c1" offset="0"/><stop class="c2" offset="1"/></linearGradient>' +
    '<linearGradient id="monitor" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".55"/><stop offset="1" stop-color="#b9c0ca" stop-opacity=".35"/></linearGradient>' +
    '<radialGradient id="halo-cerebro"><stop offset="0" stop-color="#d4bbff" stop-opacity=".6"/><stop offset="1" stop-color="#d4bbff" stop-opacity="0"/></radialGradient>' +
    '</defs>';

  // la escena va dentro de un "mundo" del tamaño del dibujo; la cámara lo mueve y lo acerca
  oficina.classList.add("ilustrada", "iso");
  var capa = el("div", "escena-iso"), mundo = el("div", "mundo-iso"); capa.append(mundo); oficina.prepend(capa);
  mundo.style.width = W + "px"; mundo.style.height = HH + "px";
  mundo.innerHTML = '<svg class="dibujo2 dibujo-iso" viewBox="' + MIN + ' ' + TOPE + ' ' + W + ' ' + HH + '" width="' + W + '" height="' + HH + '" xmlns="http://www.w3.org/2000/svg">' +
    defs + paredes + piso + objetos.map(function (x) { return x.s; }).join("") + '</svg>';
  function enMundo(x, y, z) { var q = P(x, y, z); return [q[0] - MIN, q[1] - TOPE]; }
  function hora() { var h = horaPanama().h; capa.classList.toggle("es-noche", h < 6 || h >= 18); }
  hora(); setInterval(hora, 60000);

  // el hemiciclo en la pantalla de la legal (abre la Asamblea)
  var hemi = mundo.querySelector(".hemiciclo-iso");
  function pintarHemiciclo() {
    if (!estado.actores.length) { setTimeout(pintarHemiciclo, 1500); return; }
    var s = "";
    curules(5.6 * U / 2, 2.3 * U - 22, 46, 15).forEach(function (c) {
      s += '<circle cx="' + c.x.toFixed(1) + '" cy="' + c.y.toFixed(1) + '" r="5" fill="' + (c.dip ? colorPartido(c.dip.partido) : "#c3cad0") + '"/>';
    });
    var m = 5.6 * U / 2;  // la pared x = 0 se dibuja en espejo: el texto se vuelve a dar vuelta sobre su centro
    hemi.innerHTML = s + '<text x="' + m + '" y="' + (2.3 * U - 8) + '" text-anchor="middle" font-family="Figtree, sans-serif" font-size="11" fill="#e9e6f5" transform="translate(' + (2 * m) + ' 0) scale(-1 1)">Asamblea Nacional 2024-2029</text>';
  }
  pintarHemiciclo();
  var tocaHemi = el("button", "zona-iso"); tocaHemi.type = "button"; tocaHemi.setAttribute("aria-label", "Asamblea Nacional 2024-2029: ver los diputados");
  var h0 = enMundo(0, 21.8, 3.6), h1 = enMundo(0, 16.2, 1.3);
  tocaHemi.style.left = h0[0] + "px"; tocaHemi.style.top = h0[1] + "px"; tocaHemi.style.width = (h1[0] - h0[0]) + "px"; tocaHemi.style.height = (h1[1] - h0[1] + 40) + "px";
  tocaHemi.onclick = function () { abrirMesa("hemiciclo"); };
  mundo.append(tocaHemi);

  // tarjetas sobre cada persona; persona y tarjeta abren su mesa
  AGENTES.forEach(function (a) {
    var s = SITIO[a.id]; if (!s) return;
    var g = mundo.querySelector('.persona2[data-id="' + a.id + '"]');
    var p = s[2] === "y" ? enMundo(s[0] + .45, s[1], .74) : enMundo(s[0], s[1] + .45, .74);
    var t = el("button", "tarjeta2 tarjeta-iso" + (a.apagado ? " pronto" : "")); t.type = "button";
    t.style.left = p[0] + "px"; t.style.top = (p[1] - 222 * ESC - 6) + "px";
    var funcion = a.funcion || (a.placa || "").replace(a.nombre, "").replace(/^\s*·\s*/, "");
    var tx = el("span", "txt"); tx.append(el("b", null, a.nombre), el("small", null, funcion), el("span", "est", a.apagado ? "Próximamente" : "Activo"));
    avisos[a.id] = el("span", "aviso-num");
    t.append(el("span", "ico", ICONO[a.id] || a.nombre[0]), tx, avisos[a.id]);
    t.title = a.que; t.setAttribute("aria-label", a.nombre + ": " + a.rol);
    [g, t].forEach(function (n) {
      if (!n) return;
      n.addEventListener("mouseenter", function () { g.classList.add("mira"); });
      n.addEventListener("mouseleave", function () { g.classList.remove("mira"); });
      if (!a.apagado) n.addEventListener("click", function () { if (!camara.movio) abrirMesa(a.id); });
    });
    if (!a.apagado) setInterval(function () { g.classList.add("pausa"); setTimeout(function () { g.classList.remove("pausa"); }, 1600); }, 7000 + Math.random() * 6000);
    mundo.append(t); puestos[a.id] = t;
  });
  // el cerebro y Kiwi
  function tarjeta(x, y, ico, titulo, sub, fn, clase) {
    var t = el("button", "tarjeta2 tarjeta-iso " + (clase || "")); t.type = "button";
    t.style.left = x + "px"; t.style.top = y + "px";
    var tx = el("span", "txt"); tx.append(el("b", null, titulo), el("small", null, sub), el("span", "est", "Activo"));
    t.append(el("span", "ico", ico), tx); t.onclick = function () { if (!camara.movio) fn(); }; mundo.append(t); return t;
  }
  var pc = enMundo(12, 12, 0);
  tarjeta(pc[0] - 330, pc[1] + 20, "◉", "El cerebro de Keyword", "Memoria conectada · toca para explorarla", abrirCerebro, "tarjeta-cerebro");
  var zc = el("button", "zona-iso redonda"); zc.type = "button"; zc.setAttribute("aria-label", "Abrir el mapa del cerebro");
  zc.style.left = (pc[0] - 250) + "px"; zc.style.top = (pc[1] - 390) + "px"; zc.style.width = "500px"; zc.style.height = "360px";
  zc.onclick = function () { if (!camara.movio) abrirCerebro(); }; mundo.append(zc);
  var pk = enMundo(kx, ky, .9);
  tarjeta(pk[0], pk[1] - 150, "K", "Kiwi", "Recepción · pregúntame lo que quieras", function () { abrirChat(); });

  /* ---------- la cámara: arrastrar para moverse, pellizcar (o Ctrl + rueda) para acercarse, botones para ir a cada área */
  var camara = { k: 1, x: 0, y: 0, movio: false };
  function aplicar(suave) {
    mundo.style.transition = suave && !reducir ? "transform .7s cubic-bezier(.2,.8,.2,1)" : "none";
    mundo.style.transform = "translate(" + camara.x.toFixed(1) + "px," + camara.y.toFixed(1) + "px) scale(" + camara.k.toFixed(3) + ")";
    // las tarjetas: chicas y solo con el nombre en la vista general; completas al acercarse
    var cerca = camara.k / general();
    mundo.style.setProperty("--inv", (Math.max(.62, Math.min(1, cerca / 1.9)) / camara.k).toFixed(3));
    capa.classList.toggle("lejos", cerca < 1.6);
  }
  function general() { return Math.min(capa.clientWidth / W, capa.clientHeight / HH) * .98; }
  function mirar(x, y, z, zoom, suave) {
    var q = enMundo(x, y, z); camara.k = general() * zoom;
    camara.x = capa.clientWidth / 2 - q[0] * camara.k; camara.y = capa.clientHeight / 2 - q[1] * camara.k; aplicar(suave);
  }
  var LUGARES = { 3: [12.6, 12.6, 1.2, 1], 0: [4.6, 18.4, 1.2, 2.1], 1: [18.4, 4.6, 1.2, 2.1], 2: [4.6, 4.6, 1.2, 2.3] };
  function irA(i, suave) { var l = LUGARES[i]; mirar(l[0], l[1], l[2], l[3], suave); marcarArea(i); }
  var nav = document.querySelector("nav.coordinaciones");
  nav.innerHTML = "";
  [[3, "Entrada"], [0, "Coordinación legal"], [2, "Coordinación económica"], [1, "Coordinación de inteligencia política"]].forEach(function (b) {
    var n = el("button", null, b[1]); n.type = "button"; n.setAttribute("role", "tab"); n.dataset.coord = b[0];
    n.setAttribute("aria-selected", String(b[0] === 3));
    n.addEventListener("click", function () { irA(b[0], true); });
    nav.append(n);
  });
  var arr = null;
  capa.addEventListener("pointerdown", function (e) {
    if (e.button !== 0) return;
    arr = { x: e.clientX, y: e.clientY, cx: camara.x, cy: camara.y }; camara.movio = false;
  });
  addEventListener("pointermove", function (e) {
    if (!arr) return;
    var dx = e.clientX - arr.x, dy = e.clientY - arr.y;
    if (!camara.movio && Math.hypot(dx, dy) > 5) { camara.movio = true; capa.classList.add("arrastrando"); }
    if (camara.movio) { camara.x = arr.cx + dx; camara.y = arr.cy + dy; aplicar(false); }
  });
  addEventListener("pointerup", function () { if (!arr) return; arr = null; capa.classList.remove("arrastrando"); setTimeout(function () { camara.movio = false; }, 0); });
  capa.addEventListener("wheel", function (e) {
    if (!e.ctrlKey && !e.metaKey) return;  // la rueda sola sigue bajando la página; con Ctrl (o pellizcando) acerca
    e.preventDefault();
    var r = capa.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    var nk = Math.max(general() * .8, Math.min(general() * 4, camara.k * Math.exp(-e.deltaY * .01)));
    camara.x = mx - (mx - camara.x) * nk / camara.k; camara.y = my - (my - camara.y) * nk / camara.k; camara.k = nk; aplicar(false);
  }, { passive: false });
  var acercar = el("div", "zoom-iso");
  [["+", 1.35], ["−", 1 / 1.35]].forEach(function (b) {
    var n = el("button", null, b[0]); n.type = "button"; n.setAttribute("aria-label", b[1] > 1 ? "Acercar" : "Alejar");
    n.onclick = function () { var cx = capa.clientWidth / 2, cy = capa.clientHeight / 2, nk = Math.max(general() * .8, Math.min(general() * 4, camara.k * b[1]));
      camara.x = cx - (cx - camara.x) * nk / camara.k; camara.y = cy - (cy - camara.y) * nk / camara.k; camara.k = nk; aplicar(true); };
    acercar.append(n);
  });
  capa.append(acercar);
  addEventListener("resize", function () { irA(estado.area == null ? 3 : estado.area, false); });
  setTimeout(function () { irA(3, false); }, 50);

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
  var capaRed = mundo;
  // la red de adentro: los puntos más conectados del mapa real, acomodados dentro de los hemisferios; se mueven suave
  // y cada tanto una señal recorre una línea (como una sinapsis)
  var COLORES = { persona: "#9500c5", institucion: "#2e3566", comision: "#b48cf2", partido: "#e8a33d", proyecto: "#36a37e", documento: "#8a8d96" };
  function conD3(fn) {
    if (window.d3) return fn();
    var sc = document.createElement("script"); sc.src = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"; sc.onload = fn; document.head.append(sc);
  }
  fetch(api("/oficina/grafo")).then(function (r) { return r.json(); }).then(function (g) { conD3(function () { pintarRed(g); }); }).catch(function () {});
  function pintarRed(g) {
    var NS = "http://www.w3.org/2000/svg", raiz = capa.querySelector("#red-cerebro");
    var nodos = g.nodos.slice().sort(function (a, b) { return b.grado - a.grado; }).slice(0, 170);
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
      var p = document.createElementNS(NS, "line"); p.setAttribute("stroke", "rgba(46,53,102,.22)"); p.setAttribute("stroke-width", ".8"); l.el = p; gl.append(p);
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
  var retratoViejo = retrato;  // Kiwi y quien no esté en la escena conservan su dibujo
  retrato = function (a) {
    if (!LOOK[a.id]) return retratoViejo(a);
    var id = "recorte-" + a.id;
    return '<svg viewBox="-110 -250 220 220" aria-hidden="true"><defs><clipPath id="' + id + '"><circle cx="0" cy="-140" r="110"/></clipPath></defs>' +
      '<circle cx="0" cy="-140" r="110" fill="#efe4fb"/><g clip-path="url(#' + id + ')">' + persona(a.id, a).replace("persona2 trabaja", "persona2 retrato") + '</g></svg>';
  };
  if (typeof pintarTodo === "function") pintarTodo();
})();
