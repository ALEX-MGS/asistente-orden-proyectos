-- =====================================================================
-- Edición desde el panel · tanda 3: archivar y reordenar
--
-- "Eliminar" en el tablero archiva: la fila se queda en la base y
-- desaparece de la pantalla. Deshacer la regresa, y el historial de
-- cuánto tardó cada etapa no se pierde. Nada de este archivo borra.
--
-- Archivar un proyecto u obra archiva también sus muebles. Deshacer
-- regresa exactamente los que se archivaron de paso, no los que ya
-- estaban archivados de antes.
--
-- Ejecutar después de 12_vista_y_tokens.sql. Se puede volver a correr.
-- =====================================================================

alter table obras        add column if not exists archivado boolean not null default false;
alter table pendientes   add column if not exists archivado boolean not null default false;
alter table cotizaciones add column if not exists archivado boolean not null default false;

-- ---------------------------------------------------------------------
-- Muebles
-- ---------------------------------------------------------------------
create or replace function archivar_mueble(
  p_mueble_id uuid,
  p_archivado boolean default true,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_nombre text;
begin
  select archivado, nombre into v_antes, v_nombre
  from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  update muebles set archivado = p_archivado where id = p_mueble_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'archivar_mueble', 'muebles', p_mueble_id,
          jsonb_build_object('archivado', v_antes),
          jsonb_build_object('archivado', p_archivado), p_mensaje);

  return jsonb_build_object('id', p_mueble_id, 'nombre', v_nombre,
                            'archivado', p_archivado);
end $$;

-- ---------------------------------------------------------------------
-- Un grupo / habitación completo. Se guardan los ids que se tocaron:
-- deshacer no revive lo que ya estaba archivado.
-- ---------------------------------------------------------------------
create or replace function archivar_grupo(
  p_obra_id uuid,
  p_grupo   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_ids uuid[];
begin
  if not exists (select 1 from obras where id = p_obra_id) then
    raise exception 'No existe esa obra';
  end if;

  select array_agg(id) into v_ids
  from muebles
  where obra_id = p_obra_id
    and coalesce(grupo, '') = coalesce(p_grupo, '')
    and not archivado;

  if v_ids is null then raise exception 'No hay muebles activos en ese grupo'; end if;

  update muebles set archivado = true where id = any(v_ids);

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'archivar_grupo', 'muebles', p_obra_id,
          jsonb_build_object('grupo', p_grupo, 'muebles', to_jsonb(v_ids)),
          jsonb_build_object('archivado', true), p_mensaje);

  return jsonb_build_object('grupo', p_grupo, 'muebles', array_length(v_ids, 1));
end $$;

-- ---------------------------------------------------------------------
-- Una obra o proyecto, con sus muebles.
-- ---------------------------------------------------------------------
create or replace function archivar_obra(
  p_obra_id   uuid,
  p_archivado boolean default true,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_nombre text; v_ids uuid[];
begin
  select archivado, nombre into v_antes, v_nombre from obras where id = p_obra_id;
  if not found then raise exception 'No existe esa obra'; end if;

  if p_archivado then
    select array_agg(id) into v_ids
    from muebles where obra_id = p_obra_id and not archivado;
    update muebles set archivado = true where id = any(coalesce(v_ids, '{}'::uuid[]));
  end if;

  update obras set archivado = p_archivado where id = p_obra_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'archivar_obra', 'obras', p_obra_id,
          jsonb_build_object('archivado', v_antes,
                             'muebles', to_jsonb(coalesce(v_ids, '{}'::uuid[]))),
          jsonb_build_object('archivado', p_archivado), p_mensaje);

  return jsonb_build_object('id', p_obra_id, 'nombre', v_nombre,
                            'archivado', p_archivado,
                            'muebles', coalesce(array_length(v_ids, 1), 0));
end $$;

-- ---------------------------------------------------------------------
-- Pendientes y cotizaciones
-- ---------------------------------------------------------------------
create or replace function archivar_pendiente(
  p_pendiente_id uuid,
  p_archivado    boolean default true,
  p_persona      uuid default null,
  p_mensaje      text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_texto text;
begin
  select archivado, texto into v_antes, v_texto
  from pendientes where id = p_pendiente_id;
  if not found then raise exception 'No existe ese pendiente'; end if;

  update pendientes set archivado = p_archivado where id = p_pendiente_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'archivar_pendiente', 'pendientes', p_pendiente_id,
          jsonb_build_object('archivado', v_antes),
          jsonb_build_object('archivado', p_archivado), p_mensaje);

  return jsonb_build_object('id', p_pendiente_id, 'texto', v_texto,
                            'archivado', p_archivado);
end $$;

create or replace function archivar_cotizacion(
  p_cotizacion_id uuid,
  p_archivado     boolean default true,
  p_persona       uuid default null,
  p_mensaje       text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_cliente text;
begin
  select archivado, cliente into v_antes, v_cliente
  from cotizaciones where id = p_cotizacion_id;
  if not found then raise exception 'No existe esa cotización'; end if;

  update cotizaciones set archivado = p_archivado where id = p_cotizacion_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'archivar_cotizacion', 'cotizaciones', p_cotizacion_id,
          jsonb_build_object('archivado', v_antes),
          jsonb_build_object('archivado', p_archivado), p_mensaje);

  return jsonb_build_object('id', p_cotizacion_id, 'cliente', v_cliente,
                            'archivado', p_archivado);
end $$;

-- ---------------------------------------------------------------------
-- Reordenar arrastrando.
--
-- Llega la lista completa de los muebles de la obra en el orden nuevo,
-- cada uno con el grupo en el que quedó: al soltar un mueble sobre otro
-- hereda su habitación, así que el orden y el grupo cambian juntos y
-- deben deshacerse juntos.
--
--   p_muebles = [{"id": "...", "grupo": "Recámara 1"}, ...]
-- ---------------------------------------------------------------------
create or replace function acomodar_muebles(
  p_obra_id uuid,
  p_muebles jsonb,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_antes jsonb; v_n int;
begin
  if p_muebles is null or jsonb_typeof(p_muebles) <> 'array'
     or jsonb_array_length(p_muebles) = 0 then
    raise exception 'No mandaste el orden nuevo';
  end if;

  -- Todos los ids tienen que ser de esta obra. Sin esto, una petición
  -- torcida podría mover muebles de otra obra.
  if exists (
    select 1 from jsonb_array_elements(p_muebles) e
    where not exists (
      select 1 from muebles m
      where m.id = (e ->> 'id')::uuid and m.obra_id = p_obra_id)
  ) then
    raise exception 'Hay muebles que no son de esa obra';
  end if;

  select jsonb_agg(jsonb_build_object('id', m.id, 'orden', m.orden, 'grupo', m.grupo)
                   order by m.orden)
    into v_antes
  from muebles m where m.obra_id = p_obra_id;

  update muebles m set
    orden = nuevo.pos,
    grupo = case when nuevo.e ? 'grupo'
                 then nullif(btrim(coalesce(nuevo.e ->> 'grupo', '')), '')
                 else m.grupo end
  from (
    select e, (ord)::int as pos
    from jsonb_array_elements(p_muebles) with ordinality as t(e, ord)
  ) nuevo
  where m.id = (nuevo.e ->> 'id')::uuid;
  get diagnostics v_n = row_count;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'acomodar_muebles', 'muebles', p_obra_id,
          v_antes, p_muebles, p_mensaje);

  return jsonb_build_object('muebles', v_n);
end $$;

-- ---------------------------------------------------------------------
-- Lo archivado deja de salir en las búsquedas del asistente.
-- ---------------------------------------------------------------------
create or replace function buscar_pendiente(p_texto text, p_obra text default null)
returns table (id uuid, obra text, texto text, hecho boolean)
language sql stable as $$
  select p.id, o.nombre, p.texto, p.hecho
  from pendientes p
  join obras o on o.id = p.obra_id
  where not p.hecho and not p.archivado and not o.archivado
    and (p_obra is null or norm(o.nombre) like '%' || norm(p_obra) || '%')
    and (p_texto is null or norm(p.texto) like '%' || norm(p_texto) || '%')
  order by o.nombre, p.created_at
  limit 15;
$$;

-- ---------------------------------------------------------------------
-- Deshacer aprende a desarchivar y a devolver el orden.
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

  elsif b.accion = 'crear_obra' then
    if exists (select 1 from muebles    where obra_id = b.registro_id)
    or exists (select 1 from pendientes where obra_id = b.registro_id) then
      return false;
    end if;
    delete from obras where id = b.registro_id;

  elsif b.accion = 'crear_cotizacion' then
    delete from cotizaciones where id = b.registro_id;

  -- --- nuevas de 13_archivar.sql ---
  elsif b.accion = 'archivar_mueble' then
    update muebles set archivado = (b.antes ->> 'archivado')::boolean
     where id = b.registro_id;

  elsif b.accion = 'archivar_grupo' then
    update muebles set archivado = false
     where id in (select (jsonb_array_elements_text(b.antes -> 'muebles'))::uuid);

  elsif b.accion = 'archivar_obra' then
    update obras set archivado = (b.antes ->> 'archivado')::boolean
     where id = b.registro_id;
    if b.antes ? 'muebles' then
      update muebles set archivado = false
       where id in (select (jsonb_array_elements_text(b.antes -> 'muebles'))::uuid);
    end if;

  elsif b.accion = 'archivar_pendiente' then
    update pendientes set archivado = (b.antes ->> 'archivado')::boolean
     where id = b.registro_id;

  elsif b.accion = 'archivar_cotizacion' then
    update cotizaciones set archivado = (b.antes ->> 'archivado')::boolean
     where id = b.registro_id;

  elsif b.accion = 'acomodar_muebles' then
    for e in select * from jsonb_array_elements(b.antes) loop
      update muebles set orden = (e ->> 'orden')::int, grupo = e ->> 'grupo'
       where id = (e ->> 'id')::uuid;
    end loop;

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
      'pendiente_de_oficina', 'crear_cotizacion',
      'persona_por_token', 'links_del_panel', 'renovar_token',
      'archivar_mueble', 'archivar_grupo', 'archivar_obra',
      'archivar_pendiente', 'archivar_cotizacion', 'acomodar_muebles'
    )
  order by 1;
$$;
