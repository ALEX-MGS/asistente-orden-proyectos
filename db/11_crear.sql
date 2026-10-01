-- =====================================================================
-- Edición desde el panel · tanda 2: dar de alta
--
-- Crear obras, muebles, grupos, pendientes y cotizaciones. Nada borra.
--
-- Dos cosas que cambian de fondo:
--
-- 1. obras.es_proyecto. El tablero muestra como proyecto a una obra que
--    tenga muebles. Eso basta hoy porque todas los tienen, pero en el
--    momento en que puedas crear un proyecto desde el panel, uno sin
--    muebles todavía desaparecería al recargar. Esta bandera dice
--    "ésta es un proyecto aunque esté vacía". Las obras que sólo
--    llevan pendientes —arq hugo, Laredo, Oficina— siguen fuera de las
--    pestañas de proyecto, que es como lo tienes hoy.
--
-- 2. Las funciones de alta ahora reciben el id de la obra, no su
--    nombre. Por WhatsApp el nombre está bien porque la persona escribe
--    "en Silver Deer"; desde el panel el id ya se conoce y buscar por
--    nombre parecido es justo lo que hizo que un cambio acabara en la
--    obra equivocada. Las versiones por nombre se quedan: ahora llaman
--    a las de id.
--
-- Ejecutar después de 10_edicion.sql. Se puede volver a correr.
-- =====================================================================

alter table obras add column if not exists es_proyecto boolean not null default false;

-- Las que ya tienen muebles son proyectos desde siempre.
update obras o set es_proyecto = true
 where not o.es_proyecto
   and exists (select 1 from muebles m where m.obra_id = o.id);

-- ---------------------------------------------------------------------
-- Alta de obra.
-- ---------------------------------------------------------------------
create or replace function crear_obra(
  p_nombre   text,
  p_fecha    date default null,
  p_proyecto boolean default false,
  p_tipo     text default 'obra',
  p_persona  uuid default null,
  p_mensaje  text default null
) returns jsonb
language plpgsql as $$
declare v_id uuid;
begin
  p_nombre := nullif(btrim(coalesce(p_nombre, '')), '');
  if p_nombre is null then raise exception 'La obra necesita un nombre'; end if;

  if exists (select 1 from obras where norm(nombre) = norm(p_nombre)) then
    raise exception 'Ya hay una obra con ese nombre';
  end if;

  insert into obras (nombre, fecha_entrega, es_proyecto, tipo,
                     orden)
  values (p_nombre, p_fecha, coalesce(p_proyecto, false), coalesce(p_tipo, 'obra'),
          coalesce((select max(orden) + 1 from obras), 1))
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'crear_obra', 'obras', v_id,
          jsonb_build_object('nombre', p_nombre, 'fecha_entrega', p_fecha,
                             'es_proyecto', coalesce(p_proyecto, false)),
          p_mensaje);

  return jsonb_build_object('id', v_id, 'nombre', p_nombre);
end $$;

-- Resuelve una obra por nombre parcial y la crea si no existe. Si la
-- crea, deja su propia entrada en bitácora con el mismo mensaje, para
-- que deshacer se lleve también la obra que nació de paso.
create or replace function obra_o_crear(
  p_obra    text,
  p_persona uuid default null,
  p_mensaje text default null
) returns uuid
language plpgsql as $$
declare v_id uuid;
begin
  select id into v_id from obras
   where norm(nombre) like '%' || norm(p_obra) || '%'
   order by length(nombre) limit 1;
  if v_id is not null then return v_id; end if;

  return ((crear_obra(p_obra, null, false, 'obra', p_persona, p_mensaje)) ->> 'id')::uuid;
end $$;

-- ---------------------------------------------------------------------
-- Alta de mueble. El trigger del esquema le pone sus cinco etapas.
-- ---------------------------------------------------------------------
create or replace function agregar_mueble(
  p_obra_id uuid,
  p_nombre  text,
  p_grupo   text default null,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_id uuid; v_res jsonb;
begin
  p_nombre := nullif(btrim(coalesce(p_nombre, '')), '');
  p_grupo  := nullif(btrim(coalesce(p_grupo, '')), '');
  if p_nombre is null then raise exception 'El mueble necesita un nombre'; end if;
  if not exists (select 1 from obras where id = p_obra_id) then
    raise exception 'No existe esa obra';
  end if;

  if exists (
    select 1 from muebles
     where obra_id = p_obra_id and norm(nombre) = norm(p_nombre)
       and norm(coalesce(grupo, '')) = norm(coalesce(p_grupo, ''))
  ) then
    raise exception 'Ya existe un mueble con ese nombre en esa obra';
  end if;

  insert into muebles (obra_id, nombre, grupo, orden)
  values (p_obra_id, p_nombre, p_grupo,
          coalesce((select max(orden) + 1 from muebles where obra_id = p_obra_id), 1))
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'crear_mueble', 'muebles', v_id,
          jsonb_build_object('obra_id', p_obra_id, 'nombre', p_nombre, 'grupo', p_grupo),
          p_mensaje);

  select to_jsonb(v) into v_res
  from (select id, obra, grupo, nombre, avance from v_muebles where id = v_id) v;
  return v_res;
end $$;

-- La versión por nombre, que es la que usa WhatsApp.
create or replace function crear_mueble(
  p_obra    text,
  p_nombre  text,
  p_grupo   text default null,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
begin
  return agregar_mueble(obra_o_crear(p_obra, p_persona, p_mensaje),
                        p_nombre, p_grupo, p_persona, p_mensaje);
end $$;

-- ---------------------------------------------------------------------
-- Alta de pendiente.
-- ---------------------------------------------------------------------
create or replace function agregar_pendiente_en(
  p_obra_id uuid,
  p_texto   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_id uuid;
begin
  p_texto := nullif(btrim(coalesce(p_texto, '')), '');
  if p_texto is null then raise exception 'El pendiente necesita un texto'; end if;
  if not exists (select 1 from obras where id = p_obra_id) then
    raise exception 'No existe esa obra';
  end if;

  insert into pendientes (obra_id, texto) values (p_obra_id, p_texto)
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'agregar_pendiente', 'pendientes', v_id,
          jsonb_build_object('obra_id', p_obra_id, 'texto', p_texto), p_mensaje);

  -- Se devuelve también la obra: el panel necesita su id para colgarle
  -- más pendientes cuando la obra acaba de nacer con éste.
  return jsonb_build_object(
    'id', v_id,
    'obra_id', p_obra_id,
    'obra', (select nombre from obras where id = p_obra_id),
    'texto', p_texto);
end $$;

create or replace function agregar_pendiente(
  p_obra    text,
  p_texto   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
begin
  return agregar_pendiente_en(obra_o_crear(p_obra, p_persona, p_mensaje),
                              p_texto, p_persona, p_mensaje);
end $$;

-- Los de oficina no cuelgan de una obra de cliente: van a la obra
-- interna, la que el tablero muestra en su propia pestaña.
create or replace function pendiente_de_oficina(
  p_texto   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_id uuid;
begin
  select id into v_id from obras where tipo = 'interna' order by created_at limit 1;
  if v_id is null then
    insert into obras (nombre, tipo) values ('Oficina', 'interna') returning id into v_id;
    insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
    values (p_persona, 'crear_obra', 'obras', v_id,
            jsonb_build_object('nombre', 'Oficina', 'es_proyecto', false), p_mensaje);
  end if;
  return agregar_pendiente_en(v_id, p_texto, p_persona, p_mensaje);
end $$;

-- ---------------------------------------------------------------------
-- Alta de cotización. El monto entra como texto porque así sale del
-- formulario del panel: vacío significa "todavía no sé cuánto".
-- ---------------------------------------------------------------------
create or replace function crear_cotizacion(
  p_cliente  text,
  p_concepto text default null,
  p_monto    text default null,
  p_fecha    text default null,
  p_persona  uuid default null,
  p_mensaje  text default null
) returns jsonb
language plpgsql as $$
declare v_id uuid;
begin
  p_cliente := nullif(btrim(coalesce(p_cliente, '')), '');
  if p_cliente is null then raise exception 'La cotización necesita un cliente'; end if;

  insert into cotizaciones (cliente, concepto, monto, fecha)
  values (p_cliente,
          nullif(btrim(coalesce(p_concepto, '')), ''),
          nullif(btrim(coalesce(p_monto, '')), '')::numeric(12,2),
          nullif(btrim(coalesce(p_fecha, '')), '')::date)
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'crear_cotizacion', 'cotizaciones', v_id,
          jsonb_build_object('cliente', p_cliente, 'concepto', p_concepto), p_mensaje);

  return (select to_jsonb(v) from (select id, cliente, concepto, monto, fecha, estado, nota
                                   from cotizaciones where id = v_id) v);
end $$;

-- ---------------------------------------------------------------------
-- Deshacer aprende las altas nuevas.
-- ---------------------------------------------------------------------
create or replace function revertir_entrada(b bitacora)
returns boolean
language plpgsql as $$
declare e jsonb;
begin
  if b.accion = 'actualizar_etapa' then
    update mueble_etapas set hecho = (b.antes ->> 'hecho')::boolean
     where mueble_id = b.registro_id and etapa_id = (b.antes ->> 'etapa_id')::smallint;

  elsif b.accion in ('reiniciar_mueble', 'marcar_terminado') then
    if b.antes ? 'etapas' then
      for e in select * from jsonb_array_elements(b.antes -> 'etapas') loop
        update mueble_etapas set hecho = (e ->> 'hecho')::boolean
         where mueble_id = b.registro_id and etapa_id = (e ->> 'etapa_id')::smallint;
      end loop;
    end if;
    update muebles set terminado = (b.antes ->> 'terminado')::boolean
     where id = b.registro_id;

  elsif b.accion = 'poner_nota' then
    update muebles set nota = b.antes ->> 'nota' where id = b.registro_id;

  elsif b.accion = 'crear_mueble' then
    delete from muebles where id = b.registro_id;

  elsif b.accion = 'fijar_fecha' then
    update muebles set fecha_entrega = (b.antes ->> 'fecha_entrega')::date
     where id = b.registro_id;

  elsif b.accion = 'agregar_pendiente' then
    delete from pendientes where id = b.registro_id;

  elsif b.accion = 'cerrar_pendiente' then
    update pendientes set hecho = (b.antes ->> 'hecho')::boolean,
           hecho_at = case when (b.antes ->> 'hecho')::boolean then hecho_at else null end
     where id = b.registro_id;

  elsif b.accion = 'renombrar_mueble' then
    update muebles set nombre = b.antes ->> 'nombre' where id = b.registro_id;

  elsif b.accion = 'renombrar_grupo' then
    update muebles set grupo = b.antes ->> 'grupo'
     where obra_id = b.registro_id
       and coalesce(grupo, '') = coalesce(b.despues ->> 'grupo', '');

  elsif b.accion = 'editar_obra' then
    perform aplicar_obra(b.registro_id, b.antes);

  elsif b.accion = 'editar_cotizacion' then
    perform aplicar_cotizacion(b.registro_id, b.antes);

  -- --- nuevas de 11_crear.sql ---
  elsif b.accion = 'crear_obra' then
    -- Sólo si sigue vacía. Si en el rato que pasó ya le colgaron
    -- muebles o pendientes, borrarla se los llevaría de corbata: mejor
    -- que deshacer diga que eso ya no se puede.
    if exists (select 1 from muebles    where obra_id = b.registro_id)
    or exists (select 1 from pendientes where obra_id = b.registro_id) then
      return false;
    end if;
    delete from obras where id = b.registro_id;

  elsif b.accion = 'crear_cotizacion' then
    delete from cotizaciones where id = b.registro_id;

  else
    return false;
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;
  return true;
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
      'pendiente_de_oficina', 'crear_cotizacion'
    )
  order by 1;
$$;
