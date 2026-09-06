# Asistente de obra — Grupo Morales

Operar el plan de proceso y entrega desde WhatsApp: reportar avance con lenguaje
natural, pedir resúmenes y recibir el tablero como imagen.

## Estado

- [x] **Fase 0** — Esquema de datos y carga del panel actual (`db/`)
- [ ] **Fase 1** — Bot que entiende y actualiza
- [ ] **Fase 2** — Número propio y el taller adentro
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
6. `python3 -m venv .venv && source .venv/bin/activate`
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
