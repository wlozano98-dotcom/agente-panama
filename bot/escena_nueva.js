/* ---------------------------------------------------------------- escena dibujada (vista previa)
   La oficina en 2.5D, toda en SVG: un piso de tres coordinaciones (1536 x 1024 cada una; se ve la franja de 120 a
   920). Ventanal con la ciudad de Panamá, listones de madera, la pantalla con el hemiciclo (legal), una mesa larga y
   las personas en sus puestos, de frente, detrás de la mesa. Trabajan (miran su pantalla y teclean) y, al pasar el
   cursor, levantan la cabeza y sonríen. De noche cambian el cielo, la ciudad y la luz. */
(function escenaDibujada() {
  var ZW = 1536, ZH = 1024;
  // x: centro de la persona; m: borde de atrás de la mesa (ahí la tapa la mesa); s: escala
  var SITIOS = {
    relatora: { z: 0, x: 250, m: 700, s: 1.25 }, normativa: { z: 0, x: 600, m: 700, s: 1.25 },
    judicial: { z: 0, x: 950, m: 700, s: 1.25 }, regulatoria: { z: 0, x: 1300, m: 700, s: 1.25 },
    entrevistas: { z: 1, x: 330, m: 640, s: 1.08 }, medios: { z: 1, x: 768, m: 640, s: 1.08 }, perfilador: { z: 1, x: 1206, m: 640, s: 1.08 },
    cifras: { z: 2, x: 600, m: 650, s: 1.18 },
  };
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

  /* ---------- la mesa larga con sus puestos (pantallas de espaldas, plantas, lapiceros) */
  function mesa(x0, x1, m, puestos, s) {
    var f = m + 40 * s, abajo = m + 150 * s, r = "";
    r += '<path d="M' + x0 + ' ' + m + ' L' + x1 + ' ' + m + ' L' + (x1 + 34) + ' ' + f + ' L' + (x0 - 34) + ' ' + f + 'Z" fill="url(#mesa-sup)"/>';
    r += '<rect x="' + (x0 - 34) + '" y="' + f + '" width="' + (x1 - x0 + 68) + '" height="' + (14 * s) + '" fill="#d6c2a5"/>';
    r += '<rect x="' + (x0 - 26) + '" y="' + (f + 14 * s) + '" width="' + (x1 - x0 + 52) + '" height="' + (abajo - f - 14 * s) + '" fill="#2f3a4f"/>';
    // cajoneras de madera clara entre los puestos
    for (var i = 0; i <= puestos.length; i++) {
      var cx = i === 0 ? x0 + 30 : i === puestos.length ? x1 - 30 : (puestos[i - 1] + puestos[i]) / 2;
      r += '<rect x="' + (cx - 46 * s) + '" y="' + (f + 14 * s) + '" width="' + (92 * s) + '" height="' + (abajo - f - 14 * s) + '" fill="#ece1cf"/>' +
        '<path d="M' + (cx - 34 * s) + ' ' + (f + 46 * s) + ' H ' + (cx + 34 * s) + ' M' + (cx - 34 * s) + ' ' + (f + 80 * s) + ' H ' + (cx + 34 * s) + '" stroke="#cdbfa8" stroke-width="3"/>';
    }
    r += '<rect x="' + (x0 - 34) + '" y="' + abajo + '" width="' + (x1 - x0 + 68) + '" height="10" fill="rgba(0,0,0,.08)"/>';
    return r;
  }
  function puesto(x, m, s, lado) {
    // pantalla de espaldas a un lado de la persona, separador de vidrio, lapicero y plantita
    var mx = x + lado * 118 * s, r = "";
    r += '<g transform="translate(' + mx + ' ' + m + ') scale(' + (s * .72) + ')"><rect x="-6" y="-26" width="12" height="26" fill="#c9ced6"/><rect x="-30" y="-4" width="60" height="6" rx="3" fill="#c9ced6"/>' +
      '<rect x="-66" y="-112" width="132" height="88" rx="8" fill="#e6e9ee"/><rect x="-66" y="-112" width="132" height="88" rx="8" fill="url(#monitor)"/><circle cx="0" cy="-68" r="5" fill="#cfd4dc"/></g>';
    r += lapicero(x - lado * 96 * s, m + 4) + (lado > 0 ? plantita(x - 140 * s, m + 6) : "");
    return r;
  }

  /* ---------- cada coordinación */
  function zona(i, ventanas, extra) {
    var tx = i * ZW, r = '<g transform="translate(' + tx + ' 0)">';
    r += '<rect x="0" y="0" width="' + ZW + '" height="' + ZH + '" fill="url(#pared)"/>';
    r += '<rect x="0" y="0" width="' + ZW + '" height="150" fill="#f6f2ec"/><rect x="0" y="146" width="' + ZW + '" height="6" fill="#fff4d6"/><rect x="0" y="152" width="' + ZW + '" height="40" fill="url(#luz-techo)"/>';
    r += '<rect x="0" y="640" width="' + ZW + '" height="' + (ZH - 640) + '" fill="url(#piso)"/>';
    for (var k = 0; k < 14; k++) { var xx = -300 + k * 160; r += '<path d="M' + (ZW / 2 + (xx - ZW / 2) * .55) + ' 640 L' + xx + ' ' + ZH + '" stroke="rgba(120,90,60,.07)" stroke-width="2"/>'; }
    r += ventanas + extra + '</g>';
    return r;
  }
  var defs = '<defs>' +
    '<linearGradient id="pared" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4efe8"/><stop offset=".62" stop-color="#ece4d8"/><stop offset=".63" stop-color="#e9dfd1"/><stop offset="1" stop-color="#ddd0bf"/></linearGradient>' +
    '<linearGradient id="piso" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6d9c7"/><stop offset="1" stop-color="#d3c2ab"/></linearGradient>' +
    '<linearGradient id="luz-techo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff2c8" stop-opacity=".7"/><stop offset="1" stop-color="#fff2c8" stop-opacity="0"/></linearGradient>' +
    '<linearGradient id="mesa-sup" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f3e9da"/><stop offset="1" stop-color="#e7d8c2"/></linearGradient>' +
    '<linearGradient id="monitor" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".55"/><stop offset="1" stop-color="#b9c0ca" stop-opacity=".35"/></linearGradient>' +
    '<linearGradient id="sombra-listones" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".0"/><stop offset="1" stop-color="#000" stop-opacity=".12"/></linearGradient>' +
    '<linearGradient id="g-cielo" x1="0" y1="0" x2="0" y2="1"><stop class="c1" offset="0"/><stop class="c2" offset="1"/></linearGradient>' +
    '<linearGradient id="g-noche" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f1430" stop-opacity=".35"/><stop offset="1" stop-color="#0f1430" stop-opacity=".12"/></linearGradient>' +
    '<radialGradient id="lampara" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="#ffd58a" stop-opacity=".45"/><stop offset="1" stop-color="#ffd58a" stop-opacity="0"/></radialGradient>' +
    '</defs>';

  // legal: ventanal a la izquierda (con el Puente), listones, la pantalla del hemiciclo, mesa con cuatro puestos
  var legal = zona(0,
    ventanal("l", 40, 160, 470, 440, 3, [150, 470]) + listones(530, 112, 152, 488) + listones(1410, 126, 152, 488),
    '<rect x="642" y="590" width="768" height="60" fill="#e4d7c4"/><rect x="642" y="586" width="768" height="8" fill="#efe6d8"/>' +
    '<rect x="826" y="128" width="460" height="232" rx="14" fill="#1d2027"/><rect x="835" y="137" width="442" height="214" rx="9" fill="#262a33"/>' +
    planta(700, 560, 1.1) + planta(1470, 640, .95));
  var politica = zona(1,
    ventanal("p", 120, 160, 1300, 440, 5) + listones(10, 104, 152, 488) + listones(1430, 104, 152, 488), planta(70, 640, 1));
  var economica = zona(2,
    ventanal("e", 120, 160, 980, 440, 4) + listones(10, 104, 152, 488) + listones(1120, 104, 152, 488),
    '<rect x="1050" y="700" width="460" height="16" rx="8" fill="rgba(0,0,0,.06)"/>' +
    '<path d="M1160 640 h300 a26 26 0 0 1 26 26 v84 h-352 v-84 a26 26 0 0 1 26 -26z" fill="#e9e2d6"/><rect x="1150" y="700" width="350" height="60" rx="20" fill="#f2ece2"/>' +
    '<rect x="1180" y="652" width="70" height="52" rx="14" fill="#2f3a4f"/><rect x="1380" y="652" width="70" height="52" rx="14" fill="#d6c2a5"/>' +
    '<ellipse cx="1240" cy="840" rx="150" ry="26" fill="rgba(0,0,0,.05)"/><ellipse cx="1240" cy="800" rx="110" ry="20" fill="#3a3f49"/><ellipse cx="1240" cy="796" rx="110" ry="20" fill="#f0e8dc"/>' +
    planta(1500, 650, 1.05) + planta(70, 640, .95));
  // personas (detrás de la mesa) y mesas con sus puestos
  var gente = ["", "", ""], puestosXs = [[], [], []], m = [700, 640, 650], esc = [1.25, 1.08, 1.18];
  AGENTES.forEach(function (a) {
    var s = SITIOS[a.id]; if (!s) return;
    gente[s.z] += '<g transform="translate(' + (s.z * ZW + s.x) + ' ' + s.m + ') scale(' + s.s + ')">' + persona(a.id, a) + '</g>';
    puestosXs[s.z].push(s.x);
  });
  var mesas = "";
  [[60, 1480], [40, 1500], [90, 880]].forEach(function (r, z) {
    var xs = puestosXs[z].sort(function (a, b) { return a - b; }), tx = z * ZW, sz = esc[z];
    mesas += '<g transform="translate(' + tx + ' 0)">' + mesa(r[0], r[1], m[z], xs, sz);
    xs.forEach(function (x, i) { mesas += puesto(x, m[z], sz, i % 2 ? -1 : 1); });
    mesas += '</g>';
  });
  // primer plano: una planta en la esquina (nítida) y la luz de noche
  var adelante = planta(40, 1010, 1.9, true) + planta(ZW * 2 - 30, 1010, 1.7, true) + planta(ZW * 3 - 40, 1010, 1.8, true) +
    '<rect class="capa-noche" x="0" y="0" width="' + (3 * ZW) + '" height="' + ZH + '" fill="url(#g-noche)"/>';

  oficina.classList.add("ilustrada", "dibujada");
  var capa = el("div", "escena-ilustrada"); oficina.prepend(capa);
  capa.innerHTML = '<svg class="dibujo2" viewBox="0 0 ' + (3 * ZW) + ' ' + ZH + '" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">' +
    defs + legal + politica + economica + gente.join("") + mesas + adelante + '</svg>';
  function hora() { var h = horaPanama().h; capa.classList.toggle("es-noche", h < 6 || h >= 18); }
  hora(); setInterval(hora, 60000);

  // la pantalla de la pared: el hemiciclo 2024-2029 (abre la Asamblea)
  var pantalla = el("button", "pantalla-hemiciclo"); pantalla.type = "button"; pantalla.setAttribute("aria-label", "Asamblea Nacional 2024-2029: ver los diputados");
  pantalla.style.left = px(0, 835); pantalla.style.top = py(137); pantalla.style.width = ((442 / (3 * ZW)) * 100) + "%"; pantalla.style.height = py(214);
  pantalla.onclick = function () { abrirMesa("hemiciclo"); };
  capa.append(pantalla);
  function pintarPantalla() {
    if (!estado.actores.length) { setTimeout(pintarPantalla, 1500); return; }
    var NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 420 240");
    curules(210, 212, 88, 28).forEach(function (c) {
      var n = document.createElementNS(NS, "circle"); n.setAttribute("cx", c.x.toFixed(1)); n.setAttribute("cy", c.y.toFixed(1)); n.setAttribute("r", 8);
      n.setAttribute("fill", c.dip ? colorPartido(c.dip.partido) : "#c3cad0"); svg.append(n);
    });
    var t = document.createElementNS(NS, "text"); t.setAttribute("x", 210); t.setAttribute("y", 234); t.setAttribute("text-anchor", "middle");
    t.setAttribute("fill", "#e9e6f5"); t.setAttribute("font-size", "13"); t.setAttribute("font-family", "Figtree, sans-serif"); t.textContent = "Asamblea Nacional 2024-2029";
    svg.append(t); pantalla.replaceChildren(svg);
  }
  pintarPantalla();

  // tarjetas sobre cada persona; persona y tarjeta abren la mesa; al pasar el cursor, la persona mira y sonríe
  AGENTES.forEach(function (a) {
    var s = SITIOS[a.id]; if (!s) return;
    var g = capa.querySelector('.persona2[data-id="' + a.id + '"]');
    var t = el("button", "tarjeta2" + (a.apagado ? " pronto" : "")); t.type = "button";
    t.style.left = px(s.z, s.x); t.style.top = "calc(" + py(s.m - 222 * s.s) + " - 12px)";
    // el nombre de la persona y, abajo, lo que hace
    var funcion = a.funcion || (a.placa || "").replace(a.nombre, "").replace(/^\s*·\s*/, "").replace(" · pronto", "").replace("pronto", "");
    var tx = el("span", "txt"); tx.append(el("b", null, a.nombre), el("small", null, funcion), el("span", "est", a.apagado ? "Próximamente" : "Activo"));
    avisos[a.id] = el("span", "aviso-num");
    t.append(el("span", "ico", ICONO[a.id] || a.nombre[0]), tx, avisos[a.id]);
    t.title = a.que; t.setAttribute("aria-label", a.nombre + ": " + a.rol);
    [g, t].forEach(function (n) {
      n.addEventListener("mouseenter", function () { g.classList.add("mira"); });
      n.addEventListener("mouseleave", function () { g.classList.remove("mira"); });
      if (!a.apagado) n.addEventListener("click", function () { abrirMesa(a.id); });
    });
    // cada tanto levanta la vista un momento, como quien trabaja
    if (!a.apagado) setInterval(function () { g.classList.add("pausa"); setTimeout(function () { g.classList.remove("pausa"); }, 1600); }, 7000 + Math.random() * 6000);
    capa.append(t); puestos[a.id] = t;
  });
  var retratoViejo = retrato;  // Kiwi y quien no esté en la escena conservan su dibujo
  retrato = function (a) {
    if (!LOOK[a.id]) return retratoViejo(a);
    var id = "recorte-" + a.id;
    return '<svg viewBox="-110 -250 220 220" aria-hidden="true"><defs><clipPath id="' + id + '"><circle cx="0" cy="-140" r="110"/></clipPath></defs>' +
      '<circle cx="0" cy="-140" r="110" fill="#efe4fb"/><g clip-path="url(#' + id + ')">' + persona(a.id, a).replace("persona2 trabaja", "persona2 retrato") + '</g></svg>';
  };
  if (typeof pintarTodo === "function") pintarTodo();
})();
