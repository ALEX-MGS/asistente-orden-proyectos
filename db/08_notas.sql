-- =====================================================================
-- Poner nota a un mueble
--
-- Faltaba la herramienta. Al pedir "ponle una nota al MOB 2", el
-- asistente no tenía con qué y terminó creando un pendiente suelto en
-- la obra, que no es lo mismo.
--
-- Ejecutar después de 07_deshacer_lote.sql. Se puede volver a correr.
-- =====================================================================

create or replace function poner_nota(
  p_mueble_id uuid,
  p_nota      text,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes text; v_res jsonb;
begin
  select nota into v_antes from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  update muebles set nota = nullif(btrim(coalesce(p_nota, '')), '')
   where id = p_mueble_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'poner_nota', 'muebles', p_mueble_id,
          jsonb_build_object('nota', v_antes),
          jsonb_build_object('nota', p_nota), p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, grupo, nombre, nota from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- deshacer tiene que conocer la acción nueva
create or replace function revertir_entrada(b bitacora)
returns boolean
language plpgsql as $$
declare e jsonb;
begin
  if b.accion = 'actualizar_etapa' then
    update mueble_etapas set hecho = (b.antes ->> 'hecho')::boolean
     where mueble_id = b.registro_id and etapa_id = (b.antes ->> 'etapa_id')::smallint;

  elsif b.accion = 'reiniciar_mueble' then
    for e in select * from jsonb_array_elements(b.antes -> 'etapas') loop
      update mueble_etapas set hecho = (e ->> 'hecho')::boolean
       where mueble_id = b.registro_id and etapa_id = (e ->> 'etapa_id')::smallint;
    end loop;
    update muebles set terminado = (b.antes ->> 'terminado')::boolean
     where id = b.registro_id;

  elsif b.accion = 'marcar_terminado' then
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

  else
    return false;
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;
  return true;
end $$;

-- y el catálogo de funciones también
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
      'cerrar_pendiente', 'deshacer'
    )
  order by 1;
$$;
