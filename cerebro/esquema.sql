-- El cerebro: tablas comunes a todas las áreas (legislativo, normativo, político, económico).
-- Convive con las tablas del monitor legislativo (proyectos, eventos, impactos, proponentes, agenda) en la misma D1.

-- Actores, instituciones, comisiones, partidos, medios, temas, sectores e instrumentos (leyes, decretos, fallos...).
-- id legible y estable: "persona:jose-raul-mulino-quintero", "institucion:mef", "comision:economia-y-finanzas".
CREATE TABLE IF NOT EXISTS entidades (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,               -- persona, institucion, comision, partido, medio, tema, sector, instrumento
  subtipo TEXT,                     -- diputado, suplente, ministro, viceministro, autoridad, gremio...
  nombre TEXT NOT NULL,
  cargo TEXT,                       -- cargo actual en una línea
  datos TEXT,                       -- JSON: partido, circuito, comisiones, suplente, redes, fuentes...
  perfil TEXT,                      -- mini perfil (de la investigación o del Perfilador)
  fuente TEXT,
  actualizado TEXT
);
CREATE INDEX IF NOT EXISTS entidades_tipo ON entidades(tipo, subtipo);

-- Formas de nombrar a cada entidad (sin tildes, en mayúsculas): las usa el enlazador para encontrarlas en los textos.
CREATE TABLE IF NOT EXISTS alias (
  alias TEXT NOT NULL,
  entidad TEXT NOT NULL REFERENCES entidades(id),
  PRIMARY KEY (alias, entidad)
);
CREATE INDEX IF NOT EXISTS alias_entidad ON alias(entidad);

-- Todo lo que entra: ficha, norma de Gaceta, nota de prensa, transcripción, cifra... El texto completo va en fragmentos.
CREATE TABLE IF NOT EXISTS documentos (
  id TEXT PRIMARY KEY,              -- huella de fuente + id de origen (no se duplica)
  fuente TEXT NOT NULL,             -- seglegis, gaceta, asamblea_noticias, youtube_asamblea, inec...
  tipo TEXT,                        -- ley, decreto, resolucion, nota, transcripcion, cifra, investigacion...
  titulo TEXT,
  url TEXT,
  fecha TEXT,                       -- AAAA-MM-DD del hecho o de la publicación
  resumen TEXT,
  largo INTEGER,                    -- caracteres del texto completo
  estado TEXT DEFAULT 'nuevo',      -- nuevo → enlazado
  creado TEXT
);
CREATE INDEX IF NOT EXISTS documentos_fecha ON documentos(fecha);
CREATE INDEX IF NOT EXISTS documentos_estado ON documentos(estado);
CREATE INDEX IF NOT EXISTS documentos_fuente ON documentos(fuente, fecha);

-- Texto en trozos con búsqueda de texto completo (sin tildes: "pension*" encuentra "pensiones").
CREATE VIRTUAL TABLE IF NOT EXISTS fragmentos USING fts5(
  documento UNINDEXED, n UNINDEXED, texto, tokenize = 'unicode61 remove_diacritics 2'
);

-- Qué entidades aparecen en qué documento (las crea el enlazador).
CREATE TABLE IF NOT EXISTS menciones (
  documento TEXT NOT NULL REFERENCES documentos(id),
  entidad TEXT NOT NULL REFERENCES entidades(id),
  veces INTEGER DEFAULT 1,
  cita TEXT,                        -- un trozo donde aparece
  PRIMARY KEY (documento, entidad)
);
CREATE INDEX IF NOT EXISTS menciones_entidad ON menciones(entidad);

-- Relaciones con respaldo: "X presentó el proyecto 569", "X integra la comisión Y", "el decreto Z reglamenta la ley W".
CREATE TABLE IF NOT EXISTS relaciones (
  origen TEXT NOT NULL REFERENCES entidades(id),
  tipo TEXT NOT NULL,               -- integra, preside, pertenece_a, presento, habla_de, reglamenta...
  destino TEXT NOT NULL REFERENCES entidades(id),
  documento TEXT,                   -- de dónde sale (vacío si es del directorio)
  fecha TEXT,
  detalle TEXT,
  PRIMARY KEY (origen, tipo, destino)
);
CREATE INDEX IF NOT EXISTS relaciones_destino ON relaciones(destino, tipo);

-- Lo que dice cada actor (entrevistas, sesiones, notas): alimenta su ficha. Lo llena el Perfilador.
CREATE TABLE IF NOT EXISTS declaraciones (
  id TEXT PRIMARY KEY,              -- huella de documento + actor + cita
  entidad TEXT NOT NULL REFERENCES entidades(id),
  documento TEXT NOT NULL REFERENCES documentos(id),
  fecha TEXT,
  tema TEXT,
  cita TEXT NOT NULL,               -- textual
  postura TEXT,                     -- a favor, en contra, matiza, informa
  creado TEXT
);
CREATE INDEX IF NOT EXISTS declaraciones_entidad ON declaraciones(entidad, fecha);

-- Expediente vivo de cada entidad: lo que hay que saber hoy, con fuentes. Se reescribe cuando hay novedades.
CREATE TABLE IF NOT EXISTS expedientes (
  entidad TEXT PRIMARY KEY REFERENCES entidades(id),
  contenido TEXT,                   -- JSON con las secciones (estudios, experiencia, datos de interés, posturas...)
  fuentes TEXT,                     -- JSON: ids de documentos usados
  actualizado TEXT
);

-- Productos Keyword (Keyperfil, Keylaw, Keymonitor...): borrador → aprobado (Editora) → enviado.
CREATE TABLE IF NOT EXISTS productos (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,               -- keyperfil, keymapeo, keylaw, keymonitor, keyeconomics...
  titulo TEXT,
  entidad TEXT,
  contenido TEXT,                   -- JSON o texto del producto
  archivo TEXT,                     -- PDF o enlace de Drive
  estado TEXT DEFAULT 'borrador',
  agente TEXT,
  fuentes TEXT,
  creado TEXT,
  actualizado TEXT
);
CREATE INDEX IF NOT EXISTS productos_estado ON productos(estado, tipo);

-- Turnos: qué tiene pendiente cada agente.
CREATE TABLE IF NOT EXISTS tareas (
  id TEXT PRIMARY KEY,
  agente TEXT NOT NULL,
  tipo TEXT NOT NULL,
  ref TEXT,                         -- documento, entidad o producto
  estado TEXT DEFAULT 'pendiente',  -- pendiente, hecha, error
  detalle TEXT,
  creado TEXT,
  hecho TEXT
);
CREATE INDEX IF NOT EXISTS tareas_agente ON tareas(agente, estado);

-- Cada norma publicada en una edición de la Gaceta Oficial (la Analista normativa, cerebro/normativa.py).
CREATE TABLE IF NOT EXISTS normas (
  id TEXT PRIMARY KEY,              -- huella de edición + tipo + número + entidad
  gaceta TEXT NOT NULL,             -- documento de la edición (documentos.id)
  edicion TEXT,                     -- "30641-A"
  fecha TEXT,
  entidad TEXT,                     -- quién la emite, como aparece en la Gaceta
  tipo TEXT,                        -- ley, decreto ejecutivo, resolución, acuerdo, fallo, aviso...
  numero TEXT,
  titulo TEXT,
  resumen TEXT,
  sectores TEXT,                    -- JSON
  impacto TEXT,                     -- alto, medio, bajo, ninguno
  paginas TEXT,
  producto TEXT,                    -- Keymonitor (productos.id) si se escribió
  creado TEXT,
  nombre TEXT,                      -- nombre corto para el archivo ("Plan Nacional de Vivienda")
  archivo TEXT,                     -- nombre del PDF de la norma (AAMMDD + nombre, formato Keyword)
  pdf TEXT                          -- enlace de Drive al PDF de la norma
);
CREATE INDEX IF NOT EXISTS normas_gaceta ON normas(gaceta);
CREATE INDEX IF NOT EXISTS normas_fecha ON normas(fecha, impacto);

-- Decisiones humanas tomadas en la oficina: "agenda:<id>" → keylaw | guardar; "gaceta:<documento>" → revisada.
CREATE TABLE IF NOT EXISTS decisiones (
  ref TEXT PRIMARY KEY,
  decision TEXT,
  creado TEXT
);

-- Gacetas subidas a mano desde la oficina, en trozos base64 (la Mac las arma y las borra).
CREATE TABLE IF NOT EXISTS subidas (
  id TEXT NOT NULL,
  n INTEGER NOT NULL,
  datos TEXT NOT NULL,
  PRIMARY KEY (id, n)
);

-- Entes Reguladores (cerebro/reguladores.py): resoluciones, acuerdos, avisos y consultas públicas.
CREATE TABLE IF NOT EXISTS regulatorias (
  id TEXT PRIMARY KEY,
  fuente TEXT,                      -- asep, superseguros, smv, superbancos, dgnti
  ente TEXT,
  tipo TEXT,                        -- resolucion, acuerdo, aviso, consulta
  titulo TEXT,
  nombre TEXT,                      -- nombre corto
  descripcion TEXT,
  url TEXT,
  fecha TEXT,
  resumen TEXT,
  sectores TEXT,
  impacto TEXT,                     -- alto, medio, bajo, ninguno; "base" = visto la primera vez, sin analizar
  plazo TEXT,                       -- consultas: fecha límite de comentarios
  producto TEXT,                    -- Keymonitor (productos.id) si se escribió
  documento TEXT,
  creado TEXT
);
CREATE INDEX IF NOT EXISTS regulatorias_fecha ON regulatorias(fecha);

-- Órgano Judicial (cerebro/judicial.py): notas y comunicados sobre lo que resuelve la Corte.
CREATE TABLE IF NOT EXISTS judiciales (
  id TEXT PRIMARY KEY,
  canal TEXT,                       -- prensa, comunicado, edicto
  fuente TEXT,                      -- TVN, La Prensa, Telemetro, Órgano Judicial
  titulo TEXT,
  descripcion TEXT,
  url TEXT,
  fecha TEXT,
  es_decision INTEGER,              -- 1 si informa una decisión ya tomada
  tribunal TEXT,
  proceso TEXT,
  nombre TEXT,
  resumen TEXT,
  sectores TEXT,
  impacto TEXT,
  producto TEXT,
  documento TEXT,
  creado TEXT
);
