# Agente Panamá — monitor legislativo de Keyword para la Asamblea Nacional de Panamá

Versión para la oficina de Panamá de KeyCurul (Ecuador, `../Agente Zimbra AN`, repo `wlozano98-dotcom/agente-asamblea`).
Proyecto APARTE (decisión de Andrés, 2026-10-08): cuentas, repo, base, bot y oficina propios. Se copia de KeyCurul lo que
sirva, pero no se comparte código ni datos. Alcance: todo lo de KeyCurul (alertas, matriz, D1, oficina con Kiwi, bot).

## Reglas

- Solo información PÚBLICA: no hay correo de la Asamblea ni reportes tipo Keylaw del equipo de Panamá.
- Los nombres de clientes nunca se envían a Gemini: Gemini marca sectores y el cruce con clientes es local.
- Sectores: los mismos 13 de Ecuador (clientes de Panamá se agregan después).
- Claves solo en `.env` (no se sube). Si una clave pasa por el chat, anotarla para rotarla.
- **Investigación = ChatGPT de la oficina** (regla de Andrés, 2026-10-24): toda investigación de fondo (fuentes, actores,
  medios, derecho, calendarios) la hace ChatGPT con un prompt que Claude prepara; Andrés deja los informes en
  `Invesitgacion/`. Claude no gasta en investigar: solo verifica técnicamente (endpoints, formatos) y programa.
- `ejemplos/` (productos internos de Keyword, algunos con nombres de clientes) e `Invesitgacion/` no se suben: el repo
  es público.
- La web de la Gaceta tiene anti-bots: no se esquivan. Se usa Legispan o una vía oficial.
- Plan completo del second brain en `PLAN.md`. Sistema de diseño de Keyword: local, fuera del repo, ruta en
  KEYWORD_DISENO (.env); guía A4 en `Manual de marca oficial/08-claude/keyword-documentos-a4.md`.
- NUNCA escribir nombres de clientes en el repo (es público): ni en código, ni en rutas, ni en notas.

## Cuentas (todas de agentemonitoreopa@gmail.com salvo GitHub)

- Google Cloud: proyecto `agente-panama`, APIs de Drive y Sheets, app OAuth "Agente Panama" En producción (página y
  política apuntan a este repo, `PRIVACIDAD.md`; dominio autorizado github.com), cliente de escritorio en
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET. DRIVE_TOKEN (scope `drive`, sirve también para Sheets) lo genera
  `python3 conectar_drive.py` (lo corre Andrés con `!`).
- Gemini: GEMINI_KEY del proyecto agente-panama, nivel gratuito.
- Cloudflare: cuenta propia (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_TOKEN con D1 Edit, Workers Scripts Edit y Account
  Settings Read), subdominio `agentemonitoreopa.workers.dev`.
- Telegram: bot `@keyword_panama_alertas_bot` ("Monitoreo AN Panamá"), TELEGRAM_CHAT_ID = chat de Andrés.
- GitHub: repo PÚBLICO `wlozano98-dotcom/agente-panama` (decisión de Andrés, 2026-10-08: los repos públicos no gastan
  minutos de Actions; KeyCurul ya usa más de los 2.000 gratis). Nada privado en el repo: claves en secretos y la lista de
  clientes, cuando exista, irá como secreto CLIENTES_JSON, no como archivo (GH_TOKEN de la cuenta de Andrés, el mismo de KeyCurul).
- `bin/` (no se sube): `rclone` y `gh` para macOS arm64.

## Fuentes (revisadas el 2026-10-08)

- **Seguimiento Legislativo** (fuente principal, sin anti-bots):
  https://sistemas.asamblea.gob.pa/segLegis/viewsPublico/SeguimientoLegislativo — ASP.NET WebForms. POST con los campos
  ocultos + `btnMostrarTodo` lista todo, 20 por página, más nuevos primero. Columnas: fecha de presentación, Ficha (id
  único), Proyecto, Anteproyecto, Título, Etapa, Proponente. 931 fichas (período desde 02-07-2024), 47 páginas, ~2 min
  completo: cada revisión puede leerlo todo. Paginación `__EVENTTARGET=dataTable`, `__EVENTARGUMENT=Page$N`, solo páginas
  visibles en el paginador (Page$Last y saltos largos dan 500). "Ver etapas" (Button3) = historial de etapas con fecha
  y comentario. PDF: https://sistemas.asamblea.gob.pa/segLegis/Documents/<ficha>.pdf.
  Etapas vistas: Preliminar, Prohijado, Enviado a subcomisión para analisis, Primer/Segundo/Tercer Debate,
  Segundo/Tercer Debate(Objetado), Enviado al Ejecutivo, Objetado por Ejecutivo, Ley, Archivado, Retirado por
  proponente, Fusionado, Negado, Suspendido, En Corte Sup. de Justicia.
- **Legispan** (Gaceta y normas, sin anti-bots): API JSON https://legispan.asamblea.gob.pa/api/search/norm (texto
  completo, gaceta, fecha y `procedureNumber` p. ej. `2025_P_0287`, que une la ley con su proyecto).
  Tiene 57.567 normas de muchas entidades (`?page=N&limit=100&q=<texto>`; campos authority, content, gazetteId,
  number, type, publishedAt, title, normUrl; no acepta orden ni filtro por fecha). OJO, NO es espejo de la Gaceta
  (medido 2026-10-24): trae 0-3 normas por edición, aun meses después (la 30641 del 23/10 solo tiene la ley; la 30639
  y la 30640, nada). Sirve para leyes y como índice, no para leer la Gaceta completa. La web de la Gaceta tiene
  anti-bots Incapsula (no se esquiva); Infojurídica no respondió. Vía pendiente: canal oficial (prompt E a ChatGPT),
  pedir acceso formal o que alguien de la oficina baje las ediciones a una carpeta.
- **Ritmo de la Gaceta** (medido 2026-10-24 con los números de Legispan): una edición numerada por día hábil (lunes a
  viernes, 30637 el lunes 19/10 → 30641 el viernes 23/10) más suplementos con letra el mismo día (A, B, C, D, E:
  hasta ~6 ediciones diarias). Sin ediciones en fin de semana.
- **Orden del Día del Pleno**: https://www.asamblea.gob.pa/Page/LABORLEGISLATIVA/OrdenDelDia, PDF por sesión en
  /Uploads/OrdenDia/<id>/…pdf (~175 puntos). Lo lee prensa.py (navegador + pypdf): la sesión entra a la agenda como "Pleno
  de la Asamblea" (id 10.000.000 + id; filas grandes, se insertan de a una) y a la bitácora solo cuando un proyecto entra
  al Orden del Día o cambia de debate. Telegram avisa cada Orden del Día y TODAS las sesiones nuevas de comisión.
- **Noticias y Agenda de Comisiones** (www.asamblea.gob.pa, anti-bots F5: solo con navegador): las lee `prensa.py` (la
  Cronista) con Playwright. APIs JSON desde la misma página: GET /Data/Noticias/Client/0/List?page=N&pageSize=30 (+ texto en
  /Noticias/Noticias/<slug>) y POST /Data/Agenda/List/0 (DataTables; ordenar desc por la columna 4). OJO: la Agenda NO está
  abandonada; la tabla viene ordenada de la más vieja a la más nueva. Cruce con fichas por número ("proyecto de Ley 569",
  "Anteproyectos de Ley: 154 «…», 148 «…»") confirmado con las palabras del título que acompaña al número (la prensa
  llama "proyecto" a anteproyectos). Notas → tabla eventos (fuente noticia, con url); agenda → tablas agenda y
  agenda_fichas. Telegram: nota o sesión nueva sobre ficha de impacto alto/medio. Paso propio en el workflow
  (continue-on-error).
- **Agenda publicada en X** (2026-10-27, `cerebro/agenda_x.py`): @asambleapa publica cada mañana la agenda del día en
  IMÁGENES y trae más que la web (el 27/10: 8 sesiones contra 4). La extensión v1.8 manda `fotos` de cada post; el
  receptor (redes.recibir) encola los de @asambleapa con fotos; la mesa (agenda_de_x, cada 5 min) se las pasa a Gemini
  (tabla `agenda_x`) y suma a `agenda`: sesión que falta → fila propia (id ≥ 2.000.000.000, organizador "Agenda
  publicada en X (@asambleapa)"; se borra si después la publica la web o, el Pleno, cuando entra su Orden del Día);
  puntos que faltan → al final de la descripción ("Agregado de la agenda publicada en X"). prensa.py (GitHub) reescribe
  cada hora las filas de la web: la mesa los vuelve a poner. A mano: `python3 cerebro/agenda_x.py <url foto>…`.
- No sirven: votaciones de prensa507 (vacías).

Diferencias con Ecuador: tres debates, prohijamiento (anteproyecto → proyecto), sin correo ni boletines.

## Proponentes (pedido de Andrés, 2026-10-08)

En Panamá es común que varios diputados presenten juntos (425 de 931 fichas; hasta 46 nombres). El sistema los trae en
un solo texto con comas, "H.D" (diputado) o "H.D.S" (suplente) delante. `nombres.py` los separa (ojo: el nombre de la
comisión de Credenciales lleva comas) y unifica las formas cortas en la más completa ("JOSE PEREZ BARBONI" → "José
Antonio Pérez Barboni"): 124 personas. El primero de la lista es el principal.
- Base: tabla `proponentes` (ficha, nombre, tipo, principal, orden).
- Matriz: "Proponente principal" y "Otros proponentes" en la hoja Proyectos, y hoja "Proponentes" con una fila por
  proponente y proyecto para filtrar por diputado. `MATRIZ_VERSION` en base.py: subirlo al cambiar columnas (esa vez
  no se recogen Notas ni borrados, porque las columnas no calzarían).
- Telegram: "Nombre y N más"; el .md de Drive trae la lista completa.

## Kiwi y la oficina (etapa 3, 2026-10-08)

Worker de Cloudflare `agente-panama` (https://agente-panama.agentemonitoreopa.workers.dev), binding D1 `DB`.
Desplegar: `python3 bot/desplegar.py` (todo: código, claves y webhook de Telegram) o `--codigo` (solo worker.js y
oficina.html; tarda unos segundos en propagarse). BOT_WEBHOOK_SECRET y OFICINA_CLAVE se generan la primera vez en .env.
Telegram es SOLO de notificaciones (decisión de Andrés, 2026-10-08): a cualquier mensaje responde que se pregunte en la oficina. Gemini: la misma GEMINI_KEY gratuita.
- Cerebro (`responder`): 1) un modelo liviano (MODELOS_RAPIDOS, Flash-Lite) recibe el índice de las 931 fichas y las
  listas de proponentes, comisiones, etapas y sectores, y devuelve fichas a leer y filtros; 2) se arma el contexto con
  D1 (listado con totales ya contados por rol, etapa e impacto; Gemini no debe contar filas) y el .md más reciente de
  Drive de cada ficha elegida; 3) Kiwi responde. 15-20 s por respuesta.
- Gemini no admite "" en un enum del esquema (da 400): por eso impacto_minimo usa "ninguno".
- Oficina: `/oficina?k=<OFICINA_CLAVE>`. Mismo diseño que la de KeyCurul (pedido de Andrés): pestañas debajo de la barra, seis
  escritorios (Revisor, Analista, Archivista, Mensajera, Asistente, Cronista), Kiwi en guayabera que camina al escritorio
  que corresponde mientras el Worker responde, ventana con el Puente de las Américas y pizarra con lo último. Pestañas Oficina (escena con la ciudad de Panamá, chat con Kiwi, novedades
  día a día de los últimos 14 días), Proyectos (filtros por comisión, etapa, impacto, en trámite) y Diputados (124
  proponentes; principal/coproponente). Detalle de ficha en panel lateral (`/oficina/ficha?n=`). Los títulos sin
  analizar llegan en MAYÚSCULAS y el Worker los pasa a oración (`oracion()`).

## El cerebro (second brain, desde 2026-10-24; plan en PLAN.md)

Tablas nuevas en la misma D1 (`cerebro/esquema.sql`): entidades, alias, documentos, fragmentos (FTS5, sin tildes),
menciones, relaciones, declaraciones, expedientes, productos, tareas. Todo corre gratis; lo pesado, en la Mac.
- `cerebro/__init__.py`: la puerta única (`guardar_documento`, no duplica), `guardar_entidades` (+ alias; un alias que
  calza con dos entidades se descarta y nunca se usa uno hecho solo de nombres de pila), `enlazar` (menciones por
  alias) y `buscar` (texto completo).
- `cerebro/directorio.py`: carga los actores desde la investigación de ChatGPT (`Invesitgacion/`, no se sube):
  71 diputados, 70 suplentes, gabinete, viceministros, autoridades, partidos, gremios, 15 comisiones; relaciones
  integra/preside/pertenece_a/suplente_de/dirige; une diputados con su nombre en `proponentes` (67 de 71). Los cargos
  se copian de la fuente: nunca se deduce el género de un nombre.
- `cerebro/ia.py`: Gemini gratuito; si un modelo agota su cuota diaria, prueba el siguiente.
- `cerebro/perfilador.py <nombre> [--diseno]`: expediente del actor (solo con lo del cerebro, fuentes numeradas).
- `diseno/keyperfil.py` (la Diseñadora): Keyperfil A4 en PDF con el sistema de diseño de Keyword (Figtree, paleta,
  logos; guía A4) e impresión con el Chromium de `~/.venvs/nav` (Playwright). Salida en `salidas/` (no se sube).
- `cerebro/transcribir.py <id YouTube>` (Mac): audio con yt-dlp reciente (`uvx --python 3.12 yt-dlp@latest`; el de
  Python 3.9 falla con "The page needs to be reloaded"), Whisper local (`~/.venvs/whisper`, mlx-whisper,
  large-v3-turbo) y se borra el audio. Canal de la Asamblea: youtube.com/@AsambleaNacional507/streams.
- `cerebro/relatora.py <id YouTube>`: transcripción → Keylaw (formato de los Keylaw de Keyword) + declaraciones por
  actor (alimentan su Keyperfil).

- `cerebro/en_vivo.py vigilar|seguir <id>` (Mac): sesiones EN VIVO. Detecta `is_live` en el canal, yt-dlp → ffmpeg en
  trozos de 5 min (el ffmpeg de ~/.local/bin no valida TLS: por eso yt-dlp baja y le pasa el audio por tubería),
  Whisper por trozo, aviso en caliente cada 15 min (Telegram) y Keylaw al terminar. Probado con un video emitido.
- `cerebro/receptor_gaceta.py` (Mac, 127.0.0.1:8765): recibe los PDF de la Gaceta que Claude baja con el Chrome de
  la oficina (VIGIA_JS). La Gaceta pide un captcha hCaptcha que marca una PERSONA (Claude no lo resuelve); después
  la sesión deja leer la portada (tabla de contenido + 5 últimas ediciones) y bajar PDF. Chrome pidió una vez permiso
  de "red local" para hablar con el receptor. Muchas páginas son escaneos: falta OCR (Vision de macOS, gratis).
- `cerebro/normativa.py [número]` (la Analista normativa): sube el PDF de cada edición a Gemini (lee también los
  escaneos, no hace falta OCR), guarda cada norma en `normas` (entidad, tipo, número, resumen, sectores, impacto) y
  escribe el Keymonitor de las de impacto alto o medio (`productos`, borrador). La mesa lo corre sola con cada edición nueva.
- `cerebro/partir.py` (lo llama normativa.leer): un PDF por norma con nombre de Keyword "AAMMDD Nombre corto.pdf"
  (fecha de la edición), sin las páginas del sumario, en salidas/gaceta/normas/ y en Drive (<raíz>/Gaceta Oficial/
  <edición>/); enlace en normas.pdf. La carpeta "Gaceta Oficial" de Drive está compartida con "cualquiera con el
  enlace" (lector; 28/10, pedido de Andrés para que los jefes abran los PDF): lo nuevo lo hereda solo. La oficina lo ofrece para descargar y como adjunto del Keymonitor.
- Escena (2026-10-24): ventana chica y dos pizarrones grandes por coordinación (legal: Asamblea hoy / última Gaceta;
  política: actores en el cerebro / agenda de medios; económica: pronto); reloj y bandera en la jefatura. Debajo:
  legal = agenda de la Asamblea por día (desde el lunes, con Keylaw/Solo guardar); política = gabinete con foto
  (datos.foto; si no hay, iniciales) que al tocarlo pregunta a Kiwi. Fotos y fuentes de medios: pendiente ChatGPT.
- `cerebro/perfiles.py`: carga las tandas de perfiles de ChatGPT ("# Tanda…", un bloque "## Nombre" por actor) como un
  documento por persona (fuente investigacion_perfil). Correrlo cada vez que llegue una tanda.
- `perfilador.publicar()` / `--publicar` (subir PDF a Drive) quedó en desuso: ya no se guardan PDF. En la oficina el Perfilador está ACTIVO y su mesa tiene SOLO
  dos cosas (Andrés: habrá miles de perfiles, no se listan todos): 1) Buscar un perfil (/oficina/perfiles?q=, en el
  Worker: nombre, cargo, institución, comisión, partido, provincia o grupo, en cualquier combinación; sinónimos
  congreso→asamblea, femenino/plural; dice el papel: "Preside Comisión de Presupuesto"); 2) Generar un perfil a mano
  (POST /oficina/perfil-nuevo → tarea perfilador/nuevo → mesa.perfil_nuevo: usa la persona del directorio o la crea, y
  las notas entran como perfil investigado). /oficina/actores trae `keyperfil` {archivo, fecha}.
- Las mesas se abren como VENTANA CENTRAL grande (pop-up), no como panel lateral, con un menú de tarjetas (ícono,
  título, una línea, número de pendientes). Sin listas de "pedidos recientes". Perfilador: "Editar" abre el perfil
  para corregirlo a mano (cargo, estudios, trabajos, datos de interés; POST /oficina/expediente) con el Keyperfil al
  lado; "Rehacer con IA" lo vuelve a armar (reemplaza lo hecho a mano). "Descargar PDF" del Keyperfil usa html2pdf
  (cdnjs) en el navegador: una página, sin diálogo de imprimir; al capturar usa colores lisos (clase .captura).
- Editor del perfil (Perfilador → Buscar → Editar): foto (se sube y se achica a 400 px; queda en datos.foto como data
  URI; POST /oficina/foto), secciones con negrita/cursiva/subrayado (listas contenteditable; el Keyperfil acepta solo
  b/i/u), "Revisar ortografía" (POST /oficina/revisar, Gemini liviano: solo forma, nunca contenido; también en cada
  Keylaw y Keymonitor) y "Descargar PDF". Abajo, "Lo que sabe el cerebro": declaraciones agrupadas por fuente (Asamblea,
  entrevistas) y menciones, con "Agregar a datos de interés".
- Keylaw y Keymonitor también con editor de formato (editorReporte en oficina.html): negrita, cursiva, subrayado,
  "• Viñeta" (pone o quita), → / ← (nivel de la viñeta), Quitar formato; se escribe en párrafos normales y Enter en
  una viñeta vacía sale de la lista. Se guarda como texto: **negrita**, _cursiva_, <u>subrayado</u>, viñetas "- " (dos
  espacios por nivel). "Copiar correo" copia con formato (HTML) y, si el navegador no deja, como texto.
- DATOS DE PRUEBA (BORRAR antes de la versión final): declaraciones de Fernando Boyd Galindo en documentos con fuente
  `prueba_asamblea` / `prueba_entrevista` (sin fragmentos, no entran a Kiwi). Borrar con: DELETE FROM declaraciones
  WHERE documento LIKE 'prueba:%'; DELETE FROM documentos WHERE fuente LIKE 'prueba%'. También MEDIOS_EJEMPLO.
- PDF de paso: `mesa.limpiar_pdf` borra cada día los PDF de más de 7 días (normas partidas, ediciones, Keyperfil) en
  la Mac y en Drive, y deja normas.pdf en NULL. El texto de cada norma queda en el cerebro (fuente "gaceta_texto").
- DISEÑO PUBLICADO (2026-10-25): la escena dibujada en SVG (bot/escena_nueva.js + .css) se suma a oficina.html al
  desplegar y es la oficina publicada (y /oficina/previa). Estilo plano 2.5D, línea gráfica de Keyword (Figtree,
  #18191F/#9500C5/#D4BBFF). Las piezas de ChatGPT se descartaron ("horroroso"); quedaron en D1 `imagenes` sin uso.
  Tarjeta de cada agente: el nombre de la persona y, abajo, lo que hace (campo `funcion` en AGENTES): Fernando ·
  Asamblea Nacional, Inés · Gaceta Oficial; Elena · Órgano Judicial, Mateo · Entes Reguladores, Sofía · Perfiladora (nombres
  ficticios elegidos por Claude a pedido de Andrés). Se abre la mesa tocando la tarjeta o la persona. Las mesas usan la misma línea gráfica y el encabezado
  muestra el mismo dibujo de la persona (retrato() se reemplaza en escena_nueva.js; Kiwi conserva el suyo).
- Mesas con SUBMENÚS (Andrés, 2026-10-25: "no que todo se despliegue como una tabla"): cada mesa abre con pocos
  botones grandes y cada uno abre su pantalla con "← Volver" (MESAS en oficina.html). Donde se trabaja con textos la
  mesa ocupa TODA la pantalla. Fernando: Sesiones por venir (Keylaw / Solo guardar; sin respuesta = solo guardar, NO
  se escribe Keylaw), Historial de sesiones (enlace al video + transcripción, que se lee, copia o baja en .md; "Pedir
  Keylaw" → tarea relatora/keylaw), Keylaw por revisar. Inés: Revisar si hay Gaceta (arriba), Gaceta del día (SOLO
  las ediciones de la última fecha, TODAS las normas, cada edición desplegable), Keymonitor, Subir la Gaceta (PDF →
  /oficina/subir-gaceta → tabla `subidas` en trozos → tarea vigia/subida → mesa.gaceta_subida → receptor.guardar).
  Perfilador: Buscar un perfil, Generar un perfil.
- Keyperfil SIN PDF guardado (Andrés: "los PDF son basura una vez descargados"; quedan solo los datos en
  `expedientes`): /oficina/keyperfil?id= arma la página con el modelo al vuelo y "Descargar PDF" la imprime desde el
  navegador (una página del alto del contenido, nombre "AAMMDD Keyperfil Nombre"). Íconos y logo se inyectan al
  desplegar (__KP_ACTIVOS__ desde ejemplos/keyword/keyperfil/ y KEYWORD_DISENO). Foto: datos.foto de la entidad (URL).
- Diseño del Keyperfil = el MODELO de Keyword (Andrés, 2026-10-25: "debe ser igual, no me cambies"): tira vertical
  lavanda, "PERFIL", foto redonda + nombre y cargo, tarjetas "Principales estudios:", "Principales trabajos:" y "Datos
  de Interés" con los íconos del modelo (ejemplos/keyword/keyperfil/, no se suben), logo al pie; un PDF de una página
  del alto del contenido. Fotos: ejemplos/keyword/keyperfil/fotos/<slug>.jpg. Ejemplo hecho: Mulino.
- `cerebro/reguladores.py` (Entes Reguladores, ACTIVO desde 2026-10-25): ASEP (API WordPress: resoluciones y avisos
  por sector; las "Acta de recepción" de frecuencias se saltan), Superintendencia de Seguros (acuerdos en consulta y
  acuerdos), SMV (páginas proyectos-de-acuerdo-<año> y acuerdos-<año> por la API WordPress), Superintendencia de
  Bancos (acuerdos del año), y DGNTI/MICI (consulta pública de reglamentos técnicos; los reglamentos ya adoptados salen
  en la Gaceta, que lee Inés: la web del MICI no tiene una lista al día). ACODECO NO entra (Andrés: si no genera
  normativa, no interesa). En la mesa: "Lo nuevo" = solo lo publicado; "Consultas públicas" = solo borradores; el
  resumen se ve sin abrir nada. ASEP se pide sector por sector (si no, la
  electricidad tapa a los demás). Solo se analiza lo de 45 días. Ninguna tiene anti-bots. Lo
  nuevo va a la tabla `regulatorias` (Gemini: nombre corto, resumen, sectores, impacto, plazo de comentarios) y su
  texto al cerebro (fuente "regulador"); la primera vez de cada fuente solo se analiza lo de 30 días (lo viejo queda
  impacto "base"). Telegram avisa lo alto/medio y las consultas. La mesa revisa cada 3 h de 7 a 21 (y "Revisar
  ahora"); en la oficina: Lo nuevo, Consultas públicas y Keymonitor (productos tipo keymonitor, agente regulatoria;
  `reportes(tipo, agente)` los separa de los de la Gaceta).
- `cerebro/judicial.py` (Elena · Órgano Judicial, ACTIVA desde 2026-10-25; investigación en Invesitgacion/…report-3 5.md):
  el Pleno de la CSJ decide la constitucionalidad (no hay Corte Constitucional). Orden para enterarse primero:
  comunicados del Órgano Judicial → edictos del Pleno → Consulta de Fallos → prensa → Gaceta (25-110 días: no sirve).
  SIN PRENSA (Andrés, 2026-10-25: "solo fuentes internas" de la Corte). Se probó con los RSS de TVN, La Prensa y
  Telemetro y se quitó; el análisis (Gemini dice si es una DECISIÓN: tribunal, proceso, resumen, impacto) queda para
  los comunicados y edictos. Tabla
  `judiciales`; Telegram avisa las decisiones alto/medio; Keymonitor con agente "judicial". En la oficina: Lo que
  resolvió la Corte, Otras notas judiciales, Keymonitor (misma lista que Mateo: listaReg con CFG_JUD).
  CHROME DE LA OFICINA (2026-10-25, instalada por Andrés): extensión `extension/oficina-chrome/` (chrome://extensions →
  Modo desarrollador → Cargar descomprimida; tras cambiar el código, botón de recargar). Cada 20 min (7-22 h) trae
  también la GACETA: abre la portada, manda a /gaceta las ediciones que /tengo no tiene (si pide «Soy humano», avisa;
  no lo marca). Y para la Corte abre en una pestaña de fondo la lista de edictos
  del Pleno, baja los PDF nuevos (uno por día: "edictos fijados el día…") y las noticias nuevas de /noticias, y los
  manda al receptor de la Mac (POST /judicial/edicto y /judicial/comunicado; GET /judicial/vistos). Si la web pide
  verificación, NO la toca: notificación en Chrome y Telegram (/judicial/alerta, máx. cada 3 h) para que una persona
  la pase. Clic en el ícono = revisar ahora. El receptor guarda documentos fuente oj_edicto / oj_comunicado; la mesa
  (cada 5 min) corre judicial.procesar(): los edictos vienen ESCANEADOS (sin texto): Gemini lee el PDF y separa cada expediente (proceso, si decide, fecha,
  resumen, impacto) o analiza el comunicado; Telegram avisa decisiones alto/medio. Una página web normal no puede
  hablarle al receptor sin el permiso de "red local" de Chrome; la extensión sí (host_permissions).
  Antes: comunicados de la Corte y lista de edictos del Pleno (www.organojudicial.gob.pa/files/edictos-de-salas-y-
  tribunales-superiores/corte-suprema-de-justicia-edictos/pleno-de-la-corte-suprema-de-justicia-edictos) están detrás de
  Radware: NO se esquiva (Andrés pidió esquivarlo y Claude no lo hace); entran con el Chrome de la oficina (sin
  verificación en un Chrome normal) como la Gaceta. Consulta de Fallos corre sobre vLex: no se automatiza.
- Coordinación política (Andrés, 2026-10-25): Agenda + Entrevistas + Medios se juntaron en UN agente, **Diego ·
  Entrevistas y medios** (`cerebro/entrevistas.py`), con 4 botones: Agenda de medios (grilla PROGRAMAS de la
  investigación; invitados pendientes de las redes), Autoridades en medios (Gabinete los martes, conferencias de
  Presidencia y sesiones de la Asamblea de hoy; incluye a la Asamblea), Escuchar una entrevista (enlace de YouTube →
  en_vivo.seguir con su propio aviso y al_terminar; avisos en caliente por Telegram; declaraciones a los perfiles;
  tabla `entrevistas`) y Bolas rojas (productos tipo "bolaroja", agente "entrevistas"; formato de los ejemplos reales
  en ejemplos/keyword/BolaRoja/, no se suben: "🔴 NUEVA ENTREVISTA AL…", viñetas por tema, "Saludos cordiales.").
  Noticieros (investigación Invesitgacion/…report-3 6.md): NOTICIEROS en entrevistas.py (TVN @TVNNoticiasYT,
  Telemetro @telemetropa, SERTV @SertvNoticias, Radio Panamá @RadioPanama945; franjas L-V mañana/mediodía/noche); la
  mesa (escuchar_noticieros, cada 3 min) busca el en vivo de cada canal en su franja y lo escucha hasta el fin de la
  franja (tipo "noticiero"); si no se dijo nada importante se borra todo. Diego ya NO muestra la Asamblea (la cubre
  Fernando). Se quitó la agenda de medios de abajo y MEDIOS_EJEMPLO.
  **Paula · Monitor de medios** (`cerebro/monitor.py`): cada 15 min (6-22 h) lee RSS de La Prensa, TVN y Telemetro;
  Gemini mira solo titulares nuevos con las reglas del chat real del equipo (Invesitgacion/guia_agente_noticias_keyword.md)
  y manda al chat SOLO la URL, una por línea, una fuente por hecho; no resume ni guarda (monitor_vistos, 3 días).
  El "chat de la oficina" será un GRUPO DE TELEGRAM (falta crearlo y su chat id).
  **Redes (X), desde 2026-10-26** (`cerebro/redes.py`): la extensión v1.6 lee cada 15 min (6-22 h) dos listas PRIVADAS
  de la cuenta de X de la oficina (LISTAS_X en fondo.js: Medios Panamá y Autoridades Panamá; se agregan cuentas en
  x.com → Listas → Editar → Administrar miembros) y manda las publicaciones a POST /redes/posts del receptor. Lo nuevo
  (≤12 h) va a una bandeja LOCAL (salidas/redes/, no D1); la primera vez solo anota. Paula las toma con los RSS (misma
  llamada a Gemini; si falla, vuelven a la bandeja); Diego saca invitados y apariciones (filtro PISTAS + Gemini) →
  tabla `medios_agenda` → "Agenda de medios" (invitados de hoy) y "Autoridades en medios"; Telegram avisa cada
  anunciada (🎙). Si X cierra la sesión: /judicial/alerta?que=x → Telegram.
  **Telegram por destino** (2026-10-26): cerebro.telegram(texto, destino=general|gaceta|asamblea|alertas) usa
  TELEGRAM_<DESTINO>_TOKEN / _CHAT del .env (si faltan, el bot actual al chat de Andrés). General = grupo de la
  oficina (Paula, Diego, Tomás, lo importante en vivo); gaceta = Inés; asamblea = sesiones en vivo, Keylaw y los
  BOLETINES de prensa de la Asamblea (la extensión v1.7 los lee en asamblea.gob.pa → POST /asamblea/boletines →
  receptor.boletines, de a uno con pausas; la primera vez solo anota). Corte y reguladores → grupo de la Gaceta;
  avisos del sistema (X sin sesión, Corte pide verificación) → grupo de la oficina (Andrés, 2026-10-26).
  agente.py y prensa.py (GitHub Actions) siguen con el bot actual hasta cargar los secretos nuevos en GitHub.
  NO hacer briefings ni resúmenes diarios (Andrés: "nadie los lee").
  GRUPOS (Andrés, 2026-10-26: grupos y no bots sueltos, para poder conversar): "Keyword Panamá" (oficina, bot
  @keyword_panama_oficina_bot, TELEGRAM_GENERAL_*), "Gaceta · Keyword Panamá" (@keyword_panama_gaceta_bot,
  TELEGRAM_GACETA_*), "Asamblea Nacional · Keyword Panamá" (el bot de siempre @keyword_panama_alertas_bot, que se
  llamará "Monitoreo Asamblea Panamá"; TELEGRAM_ASAMBLEA_CHAT). El Worker anota en config "grupo_telegram:<id>" cada
  grupo donde está el bot de siempre (con webhook no hay getUpdates). El monitoreo de GitHub manda a TELEGRAM_CHAT_ID
  (secreto de GitHub): cambiarlo al grupo de la Asamblea lo hace Andrés (el clasificador no deja a Claude escribir secretos). La cuenta de X está en ESPAÑOL (en inglés
  X traduce los textos). SEGUIMIENTO (Andrés, 2026-10-26): "Autoridades en medios" muestra solo a quienes seguimos
  (persona del directorio, redes.seguido → medios_agenda.entidad) y Diego escucha esas entrevistas SOLO
  (mesa.escuchar_anunciadas: cada 3 min, hasta 6 h tras el anuncio, busca el en vivo en el canal del medio, CANALES
  en redes.py, máx. 90 min); el resto queda en "Agenda de medios" con botón "Seguir" (POST /oficina/seguir). Telegram
  🎙 solo para los seguidos. Regla de Paula para autoridades: su agenda del día y reuniones con contenido SÍ son noticia.
  Keypolitics (Analista político) se BORRÓ de la oficina (Andrés, 2026-10-25: no va por ahora, quizá nunca). Política
  queda con Diego, Paula y Sofía.
- **Tomás · Cifras y Keyeconomics** (`cerebro/cifras.py`, coordinación económica, 2026-10-25): solo lo REGULAR (lo
  analítico lo hace una persona, como pasó con Keypolitics). Vigila el INEC (sin anti-bots): IPC, IMAE, Principales
  Indicadores Económicos Mensuales (la página cambia de año: se busca la más reciente), PIB trimestral y Encuesta de
  Mercado Laboral. Señal de dato nuevo = el PDF "Comentario" de cada publicación (tabla `cifras`; la primera vez solo
  anota). Gemini escribe el Keyeconomics con la plantilla de los 78 reales (ejemplos/keyword/Keyeconomics/, bajados en
  solo lectura del correo de Keyword) → productos tipo "keyeconomics", agente "cifras", borrador. Telegram solo avisa
  "ya está en la plataforma para revisión" (lo de correo nunca se revisa en el chat). Mesa: cada hora L-V 8-18.
  Oficina: Cifras publicadas (con "Escribir Keyeconomics" a mano), Calendario (CALENDARIO_INEC), Keyeconomics.
  **Combustibles** (`cerebro/combustibles.py`, 2026-10-26): comunicado de la Secretaría Nacional de Energía cada 14
  días (API WordPress de energia.gob.pa, sin anti-bots); los precios vienen en IMÁGENES que Gemini lee (inline_data);
  fila en `cifras` (indicador "Combustibles") y Keyeconomics en borrador (montos en B/. por litro). Corre con el INEC.
  La mesa usa el python de ~/.venvs/whisper: ahí también va pypdf (faltaba y el Keyeconomics fallaba).
  Pendiente: pases de Inés → Tomás (decretos económicos) y bola roja.
- **Aprendizaje nivel 2** (2026-10-26): al guardar un reporte corregido en la oficina (POST /oficina/producto), la
  versión del agente queda en `productos.original` y la pareja en `correcciones` (una fila por reporte). Al escribir,
  cerebro.ejemplos(Keylaw/Keymonitor/BolaRoja) y cifras.ejemplos suman cerebro.aprendido(tipo): las últimas 4
  correcciones (antes/después). Inés suma normativa.criterio_equipo(): normas que el equipo eligió para Keymonitor y
  las de impacto alto/medio que dejó pasar. La oficina muestra "🧠 Aprendió de N correcciones" y "✎ corregido".
  Rehacer un reporte con IA deja original en NULL (es una versión nueva del agente). Niveles 1-3 en presentacion/notas.md.
- **Vectorize** (2026-10-26, `cerebro/vectores.py`): índice `cerebro-panama` (768 dim., coseno) en la cuenta
  agentemonitoreopa, binding VECTORES del Worker; embeddings gemini-embedding-001 (RETRIEVAL_DOCUMENT / _QUERY); id =
  rowid de `fragmentos`; config "vectores_hasta" = último rowid pasado; la mesa (pasar_vectores) manda lo nuevo cada
  10 min. Kiwi: búsqueda MIXTA en contextoCerebro (FTS5 + porSignificado, intercaladas). Con Gemini gratis la carga
  inicial se corta por cuota (429) y sigue sola. Prueba: `python3 cerebro/vectores.py --buscar <texto>`.
- **Aprendizaje de PAULA ENCENDIDO** (Andrés, 2026-10-26, desde las 00:00 del 26/10 para que cuenten sus primeras reacciones): `python3 cerebro/aprendizaje.py encender monitor` (clave config "aprendizaje:monitor"; aprendizaje.para_agente). Los demás siguen apagados.
- **Aprendizaje APAGADO hasta el lanzamiento** (`cerebro/aprendizaje.py estado|encender|apagar`; tabla `config`):
  apagado, el Worker no guarda correcciones y los agentes no las usan; al encender cuenta solo lo posterior.
- **OFICINA PUBLICADA (Andrés, 2026-10-26, noche): `bot/escena_entrada.js/.css`** (la de siempre + la entrada al medio con Kiwi, el logo, la banderita y la pantalla con el cerebro EN VIVO; 4 zonas). desplegar.py la arma y cambia Math.min(2→3); el Worker sirve /oficina/grafo y /oficina/mapa (mapaCerebro, misma lógica que cerebro/mapa.py; plantilla diseno/mapa.html como __PAGINA_MAPA__). Historia (planta, isométrica, mando: descartadas):
  `cerebro/mapa.py` + `diseno/mapa.html` (red con d3: entidades, relaciones, menciones, proyectos por proponente).
  `bot/escena_planta.js/.css`: legal a la izquierda, al centro la entrada con Kiwi en la recepción, el cerebro (forma
  ilustrada con los puntos reales adentro: actores a la izquierda, documentos y proyectos a la derecha; señales que
  recorren las líneas) y la económica al fondo en una sala de vidrio; política a la derecha; se entra por el centro.
  Andrés no quedó conforme con la de frente y eligió la ISOMÉTRICA (`bot/escena_iso.js/.css`, la que sirve hoy la
  prueba): todo el piso visto desde arriba en diagonal (N = 24 m; P(x, y, z) proyecta; caja() y poly() dibujan; los
  objetos se ordenan por x + y), económica al fondo, legal a la izquierda, política a la derecha, el cerebro al
  centro y la entrada adelante con pórtico y mostrador de Kiwi con el LOGO de Keyword (imagen). Cámara: arrastrar,
  pellizcar o Ctrl + rueda, +/− y botones Entrada / Legal / Económica / Política; tarjetas chicas en la vista general.
  `python3 bot/prueba_local.py` → http://127.0.0.1:8778/oficina (solo en la Mac; reenvía al Worker y agrega la clave;
  /oficina/grafo y /oficina/mapa los arma la Mac). Para publicar: pasar grafo y mapa al Worker y cambiar
  escena_nueva por escena_planta en desplegar.py.
- `cerebro/mesa.py` (Mac): latido, tareas pedidas desde la oficina, vigila el canal en vivo y lee cada Gaceta nueva.
- **Chat de doble vía** (2026-10-26, `cerebro/chat.py`, hilo de la mesa): en los tres grupos se le habla a un agente
  por su nombre al comienzo ("Fernando, ¿dónde dijo esto?"), respondiendo a un mensaje suyo o con @bot. Bots de la
  oficina y de la Gaceta: getUpdates (privacidad apagada, sin webhook); el de la Asamblea: webhook del Worker →
  tabla `chat_entrada`. Cada aviso se anota en `chat_mensajes` (agente + ref: entrevista:/sesion:/url:/gaceta:/
  regulatorias:/judiciales:/pase:) para saber de qué hablan al responderle. Pedidos: "bola roja" y "Keyeconomics"
  (pases.del_chat, con la entrevista, la nota enlazada, la norma…), "Keylaw" y "transcripción" (.md) sobre una sesión;
  SOLO la bola roja llega completa al chat; Keylaw, Keyeconomics y transcripciones: el chat avisa que están en la
  oficina para revisión (Andrés, 2026-10-26). Lo demás → /oficina/kiwi con persona y citado (contesta como ese agente; citas con minuto y enlace ?t=).
  Solo atiende los chats del .env. Ojo: un mensaje que EMPIEZA con el nombre de un agente se toma como dirigido a él.
- **Reacciones 👍/👎** (Andrés, 2026-10-26): chat.reaccion guarda en `reacciones` cada 👍 (❤️ 🔥 👏) o 👎 a un mensaje de un
  agente, con su texto (para Paula, medio y titular). monitor.criterio_equipo() suma al FILTRO de Paula lo que sirvió y
  lo que no (solo con el aprendizaje ENCENDIDO). Telegram solo manda reacciones si el bot es ADMINISTRADOR del grupo.
  PRUEBA de que aprende (demo): `python3 cerebro/monitor.py --comparar` filtra los mismos titulares de 3 días sin y con
  el criterio del equipo (temperatura 0) y lista lo que cambió de decisión; no manda nada al chat.
- **Pestaña "Aprendizaje" dentro del cerebro** (Andrés, 2026-10-26: no un botón nuevo; TODO el aprendizaje, no solo
  Paula): la ventana del cerebro tiene dos pestañas, "Mapa del cerebro" y "Aprendizaje" (/oficina/aprendizaje,
  plantilla diseno/aprendizaje.html → __PAGINA_APRENDIZAJE__, datos en aprendizajeDatos del Worker, 5 min). Por semana
  (8): % de lo que manda cada agente que recibe 👎 (baja), % del texto que el equipo cambia en cada reporte (baja),
  cambios de Kiwi por reporte por clase (baja), normas elegidas para Keymonitor que Inés ya marcaba alto/medio (sube).
  OJO: la plantilla se rellena reemplazando la PRIMERA aparición de __DATOS__ (no escribirlo en comentarios).
- **Kiwi revisa** (Andrés, 2026-10-26: función interna de Kiwi, NO un agente aparte; `cerebro/editora.py`): todo
  Keylaw, Keymonitor, Keyeconomics y bola roja se guarda con editora.guardar(): Kiwi lo compara con sus fuentes,
  corrige datos que no están, formato y redacción, y recién ahí queda en la oficina para que el equipo lo edite.
  productos.editora = qué cambió (la oficina: "🥝 revisado por Kiwi" y la lista desplegable).
- **Memoria de anuncios** (`cerebro/anuncios.py`, tabla `anuncios`, 45 días): antes de cada aviso en vivo, Gemini
  separa nuevo / repetido / novedad y deja solo lo nuevo ("Nuevo dato sobre…"). Paula recibe lo ya enviado (3 días) y
  no reenvía el mismo hecho salvo dato nuevo. La bola roja recibe los anuncios previos ("ya anunciado el…").
- **Botón «Ver sesión»** (Andrés, 2026-10-26): tercer botón junto a Keylaw / Solo guardar (y en el Pleno de hoy, en la
  agenda de abajo). La mesa anota en config "canal_asamblea" las transmisiones en vivo y programadas del canal
  (en_vivo.anotar_canal, solo si cambian); el Worker enlaza las sesiones de HOY por el nombre de la comisión. Sin
  transmisión, abre el canal. En vivo: «● Ver en vivo» en rojo.
- **En vivo cada 2 minutos** (en_vivo.TROZO = 120): cada trozo nuevo se revisa con el anterior; el aviso lleva el
  minuto y el enlace al video en ese minuto.
- **Pases de Mateo y Elena** (pases.de_entes): Gemini marca "economica" en regulatorias y judiciales; económica +
  alto/medio → Tomás; alto → Diego. Origen "regulatoria:<id>" / "judicial:<id>".
- **Kiwi: vida de la ley y tiempos** (Worker): fichaCompleta suma "Después de la Asamblea" (la ley en la Gaceta por
  "Proyecto N de AAAA aprobado en tercer debate" + lo que cita "Ley N": reglamentos, reguladores, Corte). Si se
  pregunta cuánto tarda algo (plan.tiempos), tiemposTramite: medianas por paso y por comisión con el historial de
  `eventos` (sin botón: solo se pregunta en el chat o a Kiwi).
- Oficina (diseño final de Andrés, 2026-10-24, tercera vuelta): la oficina ILUSTRADA de KeyCurul como UN solo piso
  continuo de 3.600 de ancho (legal 0-1200, política 1200-2400, económica 2400-3600). Se recorre arrastrando con el
  mouse, deslizando o con los tres botones de arriba (se detiene en cada coordinación). Legal: Fernando (Keylaw) e Inés
  (Keymonitor) con nombre ficticio corto; Judicial y Reguladores en gris; el Vigía y la Cronista (apoyo) en la
  oficinita de vidrio "Monitoreo", con reloj, bandera y el hemiciclo 2024-2029 (por partido; abre la Asamblea con la
  ficha de cada diputado). Un solo pizarrón: la Gaceta de los últimos días (abre la mesa de Inés). Ventana grande, sin
  la "piscina". Kiwi NO está en la escena: bolita flotante con chat que se minimiza mientras piensa (puntitos; punto
  rojo si respondió). Debajo, según la zona: legal = agenda de la Asamblea día a día (flechas, "Hoy", cada sesión se
  abre: lugar, proyectos, Keylaw/Solo guardar); política = agenda de medios con DOS EJEMPLOS FICTICIOS
  (MEDIOS_EJEMPLO en oficina.html: borrarlos cuando el Monitor de medios funcione) y cómo va a funcionar.
- Decisiones humanas (tabla `decisiones`): 1) Gaceta: la Analista indexa cada edición y avisa por Telegram los temas;
  en su mesa una persona lee y marca qué normas van a Keymonitor (tarea normativa/keymonitor → normativa.redactar)
  o marca la edición "revisada". 2) Sesiones: la Cronista avisa por Telegram cada convocatoria; en la mesa de la
  Relatora se marca "Keylaw" o "Solo guardar" (agenda:<id>). La Relatora transcribe todas; sin marca, el Keylaw queda
  "archivado" y se pide después con un clic. Keylaw y Keymonitor usan como guía de tono los ejemplos reales
  (`cerebro.ejemplos()`, de `ejemplos/keyword/`, no se suben). Cada reporte: editable, "Copiar correo" (viñetas con
  asterisco), revisado/enviado.

## Pendientes (2026-10-09)

- **Workers Paid** (Andrés): el 27/10 D1 llegó al límite diario de escrituras del plan gratis y la mesa no pudo
  guardar nada (la oficina la mostraba apagada). **Mudanza a la PC de la oficina** (aprobada el 28/10; Windows 11 +
  RTX 5080): plan en PLAN.md (WSL2, no Hyper-V; faster-whisper; arranque solo tras reinicio).

- **Rotar** los tokens de los bots Keyword Panamá · Oficina (@keyword_panama_oficina_bot) y · Gaceta
  (@keyword_panama_gaceta_bot): pasaron por el chat el 2026-10-26 (en @BotFather: /revoke, y poner los nuevos en
  TELEGRAM_GENERAL_TOKEN / TELEGRAM_GACETA_TOKEN del .env). Chat de la oficina = grupo "Keyword Panamá" (TELEGRAM_GENERAL_CHAT).

- **Duda abierta (clave):** cómo saber qué se discute de verdad en cada sesión del Pleno. El Orden del Día oficial
  trae toda la fila (~175 puntos). Lo observado (sin confirmar): lo que se vota sale de la cabeza de la lista (tercer
  debate y proyectos que la Asamblea sube), lo nuevo entra al final. Hay que confirmarlo con el equipo de Panamá
  antes de mostrar "en discusión hoy" como un hecho.
- Siguientes, de a poco (decisión de Andrés: más lento que Ecuador): 1) Proyectos de ley con el edificio de la
  Asamblea (comisiones, Pleno, Ejecutivo, publicados), como KeyCurul; 2) afinar la agenda; 3) Gaceta Oficial (Legispan).
- **Vigilante** (2026-10-26, `cerebro/vigilante.py`): cada 30 s revisa que la mesa y el receptor estén vivos; si no,
  los levanta y avisa al grupo de la oficina con el último error. Lanzar UNA vez:
  `nohup python3 cerebro/vigilante.py >> salidas/logs/vigilante.log 2>&1 &` (él levanta mesa y receptor). Para
  reiniciar la mesa SIN alarma: `python3 cerebro/vigilante.py --reiniciar mesa`. En vivo, los minutos calzan con el
  video aunque la mesa se reinicie (desfase por #EXT-X-PROGRAM-DATE-TIME menos release_timestamp).
  Tras un reinicio, en_vivo.seguir conserva lo transcrito (lee el .parcial.txt), descarta trozos viejos de la carpeta
  y RECUPERA lo que falta desde la hora que guarda YouTube (DVR de ~60 min); lo atrasado no genera avisos en caliente.
  Un trozo dañado se salta (antes detenía la transcripción).
  PUERTO 8765 = receptor (29/10: una sesión de Claude de otro proyecto, Monitoreo Hidro, mató el receptor y puso ahí su
  servidor web; la extensión mandaba todo a ese servidor). Si un programa ajeno ocupa el puerto, el vigilante avisa UNA
  vez quién es y espera (antes mandaba un aviso cada 30 s). Otros proyectos: usar otro puerto.
- Lecciones del lunes 26/10: el ffmpeg de ~/.local/bin no valida el TLS de YouTube → los en vivo los baja Python
  (en_vivo.alimentar_hls); Whisper de a uno (transcribir._GPU); un aviso que no sale nunca tumba al agente (reintentos
  cada 2 min hasta una hora); la oficina recarga cada 30 s (Andrés: aunque se agote lo gratis; Workers Paid el 27/10) y nada con la pestaña escondida.
