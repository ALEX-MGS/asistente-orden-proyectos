-- =====================================================================
-- Archivados: regresar una obra con sus muebles
--
-- La pantalla de Archivados del panel regresa lo que se sacó del
-- tablero. Para un mueble, un pendiente o una cotización ya bastaba con
-- archivar_*(…, false). Una obra no: archivar_obra(false) regresaba la
-- obra vacía, porque sus muebles se habían archivado con ella y se
-- quedaban fuera.
--
-- Ahora, al regresar una obra, vuelven con ella justo los muebles que
-- salieron la última vez que se archivó — no los que ya estaban
-- archivados de antes. Y Deshacer funciona en los dos sentidos: deshacer
-- un "sacar" regresa los muebles, deshacer un "regresar" los vuelve a
-- sacar.
--
-- No agrega funciones: revisar.py sigue esperando 35.
-- Ejecutar después de 15_resumen_diario.sql. Se puede volver a correr.
-- =====================================================================

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

  elsif v_antes then
    -- Los muebles que salieron con la obra la última vez que se archivó.
    select array_agg(m.id) into v_ids
    from muebles m
    where m.obra_id = p_obra_id and m.archivado
      and m.id in (
        select (jsonb_array_elements_text(b.antes -> 'muebles'))::uuid
        from bitacora b
        where b.id = (select id from bitacora
                      where accion = 'archivar_obra' and registro_id = p_obra_id
                        and not deshecho
                        and coalesce((despues ->> 'archivado')::boolean, false)
                      order by created_at desc, id desc limit 1));
    update muebles set archivado = false where id = any(coalesce(v_ids, '{}'::uuid[]));
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

-- Igual que en 13_archivar.sql, salvo archivar_obra: los muebles que la
-- entrada movió quedan como estaban ANTES de ella. Para un "sacar" eso
-- es regresarlos (como siempre); para un "regresar", volverlos a sacar.
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
      update muebles set archivado = coalesce((b.antes ->> 'archivado')::boolean, false)
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
