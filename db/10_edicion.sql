-- =====================================================================
-- Edición desde el panel · tanda 1: cambiar lo que ya existe
--
-- Nada de esto crea ni borra. Sólo renombra y corrige campos de filas
-- que ya están en la base, que es la parte que no puede salir mal.
--
-- Las cuatro funciones nuevas dejan su rastro en bitácora igual que las
-- de WhatsApp, así que 'deshacer' funciona sobre ellas sin cambios.
--
-- Ejecutar después de 09_terminado_completa.sql. Se puede volver a correr.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Renombrar un mueble.
-- ---------------------------------------------------------------------
create or replace function renombrar_mueble(
  p_mueble_id uuid,
  p_nombre    text,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes text; v_obra uuid; v_grupo text; v_res jsonb;
begin
  p_nombre := nullif(btrim(coalesce(p_nombre, '')), '');
  if p_nombre is null then
    raise exception 'El mueble necesita un nombre';
  end if;

  select nombre, obra_id, grupo into v_antes, v_obra, v_grupo
  from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  if exists (
    select 1 from muebles
    where obra_id = v_obra and id <> p_mueble_id
      and norm(nombre) = norm(p_nombre)
      and norm(coalesce(grupo, '')) = norm(coalesce(v_grupo, ''))
  ) then
    raise exception 'Ya hay otro mueble con ese nombre en la misma obra';
  end if;

  update muebles set nombre = p_nombre where id = p_mueble_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'renombrar_mueble', 'muebles', p_mueble_id,
          jsonb_build_object('nombre', v_antes),
          jsonb_build_object('nombre', p_nombre), p_mensaje);

  select to_jsonb(v) into v_res
  from (select id, obra, grupo, nombre from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- ---------------------------------------------------------------------
-- Renombrar un grupo / habitación. Toca todos los muebles de esa obra
-- que traen ese grupo, en una sola entrada de bitácora.
-- ---------------------------------------------------------------------
create or replace function renombrar_grupo(
  p_obra_id uuid,
  p_grupo   text,
  p_nuevo   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_n int;
begin
  p_nuevo := nullif(btrim(coalesce(p_nuevo, '')), '');
  if p_nuevo is null then
    raise exception 'El grupo necesita un nombre';
  end if;
  if not exists (select 1 from obras where id = p_obra_id) then
    raise exception 'No existe esa obra';
  end if;

  update muebles set grupo = p_nuevo
   where obra_id = p_obra_id
     and coalesce(grupo, '') = coalesce(p_grupo, '');
  get diagnostics v_n = row_count;

  if v_n = 0 then raise exception 'No hay muebles en ese grupo'; end if;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'renombrar_grupo', 'muebles', p_obra_id,
          jsonb_build_object('grupo', p_grupo),
          jsonb_build_object('grupo', p_nuevo, 'muebles', v_n), p_mensaje);

  return jsonb_build_object('grupo', p_nuevo, 'muebles', v_n);
end $$;

-- ---------------------------------------------------------------------
-- Editar una obra y editar una cotización.
--
-- Reciben un jsonb con sólo los campos que cambian: así se distingue
-- "no me toques la nota" de "déjame la nota vacía", que con parámetros
-- sueltos en null no se puede.
--
-- Los nombres de columna nunca salen del jsonb: se listan aquí abajo.
-- ---------------------------------------------------------------------
create or replace function aplicar_obra(p_obra_id uuid, p_cambios jsonb)
returns void
language plpgsql as $$
begin
  if p_cambios ? 'nombre'
     and nullif(btrim(coalesce(p_cambios ->> 'nombre', '')), '') is null then
    raise exception 'La obra necesita un nombre';
  end if;

  update obras set
    nombre = case when p_cambios ? 'nombre'
                  then btrim(p_cambios ->> 'nombre') else nombre end,
    fecha_entrega = case when p_cambios ? 'fecha_entrega'
                  then nullif(p_cambios ->> 'fecha_entrega', '')::date
                  else fecha_entrega end,
    nota = case when p_cambios ? 'nota'
                  then nullif(btrim(coalesce(p_cambios ->> 'nota', '')), '')
                  else nota end
  where id = p_obra_id;
end $$;

create or replace function editar_obra(
  p_obra_id uuid,
  p_cambios jsonb,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare
  v_fila  jsonb;
  v_antes jsonb;
  v_malas text;
begin
  if p_cambios is null or p_cambios = '{}'::jsonb then
    raise exception 'No mandaste ningún cambio';
  end if;

  select string_agg(k, ', ') into v_malas
  from jsonb_object_keys(p_cambios) k
  where k <> all (array['nombre', 'fecha_entrega', 'nota']);
  if v_malas is not null then
    raise exception 'Campo que no se puede editar: %', v_malas;
  end if;

  select to_jsonb(o) into v_fila from obras o where id = p_obra_id;
  if v_fila is null then raise exception 'No existe esa obra'; end if;

  select jsonb_object_agg(k, v_fila -> k) into v_antes
  from jsonb_object_keys(p_cambios) k;

  begin
    perform aplicar_obra(p_obra_id, p_cambios);
  exception when unique_violation then
    raise exception 'Ya hay otra obra con ese nombre';
  end;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'editar_obra', 'obras', p_obra_id, v_antes, p_cambios, p_mensaje);

  return (select to_jsonb(v) from (select id, nombre, fecha_entrega, nota
                                   from obras where id = p_obra_id) v);
end $$;

create or replace function aplicar_cotizacion(p_cotizacion_id uuid, p_cambios jsonb)
returns void
language plpgsql as $$
begin
  if p_cambios ? 'cliente'
     and nullif(btrim(coalesce(p_cambios ->> 'cliente', '')), '') is null then
    raise exception 'La cotización necesita un cliente';
  end if;
  if p_cambios ? 'estado'
     and (p_cambios ->> 'estado') not in ('enviada', 'revision', 'aprobada', 'rechazada') then
    raise exception 'Estado desconocido: %', p_cambios ->> 'estado';
  end if;

  update cotizaciones set
    cliente  = case when p_cambios ? 'cliente'
                    then btrim(p_cambios ->> 'cliente') else cliente end,
    concepto = case when p_cambios ? 'concepto'
                    then nullif(btrim(coalesce(p_cambios ->> 'concepto', '')), '')
                    else concepto end,
    monto    = case when p_cambios ? 'monto'
                    then nullif(p_cambios ->> 'monto', '')::numeric(12,2)
                    else monto end,
    fecha    = case when p_cambios ? 'fecha'
                    then nullif(p_cambios ->> 'fecha', '')::date else fecha end,
    estado   = case when p_cambios ? 'estado'
                    then p_cambios ->> 'estado' else estado end,
    nota     = case when p_cambios ? 'nota'
                    then nullif(btrim(coalesce(p_cambios ->> 'nota', '')), '')
                    else nota end
  where id = p_cotizacion_id;
end $$;

create or replace function editar_cotizacion(
  p_cotizacion_id uuid,
  p_cambios jsonb,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare
  v_fila  jsonb;
  v_antes jsonb;
  v_malas text;
begin
  if p_cambios is null or p_cambios = '{}'::jsonb then
    raise exception 'No mandaste ningún cambio';
  end if;

  select string_agg(k, ', ') into v_malas
  from jsonb_object_keys(p_cambios) k
  where k <> all (array['cliente', 'concepto', 'monto', 'fecha', 'estado', 'nota']);
  if v_malas is not null then
    raise exception 'Campo que no se puede editar: %', v_malas;
  end if;

  select to_jsonb(c) into v_fila from cotizaciones c where id = p_cotizacion_id;
  if v_fila is null then raise exception 'No existe esa cotización'; end if;

  select jsonb_object_agg(k, v_fila -> k) into v_antes
  from jsonb_object_keys(p_cambios) k;

  perform aplicar_cotizacion(p_cotizacion_id, p_cambios);

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'editar_cotizacion', 'cotizaciones', p_cotizacion_id,
          v_antes, p_cambios, p_mensaje);

  return (select to_jsonb(v) from (select id, cliente, concepto, monto, fecha, estado, nota
                                   from cotizaciones where id = p_cotizacion_id) v);
end $$;

-- ---------------------------------------------------------------------
-- Deshacer aprende las cuatro acciones nuevas.
-- El resto queda igual que en 09_terminado_completa.sql.
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

  -- --- nuevas de 10_edicion.sql ---
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

  else
    return false;
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;
  return true;
end $$;

-- ---------------------------------------------------------------------
-- El catálogo que usa revisar.py para comprobar qué hay instalado.
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
      'renombrar_mueble', 'renombrar_grupo', 'editar_obra', 'editar_cotizacion'
    )
  order by 1;
$$;
