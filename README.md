# Asistente de obra — Grupo Morales

Operar el plan de proceso y entrega desde WhatsApp: reportar avance con lenguaje
natural, pedir resúmenes y recibir el tablero como imagen.

## Estado

- [x] **Fase 0** — Esquema de datos y carga del panel actual (`db/`)
- [x] **Fase 1** — Bot que entiende y actualiza
- [~] **Fase 2** — WhatsApp conectado (sandbox de Twilio)
- [ ] **Fase 3** — Imagen del tablero
- [ ] **Fase 4** — Voz y avisos automáticos

## Cómo está armado el dato

Un mueble **no** guarda una etapa ni un porcentaje: guarda cinco palomas
independientes en `mueble_etapas`, igual que el panel. El avance se calcula
sumando los pesos de las etapas palomeadas, así que si algún día cambian las
etapas o los pesos nada queda inconsistente. Cada paloma guarda además cuándo se
marcó y quién la reportó — de ahí saldrá saber cuánto tarda realmente cada etapa.

`bitacora` guarda el antes, el después y el mensaje de WhatsApp que provocó cada
cambio. De ahí sale `deshacer` y de ahí sale saber quién reportó qué.

`v_muebles` es la vista de la que leen el tablero, los resúmenes y la imagen.
Trae obra, avance, en qué etapa va, cuál sigue, si está terminado, si está
atrasado y cuántos días lleva sin moverse.

`obras` incluye las obras con muebles (Silver Deer, Bosque Real, Varios), las que
solo tienen pendientes (Ahuehuetes, Pepe Simón, Liliana…) y una obra `interna`
llamada Oficina para lo que no es de cliente.

## Qué trae el seed

Sale del export del panel del 2 de septiembre de 2026: 14 obras, 45 muebles con
sus 142 etapas ya palomeadas, 20 pendientes y 1 cotización. Los 45 avances se
verificaron uno por uno contra la columna AVANCE % del CSV.

## Arrancar (Fase 0)

1. Crear un proyecto en [supabase.com](https://supabase.com) — plan gratis,
   región `us-east-1`. Guarda la contraseña de la base.
2. SQL Editor → pegar y correr `db/01_schema.sql`.
3. SQL Editor → pegar y correr `db/02_seed.sql`.
4. Settings → API → copiar `Project URL` y la llave `service_role`.
5. `cp .env.example .env` y llenar esas dos variables.
6. `/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate`
   (el Python 3.9 que trae macOS rompe las librerías compiladas — usa el de Homebrew)
7. `pip install -r requirements.txt`
8. `python check_db.py` — debe imprimir el tablero completo.

Los dos SQL son idempotentes: se pueden volver a correr sin duplicar nada.
Cuando el paso 8 imprima el tablero, la Fase 0 está terminada.

## Lo que falta poner a mano

En `db/02_seed.sql`, la tabla `personas` trae un teléfono de relleno
(`+520000000000`). Cámbialo por el tuyo en formato E.164 y agrega ahí a las
personas del taller cuando tengas sus números — un número que no esté en esa
tabla no puede leer ni escribir nada.

## Seguridad

Las tablas tienen RLS activo y **sin políticas**, o sea que ninguna llave pública
puede leer nada. El backend usa la llave `service_role`, que se salta RLS.
Esa llave nunca sale del servidor y nunca se sube a git.


## Fase 1 — el asistente

`db/03_funciones.sql` son las operaciones que el asistente puede ejecutar.
El modelo **no escribe SQL**: llama a estas funciones, que ya traen adentro la
búsqueda difusa (sin acentos, por texto parcial), la validación y el registro en
bitácora. Buscar y escribir están separados a propósito — el asistente busca,
ve los candidatos, y sólo entonces escribe usando un id. Así nunca le pega al
mueble equivocado por una coincidencia parcial.

    app/herramientas.py   las 9 herramientas y cómo se ejecutan
    app/agente.py         el ciclo mensaje → Claude → herramientas → respuesta
    app/main.py           el servidor que recibe los webhooks de Twilio
    app/whatsapp.py       mandar mensajes por Twilio
    probar.py             probar todo desde la terminal, sin WhatsApp

### Probarlo sin WhatsApp

1. SQL Editor de Supabase → correr `db/03_funciones.sql`.
2. Elegir proveedor en el `.env`. Por defecto viene OpenAI:

       PROVEEDOR=openai
       OPENAI_API_KEY=sk-...
       MODELO=gpt-4o

   `app/llm.py` tiene las dos rutas de tool use que existen hoy: la de
   Anthropic y la de OpenAI — que también usan DeepSeek, Groq, Gemini,
   Mistral y xAI. Para uno de esos, deja `PROVEEDOR=openai` y sólo cambia
   `BASE_URL` y `MODELO`. Para volver a Claude, `PROVEEDOR=anthropic`.
   El resto del código no sabe con qué modelo está hablando.
3. En Supabase, tabla `personas`: cambiar el teléfono de relleno por el tuyo
   en formato E.164 (`+52` + 10 dígitos).
4. `python probar.py`

Se abre una conversación en la terminal contra la base real. Cosas que probar:

    cómo va bosque real
    ya salió de barniz el mob 6 de silver deer
    no, deshaz eso
    qué tengo pendiente de liliana
    el escritorio de fátima se entrega el 20 de septiembre

Si el modelo configurado ya no existe, `python probar.py --modelos` lista los
que tu cuenta puede usar; el que elijas va en `MODELO` del `.env`.

Cuando esto conteste bien en la terminal, conectarlo a WhatsApp es sólo apuntar
el webhook de Twilio a `/whatsapp` — la lógica es exactamente la misma.


## Fase 2 — conectarlo a WhatsApp

Twilio corta el webhook a los ~15 segundos y el asistente puede tardar más
cuando encadena varias herramientas. Por eso `/whatsapp` contesta vacío de
inmediato y manda la respuesta real por la API de Twilio, en segundo plano.
El webhook además verifica la firma `X-Twilio-Signature`: la URL queda
expuesta a internet y sin esa verificación cualquiera que la descubra podría
mover muebles en el tablero.

### Levantarlo

1. Crear cuenta en [twilio.com](https://twilio.com) (el sandbox es gratis).
2. Console → Messaging → Try it out → **Send a WhatsApp message**.
   Ahí sale un número y un código tipo `join algo-algo`. Mándalo por WhatsApp
   desde tu celular a ese número: así te unes al sandbox.
3. Instalar ngrok y abrir un túnel a tu Mac:

       brew install ngrok
       ngrok http 8000

   Copia la URL `https://xxxx.ngrok-free.app` que te da.
4. En el `.env`:

       TWILIO_ACCOUNT_SID=AC...
       TWILIO_AUTH_TOKEN=...
       TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
       URL_PUBLICA=https://xxxx.ngrok-free.app/whatsapp

5. En Twilio, en la config del sandbox, campo **"When a message comes in"**:
   pegar esa misma URL con `/whatsapp` al final, método POST.
6. Levantar el servidor:

       uvicorn app.main:app --reload --port 8000

7. Mandar un WhatsApp al número del sandbox: *cómo va silver deer*

### Cosas que se sienten como bugs y no lo son

- **La sesión del sandbox expira a los 3 días.** Hay que volver a mandar el
  `join`. Es del sandbox, no del código.
- **ngrok cambia de URL cada vez que lo reinicias.** Hay que actualizar
  `URL_PUBLICA` y el webhook en Twilio. Cuando esto ya sirva a diario,
  conviene desplegarlo en Railway y olvidarse del túnel.
- **Si la firma no cuadra** y todo lo demás está bien, casi siempre es que
  `URL_PUBLICA` no es idéntica a la que pusiste en Twilio (`http` vs `https`,
  una diagonal de más, o el `/whatsapp` faltante).
