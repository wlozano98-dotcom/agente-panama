-- Base de datos del Agente Panamá (Cloudflare D1, SQLite).
-- Todas las fichas del Seguimiento Legislativo; las "en seguimiento" (analizadas con impacto) van a la matriz.

CREATE TABLE IF NOT EXISTS proyectos (
  ficha INTEGER PRIMARY KEY,        -- identificador único del Seguimiento Legislativo
  proyecto TEXT,                    -- número de proyecto (vacío si sigue siendo anteproyecto)
  anteproyecto TEXT,                -- número de anteproyecto (se reinicia cada legislatura)
  titulo_oficial TEXT NOT NULL,     -- tal cual lo publica la Asamblea (mayúsculas)
  titulo TEXT,                      -- legible, con tildes (del análisis)
  titulo_corto TEXT,
  fecha_presentacion TEXT,          -- AAAA-MM-DD
  proponente TEXT,
  comision TEXT,
  etapa TEXT,
  tiene_pdf INTEGER DEFAULT 0,
  -- lo nuestro
  analizado TEXT,                   -- fecha del análisis (vacío: aún no)
  impacto TEXT,                     -- alto, medio, bajo, ninguno
  sectores TEXT,
  clientes TEXT,
  resumen TEXT,
  razon TEXT,
  disposiciones TEXT,               -- JSON
  carpeta_url TEXT,
  en_seguimiento INTEGER DEFAULT 0, -- 1: está en la matriz
  descartada INTEGER DEFAULT 0,     -- 1: el equipo la borró de la matriz (no vuelve sola)
  notas TEXT,                       -- del equipo (columna Notas de la matriz)
  actualizado TEXT
);
CREATE INDEX IF NOT EXISTS proyectos_seguimiento ON proyectos(en_seguimiento);
CREATE INDEX IF NOT EXISTS proyectos_comision ON proyectos(comision);
CREATE INDEX IF NOT EXISTS proyectos_etapa ON proyectos(etapa);

-- Bitácora: historial de etapas de cada ficha (y lo que se sume después: orden del día, Gaceta...).
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY,
  ficha INTEGER NOT NULL REFERENCES proyectos(ficha),
  fecha TEXT NOT NULL,              -- AAAA-MM-DD
  etapa TEXT,
  texto TEXT,
  fuente TEXT,                      -- seglegis, orden_del_dia, gaceta...
  id_origen TEXT UNIQUE,            -- evita cargar dos veces lo mismo
  creado TEXT
);
CREATE INDEX IF NOT EXISTS eventos_ficha ON eventos(ficha, fecha);
CREATE INDEX IF NOT EXISTS eventos_fecha ON eventos(fecha);

-- Impacto por sector (lo da Gemini; el impacto general de la ficha es el máximo).
CREATE TABLE IF NOT EXISTS impactos (
  ficha INTEGER NOT NULL REFERENCES proyectos(ficha),
  sector TEXT NOT NULL,
  nivel TEXT NOT NULL,
  razon TEXT,
  actualizado TEXT,
  PRIMARY KEY (ficha, sector)
);
CREATE INDEX IF NOT EXISTS impactos_sector ON impactos(sector, nivel);

-- Proponentes de cada ficha, uno por fila (en Panamá es común que varios diputados presenten juntos).
-- Nombres unificados en su forma más completa (nombres.py); principal = 1 para el primero de la lista oficial.
CREATE TABLE IF NOT EXISTS proponentes (
  ficha INTEGER NOT NULL REFERENCES proyectos(ficha),
  nombre TEXT NOT NULL,
  tipo TEXT,                        -- Diputado, Suplente, Institución, Ciudadano
  principal INTEGER DEFAULT 0,
  orden INTEGER,
  PRIMARY KEY (ficha, nombre)
);
CREATE INDEX IF NOT EXISTS proponentes_nombre ON proponentes(nombre);
