# Agente Panamá — monitor legislativo de Keyword para la Asamblea Nacional de Panamá

Versión para la oficina de Panamá de KeyCurul (Ecuador, `../Agente Zimbra AN`, repo `wlozano98-dotcom/agente-asamblea`).
Proyecto APARTE (decisión de Andrés, 2026-10-08): cuentas, repo, base, bot y oficina propios. Se copia de KeyCurul lo que
sirva, pero no se comparte código ni datos. Alcance: todo lo de KeyCurul (alertas, matriz, D1, oficina con Kiwi, bot).

## Reglas

- Solo información PÚBLICA: no hay correo de la Asamblea ni reportes tipo Keylaw del equipo de Panamá.
- Los nombres de clientes nunca se envían a Gemini: Gemini marca sectores y el cruce con clientes es local.
- Sectores: los mismos 13 de Ecuador (clientes de Panamá se agregan después).
- Claves solo en `.env` (no se sube). Si una clave pasa por el chat, anotarla para rotarla.

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
- **Orden del Día del Pleno**: https://www.asamblea.gob.pa/Page/LABORLEGISLATIVA/OrdenDelDia, PDF diario en
  /Uploads/OrdenDia/<id>/…pdf. El sitio www.asamblea.gob.pa tiene anti-bots F5 (TSPD): curl falla; hará falta navegador.
- No sirven: Agenda de Comisiones (abandonada desde julio de 2024) y votaciones de prensa507 (vacías).

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
