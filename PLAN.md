# Plan: Keyword Panamá, el second brain de la oficina

Pedido de Andrés (2026-10-24): automatizar todo el trabajo de información estratégica de la oficina de Panamá.
No es un chatbot: es un **second brain** que vigila, guarda TODO, conecta, recuerda y entrega productos terminados en
formato Keyword, para que el trabajo humano sea revisar y enviar. Presupuesto amplio; fechas y dinero los maneja Andrés.
Fuentes ya investigadas: `Invesitgacion/` (informes de ChatGPT, corte 23-24/10/2026).

## 1. Qué significa "second brain"

Cuatro capacidades, en este orden de importancia:
1. **Capturar lo que sirve**: documentos, PDF, notas y transcripciones completas, con fuente, fecha y huella. Los
   videos y audios NO se guardan (pedido de Andrés): se ven donde están publicados (YouTube, Facebook), se transcriben
   y se queda el enlace y la transcripción.
2. **Conectar**: todo se une a entidades: actores (personas, instituciones, partidos, medios), instrumentos
   (proyectos, leyes, decretos, resoluciones, fallos), temas, sectores y clientes. "¿Qué dijo el ministro X del tema Y
   y qué norma salió después?" se responde siguiendo enlaces, no buscando de cero.
3. **Recordar**: cada actor, norma y tema tiene un **expediente vivo** que los agentes actualizan solos (qué es, qué
   pasó, quién habló, qué viene). Es lo que se consulta primero.
4. **Producir sin pedírselo**: los agentes trabajan por turnos, no por preguntas; generan alertas, reportes y
   resúmenes en formato Keyword, y una editora los revisa antes de que salgan. El chat con Kiwi es solo una puerta
   más para consultar el cerebro.

## 2. Los agentes

Un agente = una cobertura (de qué es responsable) + turnos + productos que entrega + su parte del cerebro.
Debajo hay **servicios** compartidos que no son agentes (recolectores, estudio de grabación, cerebro, mensajería).
KeyCurul (el monitor legislativo actual) sigue funcionando y pasa a ser el piso Legislativo.

| Piso | Agente | Cobertura | Productos |
|---|---|---|---|
| Dirección | **Kiwi, jefe de redacción** | Prioriza, reparte, ve el panorama, responde consultas | Briefing diario, consulta al cerebro |
| Dirección | **Editora** | Control de calidad: formato Keyword, fuentes citadas, sin inventos, sin duplicados | Aprueba o devuelve cada producto |
| Dirección | **Diseñadora** | Convierte los productos en piezas con la marca Keyword (sistema de diseño local): HTML con la paleta, Figtree, portadas y logos oficiales → PDF con el Chromium local. Primero Keyperfil (infografía vertical de 1 página: foto, nombre, cargo, estudios, experiencia, datos de interés) y Keymapeo | PDF listos para enviar |
| Dirección | **Ejecutiva de cuentas** | Cruce con clientes (local, nunca a la IA externa sin anonimizar) | Alertas y resúmenes por cliente |
| Legislativo | **Monitor de trámite** | Seguimiento Legislativo, etapas, Orden del Día, agenda de comisiones, Legispan | Alertas de trámite, matriz |
| Legislativo | **Relatora de sesiones** | Ve las sesiones de comisiones y del Pleno (video), transcribe, identifica quién habla | Reporte de sesión tipo Keylaw |
| Legislativo | **Analista legislativo** | Impacto por sector y cliente, textos, cambios entre debates | Informe de proyecto, comparativos |
| Normativo | **Vigía de Gaceta y Ejecutivo** | Gaceta Oficial, Consejo de Gabinete, decretos ejecutivos, resoluciones ministeriales | Alerta normativa, informe de norma |
| Normativo | **Vigía regulatoria** | Reguladores y consultas previas: DGNTI, MiAmbiente, SBP, SMV, SSRP, ASEP, DGI, ANA, ACP, AMP, ACODECO… | Alerta de borrador/consulta, informe |
| Normativo | **Analista judicial** | Corte Suprema (inconstitucionalidades, doctrina), laboral, Procuraduría, Infojurídica (vigencia) | Alerta de fallo, informe jurisprudencial |
| Político | **Agenda de autoridades** | Dónde y cuándo hablarán presidente, ministros, diputados, reguladores | Agenda del día siguiente, órdenes de grabación |
| Político | **Monitor de medios** | Prensa, TV, radio, redes; menciones de actores y temas | Monitoreo de medios diario |
| Político | **Relator de entrevistas** | Entrevistas, conferencias, comparecencias: transcripción y declaraciones citables | Reporte de entrevista, citas por actor |
| Político | **Analista político** | Lectura de coyuntura, mapas de poder, posturas por tema | Reporte político, escenarios |
| Económico | **Monitor de cifras** | INEC, MEF, SBP, SMV, ACP, AMP, ZLC, DGI; calendario de publicaciones | Series actualizadas, alertas de publicación |
| Económico | **Analista económico** | Lectura de cifras, FMI, calificadoras, fiscal, presupuesto, CSS | Productos económicos |
| Archivo | **Perfilador** | Ficha de cada actor que se alimenta sola: datos, trayectoria, cargos, proyectos, votos, y lo que dice en cada entrevista, sesión o nota (cita textual, fecha, fuente, tema); posturas por tema y cambios de postura; relaciones | Keyperfil, Keymapeo, ficha del actor |
| Archivo | **Archivista** | Expedientes vivos de temas, normas e instituciones; une duplicados y enlaces | Expedientes |

Son **18 agentes** en 6 pisos. Se pueden encender por fases; la estructura queda desde el principio.

**Servicios compartidos:**
- **Recolectores**: un colector por fuente (como `seglegis.py` y `prensa.py` hoy), que solo trae y guarda.
- **Estudio de grabación**: graba transmisiones (YouTube, Facebook, streaming de TV/radio), transcribe con
  identificación de quién habla, corta por temas. Lo usan la Relatora de sesiones y el Relator de entrevistas.
- **Cerebro**: base de datos + archivos + búsqueda (ver 3).
- **Mensajería**: Telegram, correo, Drive o Docs para entregar.

## 3. Dónde vive el cerebro

Sin video ni audio, el cerebro es texto: transcripciones (~40 MB al mes), PDF oficiales (2-5 GB al año) y vectores
de búsqueda. El primer año cabe en menos de 20 GB.

Propuesta en dos pasos:
- **Paso 1, casi gratis: Cloudflare** (lo que ya hay). D1 para datos (bases de hasta 10 GB, se pueden repartir por
  área), R2 para PDF y transcripciones (10 GB gratis), Vectorize para búsqueda por significado, Workers para la
  oficina. Plan Workers de pago: 5 USD al mes.
- **Paso 2, cuando el cerebro crezca: PostgreSQL administrado** (Supabase Pro, 25 USD al mes, 8 GB incluidos) con
  pgvector y búsqueda de texto en español, si las relaciones entre entidades piden algo más potente que D1.
- **Google Drive** sigue como vitrina para el equipo (productos terminados), no como almacén.
- Tablas: fuentes, documentos, fragmentos, entidades, relaciones, eventos, expedientes, productos.

**Cómputo:**
- GitHub Actions (gratis en repo público) para colectores y agentes por turnos.
- **Nodo en Panamá**: un computador de la oficina siempre encendido (o un Mac mini). IP residencial para YouTube y
  sitios con anti-bots (F5 de la Asamblea); ahí se bajan los audios para transcribir y se borran al terminar.

**Modelos:**
- **Claude** (API) para análisis, redacción de productos y la Editora; Haiku para clasificar en volumen.
- **Gemini** para transcribir audio (lo más barato con buena calidad) y para embeddings.
- Subtítulos automáticos de YouTube como opción gratuita de respaldo (sin identificar quién habla).
- Regla que se mantiene: los nombres de clientes no salen a modelos externos; el cruce con clientes es local.

## 4. Formato Keyword

Cada producto tiene una plantilla fija (estructura, tono, extensión, qué se cita) y ejemplos reales. Sin eso, los
agentes no pueden "entregar listo".

Catálogo real de Keyword (correo de Andrés, 24/10/2026). Ejemplos guardados en `ejemplos/keyword/` (no se suben:
son internos y algunos llevan nombres de clientes).

| Producto | Qué es | Formato | Agente que lo produce |
|---|---|---|---|
| Keylaw | Sesión de comisión o Pleno sobre un proyecto: qué se trató, quién dijo qué (por bancada) | Correo, ~2-4 mil caracteres, con PDF | Relatora de sesiones |
| Keymonitor | Norma nueva (Registro Oficial, acuerdos, normas técnicas): qué cambia | Correo + PDF de la norma | Vigía de Gaceta / Vigía regulatoria |
| Keyalert | Hecho urgente (emergencias, decisiones de último momento) | Correo corto | Kiwi + Monitor de medios |
| Keypolitics | Hecho político: nombramientos, decretos, gabinete, encuestas | Correo, a veces PDF | Analista político |
| Keyeconomics | Cifra o decisión económica: PIB, empleo, combustibles, impuestos | Correo | Analista económico |
| Keyperfil | Perfil de una autoridad nueva: estudios, trayectoria, posturas | PDF de 1 página | Perfilador |
| Keymapeo | Mapa de los miembros de un órgano (junta, consejo, superintendencia) | PDF de varias páginas | Perfilador |
| Keyreview | Resumen semanal | PDF | Kiwi + Editora |
| KeyHealth | Sinopsis mensual de un sector (salud) | PDF | Analista sectorial (futuro) |
| Keyradar | Boletín legal mensual para un cliente | PDF | Ejecutiva de cuentas |
| Keynews | Resumen diario de noticias para un cliente | Correo | Monitor de medios + Ejecutiva de cuentas |
| KeyEspecial, Keyelecciones, Keymundial | Especiales (balance del año, elecciones, internacional) | PDF | Analista político |

En Ecuador hay además 842 Keylaw guardados (caché local de KeyCurul) como modelo de estilo.

## 5. Los cimientos del cerebro (lo primero que se construye)

Siete piezas. Todo lo demás (pisos, agentes, fuentes nuevas) se enchufa a ellas sin rehacer nada.

1. **Modelo de datos.** Siete tablas comunes a todas las áreas:
   - `documentos`: todo lo que entra (ficha, norma de Gaceta, nota de prensa, transcripción, cifra del INEC), con
     fuente, URL, fecha, tipo, huella y texto completo (en R2 si es largo).
   - `fragmentos`: el texto partido en trozos para buscar (búsqueda de texto en español; vectores más adelante).
   - `entidades`: actores (personas, instituciones, comisiones, partidos, medios), instrumentos (proyectos, leyes,
     decretos, resoluciones, fallos), temas, sectores y clientes. Cada una con un id único y sus nombres alternativos.
   - `relaciones`: quién se relaciona con qué y según qué documento ("X presentó el proyecto 569", "el decreto 13
     reglamenta la ley 462", "la ministra Y habló del tema CSS en la entrevista Z").
   - `eventos`: la bitácora con fecha (lo que hoy es `eventos`, ampliado a todas las áreas).
   - `expedientes`: el resumen vivo de cada entidad (qué es, qué pasó, quién habla, qué viene) y su fecha de
     actualización.
   - `productos`: cada reporte o alerta generado, su plantilla, su estado (borrador → aprobado por la Editora →
     enviado) y las fuentes que cita.
2. **Ingesta única.** Todos los colectores guardan por la misma puerta, `guardar(documento)`: calcula la huella
   (no duplica), guarda el texto, lo parte en fragmentos y deja el documento en cola para el enlazador. El colector
   solo sabe traer; nunca analiza.
3. **Directorio de actores.** Las entidades base cargadas a mano o desde fuentes oficiales: 71 diputados, gabinete,
   autoridades, comisiones, partidos, instituciones, medios, sectores. Es el esqueleto del cerebro.
4. **Enlazador.** Lee cada documento nuevo, detecta qué entidades menciona (por nombre y alias; la IA solo cuando hay
   duda) y crea las relaciones. Es lo que convierte un montón de textos en un cerebro.
5. **Expedientes vivos.** Cuando una entidad recibe eventos nuevos, su expediente se reescribe con lo nuevo y con
   las fuentes citadas.
6. **Plantillas Keyword y Editora.** Cada producto tiene una plantilla (estructura, tono, extensión, citas) y
   ejemplos. La Editora revisa que el producto cumpla la plantilla, que cada afirmación tenga fuente y que no repita
   uno ya enviado.
7. **Turnos de agentes.** Una tabla de tareas: cada agente tiene su cobertura y su horario; toma los eventos nuevos
   de su área, produce lo que le toca y lo deja en `productos`. Así trabajan solos, sin que nadie pregunte.

Y la **puerta**: la oficina (el edificio con sus pisos), un buscador sobre todo el cerebro y Kiwi respondiendo con
citas a los documentos.

## 6. La demo (todo gratis, todo funcionando)

Objetivo: mostrar a los jefes el cerebro trabajando con datos reales de Panamá, y entregar con ella este plan de
expansión. Nada pagado.

**Dónde corre cada cosa:**

| Pieza | Herramienta gratuita |
|---|---|
| Base de datos y búsqueda | Cloudflare D1 (plan gratis: 5 GB, búsqueda de texto FTS5) |
| Textos largos | D1 o Drive (R2 solo si se puede activar gratis) |
| Oficina y API | Cloudflare Workers (plan gratis) |
| Colectores y agentes por turnos | GitHub Actions (repo público) |
| Transcripción | En la Mac: Whisper local (gratis, bueno en español) + separación de voces local |
| Análisis y redacción | Gemini nivel gratuito (se prioriza lo de la demo; se pausan los atrasados si hace falta) |
| Avisos | Telegram |

**Qué se muestra (de punta a punta, con datos reales):**
1. El edificio: pisos y agentes, qué está haciendo cada uno y qué entregó hoy.
2. Directorio: diputados y ministros con expediente vivo (proyectos, sesiones, declaraciones, enlaces).
3. Legislativo: lo que ya funciona, más **una sesión de comisión real transcrita y su reporte tipo Keylaw**.
4. Normativo: la Gaceta de la semana leída y clasificada, con alertas.
5. Político: una conferencia o entrevista transcrita, con declaraciones por actor enlazadas a su expediente.
6. Económico: últimas cifras del INEC y una nota económica automática.
7. Briefing diario de Kiwi y una pregunta en vivo que cruce áreas ("¿qué se ha dicho y hecho sobre la CSS esta
   semana?"), respondida con fuentes.

**Límites de lo gratis (se dicen en la presentación, son el argumento del plan de expansión):** la transcripción
depende de la Mac encendida; la cuota gratuita de Gemini limita cuántos documentos se analizan al día; sin vectores
la búsqueda es por palabras.

## 7. Fases después de la demo

**Fase 1 — Cimientos del cerebro.** Postgres + R2 + esquema de entidades; migrar lo legislativo actual; directorio de
actores (71 diputados, gabinete, autoridades) con expedientes; plantillas de formato Keyword; Editora; edificio
nuevo en la oficina (pisos, agentes, qué está haciendo cada uno).

**Fase 2 — Legislativo completo.** Relatora de sesiones (comisiones y Pleno en video → reporte tipo Keylaw), analista
legislativo con comparativos entre debates; se resuelve la duda de qué se discute de verdad en el Pleno.

**Fase 3 — Normativo.** Gaceta, Consejo de Gabinete, reguladores con consulta previa, Corte y Procuraduría,
Infojurídica; ciclo de vida de cada norma (borrador → consulta → aprobada → Gaceta → reformada/derogada/inconstitucional).

**Fase 4 — Político.** Agenda de autoridades, Estudio de grabación con transmisiones en vivo, monitoreo de medios y
redes, reporte político.

**Fase 5 — Económico.** Series y calendario, productos económicos automáticos.

**Fase 6 — Clientes y entrega.** Ejecutiva de cuentas, alertas y reportes por cliente, entrega directa (correo,
Telegram, Docs), panel de revisión para el equipo.

Las fases 3, 4 y 5 pueden avanzar en paralelo una vez estén los cimientos.

**Ecosistema de trabajo (pedido de Andrés, 2026-10-25; anotado, sin desarrollar).** La oficina deja de ser solo de
consulta y pasa a ser donde el equipo trabaja:
- Perfilador: crear perfiles nuevos a mano desde la oficina (nombre, cargo, lo que se sepa) y que el Perfilador los
  complete con lo que hay en el cerebro y genere el Keyperfil.
- Editor de texto en el Perfilador (y en todos los productos: Keylaw, Keymonitor, Keyperfil) para corregir y
  completar antes de enviar.
- Revisión con IA en ese editor: ortografía, gramática y tono Keyword, automática mientras se escribe y antes de
  marcar "revisado", con los cambios marcados para aceptar o rechazar. Nada sale mal escrito.
- Aprender de las correcciones: cada cambio que el equipo hace en el editor se guarda (antes/después) y se usa como
  ejemplo de tono en los siguientes reportes del mismo tipo, junto con los ejemplos reales de Keyword.
- Chat de la oficina (Andrés, 2026-10-25): UN solo chat de equipo, como el de una oficina de verdad (no uno nuevo por
  transmisión), donde están todas las personas del equipo y los agentes. Sirve para lo que se diría en voz alta
  mirando la misma pantalla: "oigan, el Presidente acaba de anunciar un nuevo impuesto, fue lo primero que dijo".
  - Las personas escriben; los agentes también escriben cuando creen que pasa algo importante, y conversan entre sí
    (p. ej. Fernando avisa un anuncio en la sesión e Inés responde si ya hay norma en la Gaceta; el Perfilador suma lo
    que ese actor dijo antes).
  - En vivo (comisiones, Pleno, entrevistas): bajar la espera de `en_vivo.py` de trozos de 5 min a 1-2 min. El agente
    escribe en el chat lo fuerte (anuncio, impuesto, nombramiento, cifra) con la hora del video, no un resumen de
    todo; lo destacado también va a Telegram.
  - Cada mensaje de una persona durante una transmisión queda pegado al minuto del video y se puede marcar destacado.
  - Kiwi está en el chat y responde ahí mismo (p. ej. "¿qué dijo de la ANATI?" con lo dicho hasta ese momento).
  - Al terminar, el Keylaw usa la transcripción más las notas y destacados del chat (que van primero).
  - Más detalles del ecosistema: los contará Andrés.
- Siguiente fase (Andrés, 2026-10-25): pedir al equipo de diseño de Keyword un SISTEMA DE DISEÑO para el Keyperfil
  (fuentes como Proxima Nova, íconos, colores, medidas). Con eso el Keyperfil queda perfecto y corre donde se necesite.
  Hoy se copia el modelo a mano (oficina /oficina/keyperfil y diseno/keyperfil.py).
- Regla a futuro (Andrés, 2026-10-25; NO hacerlo ahora): para unir lo que dice cada persona en una sesión con su
  ficha, usar la LISTA DE ASISTENCIA que se lee al inicio de cada sesión (nombres completos de los presentes) como
  lista de quiénes pueden hablar, y avisar en el perfil "hay información nueva desde la última versión" en lugar de
  rehacerlo solo (no pisar lo corregido a mano). Hoy solo 3 declaraciones de 2 sesiones calzaron con el directorio.
- Pendiente: entrenar bien el Keylaw. El formato está bien, pero el contenido todavía es "poco Keyword". Definir cómo
  (más ejemplos reales por tipo de sesión, las correcciones del equipo como ejemplos, una guía de qué incluir y qué
  no, revisión con el equipo). Se decide después con Andrés.

## 8. Qué se necesita

**De Andrés / del equipo:**
- Ejemplos reales de cada producto Keyword (mejor si son de Panamá; si no, de Ecuador) y autorización para usar los
  Keylaw de Ecuador como modelo de formato.
- Cómo trabaja hoy cada rol (qué entrega, cuándo, a quién) y la lista de clientes y sectores de Panamá.
- Cuentas: Claude API, Gemini de pago, Supabase o Neon, R2 en la cuenta de Cloudflare, VPS, y decidir el nodo en Panamá.

**De ChatGPT (investigación):** actores y perfiles; dónde y cuándo hablan las autoridades y cómo se transmiten las
sesiones de la Asamblea; jurisprudencia obligatoria y calendario económico; marco legal de grabar transmisiones y
guardar perfiles (Ley 81 de 2019, derechos de autor).

## 9. Costos estimados (mensuales, USD, precios de octubre de 2026)

Supuestos: ~250 horas al mes de transcripción (~190 de comisiones y Pleno, ~60 de entrevistas y conferencias),
~2.000 documentos de Gaceta y reguladores, ~9.000 notas de prensa, ~300 productos, ~50 consultas diarias a Kiwi.

| Rubro | Mínimo | Recomendado | Completo |
|---|---|---|---|
| Transcripción | 0 (subtítulos YouTube + Gemini gratis) | 45 (Gemini audio) | 100-150 (servicio con identificación de voces) |
| Claude: análisis, productos, Editora | 20 (Haiku + Sonnet poco) | 80-120 (Sonnet) | 200-300 (Opus en productos) |
| Kiwi (consultas) | incluido arriba | 30 | 60-90 |
| Embeddings y clasificación masiva | 0 | 5-10 | 10-20 |
| Base y archivos | 0-5 (Cloudflare) | 5 (Cloudflare) | 30 (Supabase + Cloudflare) |
| Cómputo | 0 (Actions + PC de la oficina) | 0 | 10-20 (VPS de apoyo) |
| **Total al mes** | **~25** | **~170-210** | **~410-610** |

Aparte: Mac mini para el nodo (~600 una vez) si no hay un computador disponible; plan Claude Max para desarrollo
(100-200 al mes, mientras se construye); redes sociales: la API de X es cara, se deja fuera al principio.

## 10. Riesgos

- YouTube y sitios con anti-bots bloquean IP de centros de datos → nodo en Panamá o proxy residencial.
- Gaceta: su web tiene anti-bots (Incapsula) y Legispan NO la refleja completa (0-3 normas por edición). Hace falta una
  vía legítima: canal oficial de avisos, acceso formal pedido por Keyword, o que la oficina baje las ediciones a una
  carpeta que el Vigía lee.
- Cuentas de redes de autoridades: solo las enlazadas desde sitios oficiales (riesgo de cuentas falsas).
- Identificar quién habla en una sesión es la parte difícil de la Relatora: hay que probarlo con sesiones reales.

## Mejoras anotadas (Andrés, 2026-10-25: "todo ese tipo de mejora tienes que anotarte")

- **Nombres en las transcripciones:** Whisper escucha mal los nombres (p. ej. "José Ramón Micaza" por Icaza en la
  conferencia del 22/10) y entonces lo dicho no llega al perfil. Darle a Whisper la lista de nombres del directorio
  (initial_prompt / vocabulario) y, al unir declaraciones con personas, aceptar parecidos (como en perfiles.py) además
  del alias exacto.
- **Lista de asistencia de la Asamblea** como lista de quiénes pueden hablar en cada sesión (ver arriba).
- **Paula aprende del chat real:** los chats del equipo (WhatsApp "Keyword I.E." y Telegram, en Descargas del Mac) los
  analiza ChatGPT con el prompt entregado y devuelve una guía corta (qué se manda, qué no, medios, ritmo, forma, 10
  reglas, sin nombres de clientes ni del equipo) → cargarla en el FILTRO de cerebro/monitor.py.
- **Redes sociales con el Chrome de la oficina** (visto bueno de Andrés, 2026-10-25, para pruebas con SU cuenta: "si
  la pierdo tampoco me genera tanto lío"): leer perfiles de X/Instagram de medios (invitados del día → Agenda de
  medios de Diego), del Presidente, ministros y diputados (→ Autoridades en medios) y de medios para Paula. Riesgo:
  bloqueo de la cuenta por lectura automática; luego, una cuenta de la oficina.
  HECHO X (2026-10-26, v1.6 de la extensión): dos listas PRIVADAS en la cuenta de la oficina (Medios Panamá, 13
  cuentas; Autoridades Panamá, 28) en vez de seguir cuentas (nadie ve a quién se vigila y las cuentas no reciben aviso;
  la línea de tiempo es cronológica y sin ruido). Quedan: **Instagram** (los medios anuncian invitados también ahí);
  sumar diputados con cuenta verificada (la investigación solo confirmó a Castañedas); si Gemini falla en el paso de
  Diego, esas publicaciones no se reintentan (las de Paula sí); escuchar sola la entrevista anunciada cuando el medio
  transmite en YouTube (hoy Diego solo avisa); cuentas falsas: MEFPanama, MeducaPanama y MICIPanama NO son oficiales
  (las reales: Mef_Pma, MeducaPma, MICIPMA).
- **Levantamiento en Panamá (in situ):** contratar a un periodista panameño que arme a mano la lista de medios,
  periodistas, programas y cuentas a seguir (X, Instagram, YouTube, WhatsApp), con su peso real; hoy la lista sale de
  la investigación de ChatGPT y hay huecos (diputados sin cuenta verificada, programas sin horario confirmado).
- **Paula sin ráfagas** (Andrés, 2026-10-26): HECHO. Los enlaces salen de a uno con 1 a 2,5 minutos al azar entre
  cada uno (cerebro.telegram_pausado), también los 🎙 de Diego. Las publicaciones de X de autoridades e instituciones
  que no son entrevistas van al chat si son noticia.
- **Noticieros por franja:** con la lista de noticieros y sus canales de YouTube (prompt a ChatGPT entregado), Diego
  escucha cada franja (mañana, mediodía, noche), borra lo que no tuvo nada importante y deja "lo que se dijo en los
  noticieros de la mañana" con "Reporte ampliado" por tema.
- **Keypolitics:** se borró de la oficina (Andrés, 2026-10-25); no va por ahora.
- **Chat de la oficina = un GRUPO DE TELEGRAM** (Andrés, 2026-10-25), no una pantalla nueva: ahí están el equipo y los
  agentes (el bot @keyword_panama_alertas_bot). Falta: que Andrés cree el grupo, agregue el bot y, con un mensaje en el
  grupo, sacar su chat id (getUpdates) → TELEGRAM_GRUPO en .env; Paula, Diego y Elena escriben ahí; los avisos
  personales siguen al chat de Andrés.
- **Redes con el Chrome de la oficina (cómo):** la misma extensión (extension/oficina-chrome) abre en una pestaña de
  fondo los perfiles de X de los medios (@TReporta #CaraACara, @EcoPanamaTV #RadioGrafía "Hoy nos acompaña",
  @tvnnoticias, @radiopanama, @NexNoticias, @KWCONTINENTE) y de las autoridades (lista verificada en
  Invesitgacion/…report-3 6.md), lee las publicaciones nuevas y las manda a la Mac: Diego saca invitados y
  apariciones de autoridades; Paula manda al chat el enlace del post si importa (en Ecuador el 65 % de lo compartido
  son posts de X). Requisito: sesión abierta de X (y de Instagram) en ese Chrome, con la cuenta de Andrés para pruebas.
- **Varios bots de Telegram, cada agente sabe a dónde manda** (Andrés, 2026-10-25). Bots: Alertas (el actual), Gaceta,
  Asamblea Nacional, y el CHAT GENERAL de la oficina (grupo). Ruteo: cambios de etapa de proyectos (Fernando/
  seguimiento) → bot Asamblea; algo IMPORTANTE dicho en una sesión (aviso en caliente de Fernando) → chat general;
  ediciones y normas de la Gaceta (Inés) → bot Gaceta; noticias de Paula y bolas rojas de Diego → chat general;
  Corte y reguladores → bot Alertas. Implementación: `cerebro.telegram(texto, destino="general|asamblea|gaceta|alertas")`
  con un token/chat por destino en .env (TELEGRAM_<DESTINO>_TOKEN / _CHAT); si falta uno, cae al bot actual. Los bots
  los crea Andrés en @BotFather.
- **Vista previa de los enlaces de Paula** (HECHO 2026-10-25): antes se mandaban todos los enlaces en un mensaje y con la
  vista previa APAGADA (por eso solo llegaba la URL). Ahora un mensaje por enlace con vista previa (Telegram muestra
  titular e imagen). Si algún medio no da vista previa, agregar el titular en la línea de arriba.
- **Bola roja directo al chat** (HECHO 2026-10-25): Diego manda la bola roja completa (asunto, viñetas, enlace) al chat
  apenas la escribe; en la oficina queda como "enviado" por si hay que corregirla.
- **Chat de doble vía en el grupo de Telegram** (Andrés, 2026-10-25: "un chat un poquito más inteligente"). Cambia la
  regla de 2026-10-08 (Telegram solo avisos) SOLO para el grupo de la oficina. Se le habla a un agente por su nombre o
  respondiendo a su mensaje: "Fernando, ¿dónde dijo esto?" → busca en las transcripciones (fragmentos FTS del cerebro),
  responde con la cita, quién, minuto y enlace al video en ese minuto, y adjunta la transcripción completa en .md
  (sendDocument). Responder a una bola roja o a un aviso = pregunta sobre ESA entrevista/sesión. Base: el webhook del
  Worker y el cerebro de Kiwi (`responder`) ya existen; falta: privacidad del bot apagada en @BotFather (o mencionarlo),
  aceptar solo el chat id del grupo, enrutar por nombre de agente y guardar el minuto de cada fragmento.
- **Flujo de Diego en el chat** (Andrés, 2026-10-25, corrige lo anterior): Diego escucha, detecta lo importante y manda
  al chat SOLO lo importante (avisos en caliente + resumen al terminar). La bola roja NO es automática: se pide en el
  chat respondiendo a ese mensaje ("necesito una bola roja de esto") → Diego la escribe y la manda completa al chat.
  Hasta que exista el chat de doble vía, se pide con el clic de la oficina. Al armarlo, cambiar el texto del resumen
  ("pídanla en la oficina") por "respondan a este mensaje si quieren la bola roja".
- **Memoria de anuncios: no repetir, sí avisar lo nuevo** (Andrés, 2026-10-25). Ejemplo: sábado el Presidente anuncia un
  impuesto a la banca para la reconstrucción → AVISO. Lunes lo repite "como ya se anunció" → NO se avisa. Martes lo
  retoma y da un dato nuevo (tarifa 2 % de las ventas de un año) → AVISO como novedad: "Nuevo dato sobre el impuesto
  a la banca: la tarifa será del 2 %…". Diseño: tabla `anuncios` (id, actor, tema, afirmación, detalles, fecha, fuente,
  enlace). Cada vez que Diego, Fernando o Paula van a avisar, Gemini recibe los anuncios de los últimos 30-60 días del
  mismo actor o tema (búsqueda FTS + entidades del cerebro) y clasifica cada punto: NUEVO (avisar y guardar),
  REPETIDO (no avisar; solo se suma la fuente) o NOVEDAD de un tema ya conocido (avisar SOLO lo que cambia, citando
  el anuncio anterior, y actualizar detalles). Para Paula: el mismo hecho en otro medio u otro día no se reenvía salvo
  novedad. La bola roja sí cuenta todo lo dicho, pero puede marcar "(ya anunciado el sábado)".
- **¿Cambiar Gemini por Kimi K3.1 Pro?** (Andrés, 2026-10-25). Evaluado: NO por ahora. Gemini nos cuesta $0 (nivel
  gratuito) y lee PDF escaneados directo (edictos, Gaceta); Kimi se paga por uso y su modelo abierto (2,8T) no corre
  en la Mac. Revisar si el Gemini gratis se queda corto de cuota o de calidad: ia.py ya salta de modelo en modelo y
  sumar otro proveedor como respaldo es poco trabajo (probar antes calidad en español y lectura de PDF).
- **IAs gratuitas de respaldo** (Andrés, 2026-10-25: "sí me interesa, pero al final"): sumar a ia.py y al Worker
  modelos gratuitos de otros proveedores (p. ej. OpenRouter :free, Groq) para cuando se agote la cuota gratis de
  Gemini. Nunca nombres de clientes. Probar antes calidad en español. Va al FINAL de la lista.
- **Coordinación económica: qué se automatiza** (Andrés, 2026-10-25: lo analítico necesita un cerebro humano, como
  Keypolitics; lo regular y de formato fijo, sí). Los 5 Keyeconomics de ejemplo son DESCRIPTIVOS con plantilla fija:
  "Estimados, Ponemos en su conocimiento… publicados por <institución>… - viñetas con cifras… Saludos cordiales", a
  veces con un reporte en línea (Notion) con gráficos.
  · AUTOMÁTICO (cifra con fecha y formato fijo): IPC/inflación (mensual), IMAE (mensual), PIEM: comercio exterior, ZLC,
    Canal, puertos, construcción (mensual), PIB trimestral, balanza de pagos/IED (trimestral), empleo EML (2 veces al
    año), deuda pública MEF (mensual), combustibles (Secretaría de Energía; verificar ritmo). Agente "Cifras": vigila el
    calendario del INEC, baja el Excel/CSV, compara con el dato anterior, avisa al chat y deja el Keyeconomics en
    borrador para revisar (como Keymonitor; no sale al cliente sin visto bueno).
  · SEMIAUTOMÁTICO (evento con la misma plantilla, borrador para revisar): decretos/resoluciones con efecto económico
    (impuestos, IVA, aranceles) que detecta Inés en la Gaceta; acciones de calificadoras; FMI Artículo IV; informes
    anuales oficiales (estabilidad financiera, Informe Económico y Social del MEF).
  · HUMANO (no se automatiza): perspectivas, escenarios, lectura del presupuesto, implicaciones por cliente.
  Técnico (2026-10-25): la página de indicadores del INEC (avance/Default2.aspx) responde sin anti-bots y lista PDF,
  XLS y CSV con la fecha y hora en el nombre del archivo (A…20261016131132PIEM_agosto_2026.pdf): fácil detectar lo
  nuevo. Trae también el "comentario" del INEC en PDF (texto listo para resumir).
  Pedir a Andrés más Keyeconomics reales (inflación, empleo, deuda) para entrenar el tono de cada cifra.
- **Keyeconomics reales bajados** (2026-10-25, correo de Keyword en solo lectura con microsoft.py del proyecto de
  Ecuador): 78 correos distintos (nov-2024 a oct-2026) en ejemplos/keyword/Keyeconomics/ (.txt + .html; no se suben).
  Reparto: empleo mensual 20, comercio/aranceles/acuerdos 12, IVA por feriado 9, PIB 8, combustibles 7 (mensual desde
  abr-2026), FMI 6, empleo trimestral/anual 3, previsiones del Banco Central 3, presupuesto 3, análisis/impacto 3,
  otros 4. Plantillas CASI IDÉNTICAS mes a mes en empleo, combustibles, PIB e IVA por feriado (cambian solo cifras y
  fechas; un correo real de empleo de marzo dice "febrero": la automatización evita ese error). Presupuesto,
  análisis/impacto y comercio internacional = análisis humano (PDF propio). FMI y previsiones = semiautomático.
  Equivalentes en Panamá: empleo → EML del INEC (2 veces al año, no mensual); PIB → INEC trimestral; combustibles →
  Secretaría de Energía; IVA por feriado → no aplica (en Panamá sería ITBMS u otras medidas por decreto, vía Gaceta).
- **Pases entre agentes, a la vista en el chat** (Andrés, 2026-10-25). Ej.: Inés detecta en la Gaceta un decreto de
  impacto económico → escribe en el chat del equipo "Decreto Ejecutivo N.º X: <qué hace>. Se lo pasé a Tomás para el
  Keyeconomics (correo) y a Diego para la bola roja (aviso al celular)" → cada uno deja su borrador y avisa cuando
  está. Tabla `pases` (de, para, producto, origen, estado). Reglas: la Gaceta/reguladores/Corte con efecto económico →
  Tomás; cualquier cosa de impacto alto → bola roja.
  Y AL REVÉS: aunque el agente no lo haya marcado importante, cualquiera en el chat puede responder a su mensaje
  "pásenme la bola roja" / "arma el Keyeconomics de esto" y el agente que corresponde lo arma con ESE documento y lo
  manda al chat. La bola roja deja de ser solo de entrevistas: es un formato que cualquier agente puede pedir
  (decreto, fallo, resolución, cifra). Necesita el chat de doble vía (ver arriba).
- Nombre del economista (ficticio): **Tomás · Cifras y Keyeconomics**.
- **Regla de revisión** (Andrés, 2026-10-25): lo que va por CORREO (Keyeconomics, Keymonitor, Keylaw) NUNCA se revisa
  en el chat: el agente solo avisa "ya está el reporte en la plataforma para revisión". La BOLA ROJA sí llega completa
  al chat para revisión.
- **Límite de D1 agotado** (2026-10-25): 170.000 escrituras (límite gratis 100.000/día, se reinicia 00:00 UTC = 19:00
  Panamá). Causa: base.sincronizar reescribía TODOS los proponentes de cada ficha tocada (150.000). Arreglo subido a
  GitHub (solo base.py, con permiso de Andrés): ahora compara con lo que hay en D1 y escribe solo la diferencia.
  Vigilar el consumo con la API GraphQL de Cloudflare (d1QueriesAdaptiveGroups, sum.rowsWritten por consulta).
- **Pases Inés → Tomás / Diego** (HECHO 2026-10-25, cerebro/pases.py; probar con la próxima Gaceta): al leer cada
  edición, Gemini marca si la norma es "economica" (impuestos, tarifas, aranceles, precios, presupuesto, deuda, salario
  mínimo, subsidios, incentivos). Económica + impacto alto/medio → pase a Tomás (Keyeconomics en borrador; chat: "ya
  está en la plataforma para revisión"). Impacto alto → pase a Diego (bola roja completa al chat "para revisión").
  El aviso de Inés en el chat dice "➡️ Decreto X: se lo pasé a Tomás… y a Diego…". Tabla `pases` + tarea en la mesa
  del que recibe (keyeconomics_norma / bola_norma). Siguiente: pases de Mateo y Elena; pedir pases desde el chat.
- **Que no vuelva el bloqueo de D1** (Andrés, 2026-10-25: "guárdalo"): 1) proponentes solo diferencias (HECHO, subido);
  2) prensa.py: agenda_fichas igual, solo diferencias (~21.000 escrituras/día; necesita permiso para subir a GitHub);
  3) alarma en la mesa: cada hora suma rowsWritten del día (GraphQL de Cloudflare); >60.000 aviso por Telegram,
  >85.000 pausa latidos y monitor_vistos de lo no enviado; 4) RECOMENDADO: Workers Paid (~USD 5/mes, ~50 M escrituras/mes;
  confirmar precio en Cloudflare); lo activa Andrés en el panel (pide tarjeta).

## Hecho la noche del 2026-10-26 (detalle en CLAUDE.md)

- Chat de doble vía en los tres grupos (cerebro/chat.py): se le habla a un agente por su nombre o respondiéndole.
  Solo la bola roja llega completa al chat; Keylaw, Keyeconomics y transcripciones avisan que están en la oficina.
- Memoria de anuncios (cerebro/anuncios.py): no repetir, sí avisar lo nuevo. Paula no reenvía el mismo hecho.
- Pases de Mateo (reguladores) y Elena (Corte) a Tomás y Diego.
- En vivo cada 2 minutos, con el minuto y el enlace al video en ese momento.
- Kiwi revisa (cerebro/editora.py): función interna de Kiwi; cada reporte se corrige contra sus fuentes antes de
  llegar a la oficina. Sin probar con éxito todavía (Gemini 3.8 con 503/timeout esa noche).
- Kiwi: vida de la ley después de la Asamblea y tiempos de trámite (solo preguntando, sin botón).
- Oficina nueva publicada (escena_entrada + mapa del cerebro servido por el Worker).
- Equipo dedicado (Andrés, 2026-10-26): PC con Linux (Ubuntu) y NVIDIA (RTX 4070 / 4060 Ti 16 GB, 32 GB RAM) en
  lugar del MacBook Air; Whisper → faster-whisper; mesa y receptor como servicios. Detalle en presentacion/notas.md.

- 2026-10-26: botón «Ver sesión» en cada sesión de hoy (enlace a la transmisión de YouTube; config canal_asamblea que anota la mesa; sin transmisión abre el canal).

## Hecho el 2026-10-27

- **Agenda desde X** (Andrés: "hay más agenda hoy"): la web de la Asamblea traía 4 de las 8 sesiones del día y la de
  Comercio con 2 de sus 4 puntos; @asambleapa publica la agenda completa en IMÁGENES. `cerebro/agenda_x.py`: la
  extensión v1.8 manda las fotos de cada post, el receptor encola los de @asambleapa con fotos, la mesa (cada 5 min)
  le pasa las imágenes a Gemini y suma a `agenda` lo que la web no tiene; Telegram (Asamblea) avisa qué se agregó.

## PC de la oficina (aprobada el 28/10/2026)

Reemplaza a la PC con Linux propuesta en la presentación. Windows 11 Pro, Intel Core Ultra 7 265K, 64 GB de RAM,
RTX 5080 de 16 GB, un disco de 1,82 TB (606 GB ya usados: preguntar qué son).
- Second brain en WSL2 (CUDA funciona ahí), NO en una VM de Hyper-V: en Windows 11 Pro Hyper-V no le pasa bien la
  NVIDIA a una VM y Whisper quedaría en el procesador. Chrome de la oficina + extensión en Windows; habla con el
  receptor por 127.0.0.1.
- Whisper: de mlx-whisper (Mac) a faster-whisper sobre NVIDIA (mismo large-v3-turbo). Mesa, receptor y vigilante como
  servicios que arrancan solos: inicio de sesión automático + tarea programada; suspensión apagada; actualizaciones de
  Windows en horario fijo de madrugada; UPS. Solo servidor (nadie la usa a diario); escritorio remoto para los
  «Soy humano».
- Lo administrativo (propuesta de la oficina, modelo local): cuenta de Windows aparte + BitLocker; la tarjeta no se
  divide entre espacios aislados: si se exige aislamiento total con modelo local, otra máquina. Modelo local de 8-14 B
  (bastante más débil que Gemini; comparte la tarjeta con Whisper).
- Respaldo: lo crítico es `.env` y `salidas/` (la base está en Cloudflare, documentos en Drive, código en GitHub).
- Un día de trabajo para pasarlo y probarlo.

## Límite de D1 (27/10/2026)

En la demo la oficina mostró la mesa "apagada": el proceso vivía, pero D1 llegó al límite diario de escrituras del plan
gratis (error 7500) y no se guardaba nada hasta las 00:00 UTC. Solución: Workers Paid (USD 5/mes) en la cuenta
agentemonitoreopa (lo hace Andrés).
