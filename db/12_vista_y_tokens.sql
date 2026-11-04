-- =====================================================================
-- Dos cosas que conviene hacer antes de poder eliminar desde el panel
--
-- 1. LAS 1000 FILAS. Supabase corta toda consulta de su API en 1000
--    filas y no avisa: devuelve mil renglones como si fueran todos. El
--    panel traía las etapas en su propia consulta, cinco renglones por
--    mueble, sin filtro. Con 45 muebles son 225; a los 200 muebles se
--    llega a mil y el tablero empezaría a mostrar palomitas incompletas
--    en silencio. Ahora las cinco palomitas viajan dentro de v_muebles,
--    un renglón por mueble: el techo se mueve de ~200 a ~1000 muebles y
--    baja a la mitad lo que carga el navegador.
--
-- 2. UN LINK POR PERSONA. Hasta hoy todo cambio hecho en el panel se
--    anotaba como tú, porque el panel sólo conocía un token. Cada
--    persona de `personas` recibe el suyo: la bitácora deja de mentir y
--    un link se puede revocar sin tocar los demás.
--
-- Ejecutar después de 11_crear.sql. Se puede volver a correr.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Las palomitas, dentro de la vista.
--
-- Se arma desde el catálogo `etapas` con left join, no desde
-- mueble_etapas directo: así el arreglo siempre trae cinco en el orden
-- del catálogo, aunque a un mueble le faltara un renglón.
--
-- La columna nueva va AL FINAL a propósito: Postgres no permite
-- reordenar ni renombrar las columnas de una vista con CREATE OR
-- REPLACE, y hay funciones que dependen de ésta.
-- ---------------------------------------------------------------------
create or replace view v_muebles as
select
  m.id,
  m.nombre,
  m.grupo,
  m.medidas,
  m.nota,
  m.orden,
  m.archivado,
  m.fecha_entrega,
  m.updated_at,
  o.id      as obra_id,
  o.nombre  as obra,
  o.estado  as obra_estado,
  round((
    (select count(*) from mueble_etapas me where me.mueble_id = m.id and me.hecho)
    + case when m.terminado then 1 else 0 end
  )::numeric / 6, 3)::numeric(4,3) as avance,
  (
    select e.nombre from mueble_etapas me
    join etapas e on e.id = me.etapa_id
    where me.mueble_id = m.id and me.hecho
    order by e.orden desc limit 1
  ) as en,
  (
    select e.nombre from mueble_etapas me
    join etapas e on e.id = me.etapa_id
    where me.mueble_id = m.id and not me.hecho
    order by e.orden asc limit 1
  ) as sigue,
  m.terminado,
  (m.fecha_entrega is not null
    and m.fecha_entrega < current_date
    and not m.terminado) as atrasado,
  (current_date - m.updated_at::date) as dias_sin_movimiento,
  (
    (select count(*) from mueble_etapas me where me.mueble_id = m.id and me.hecho)
    + case when m.terminado then 1 else 0 end
  )::int as pasos_hechos,
  (
    select array_agg(coalesce(me.hecho, false) order by e.orden)
    from etapas e
    left join mueble_etapas me on me.etapa_id = e.id and me.mueble_id = m.id
  ) as etapas
from muebles m
join obras o on o.id = m.obra_id;

-- ---------------------------------------------------------------------
-- 2. Un token por persona.
--
-- 32 caracteres hexadecimales: sin '+' ni '/' que haya que escapar en
-- la URL, y suficientemente largo para que no se adivine.
-- ---------------------------------------------------------------------
alter table personas add column if not exists token text;

create unique index if not exists personas_token_uk on personas (token)
  where token is not null;

update personas set token = encode(gen_random_bytes(16), 'hex')
 where token is null;

-- Quién trae ese link. Devuelve nada si el token no existe o la persona
-- está desactivada — desactivar a alguien le cierra el panel.
create or replace function persona_por_token(p_token text)
returns table (id uuid, nombre text, rol text)
language sql stable as $$
  select p.id, p.nombre, p.rol
  from personas p
  where p.token = p_token and p.activo
  limit 1;
$$;

-- Para copiar los links. Corre esto en el SQL Editor y reparte uno a
-- cada quien; nunca los mandes todos en el mismo mensaje.
create or replace function links_del_panel()
returns table (nombre text, rol text, telefono text, activo boolean, token text)
language sql stable as $$
  select p.nombre, p.rol, p.telefono, p.activo, p.token
  from personas p order by p.rol, p.nombre;
$$;

-- Si un link se filtra: cambia ese y nada más.
create or replace function renovar_token(p_persona_id uuid)
returns text
language plpgsql as $$
declare v_token text;
begin
  v_token := encode(gen_random_bytes(16), 'hex');
  update personas set token = v_token where id = p_persona_id;
  if not found then raise exception 'No existe esa persona'; end if;
  return v_token;
end $$;

-- ---------------------------------------------------------------------
-- Catálogo.
-- ---------------------------------------------------------------------
create or replace function funciones_del_asistente()
returns table (nombre text)
language sql stable as $$
  select p.proname::text
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname in (
      'buscar_mueble', 'buscar_pendiente', 'resumen',
      'actualizar_etapa', 'marcar_terminado', 'reiniciar_mueble',
      'poner_nota', 'crear_mueble', 'fijar_fecha', 'agregar_pendiente',
      'cerrar_pendiente', 'deshacer',
      'renombrar_mueble', 'renombrar_grupo', 'editar_obra', 'editar_cotizacion',
      'crear_obra', 'agregar_mueble', 'agregar_pendiente_en',
      'pendiente_de_oficina', 'crear_cotizacion',
      'persona_por_token', 'links_del_panel', 'renovar_token'
    )
  order by 1;
$$;
