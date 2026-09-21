-- =====================================================================
-- Deshacer por MENSAJE, no por fila
--
-- "Borra ambas credenzas" produce dos escrituras. Al pedir "deshaz el
-- último cambio", deshacer revertía sólo una y el asistente decía que
-- había revertido las dos. Ahora revierte todo lo que vino del mismo
-- mensaje, y devuelve cuántas cosas tocó para que el eco no pueda
-- inventar.
--
-- Ejecutar después de 06_utilidades.sql. Se puede volver a correr.
-- =====================================================================

-- --- Revertir UNA entrada. Antes esta lógica vivía duplicada. --------
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

-- --- Deshacer el último MENSAJE completo -----------------------------
create or replace function deshacer(p_persona uuid)
returns jsonb
language plpgsql as $$
declare
  ult      bitacora%rowtype;
  b        bitacora%rowtype;
  n        int := 0;
  acciones text[] := '{}';
begin
  select * into ult from bitacora
   where (p_persona is null or persona_id = p_persona) and not deshecho
   order by created_at desc, id desc limit 1;

  if not found then
    return jsonb_build_object('ok', false, 'revertidos', 0,
                              'motivo', 'No hay nada que deshacer');
  end if;

  -- Todo lo que salió del mismo mensaje. La ventana de tiempo evita
  -- agarrar un mensaje idéntico escrito horas después.
  for b in
    select * from bitacora
     where not deshecho
       and (p_persona is null or persona_id = p_persona)
       and mensaje_origen is not distinct from ult.mensaje_origen
       and created_at >= ult.created_at - interval '3 minutes'
       and created_at <= ult.created_at
     order by created_at desc, id desc
  loop
    if revertir_entrada(b) then
      n := n + 1;
      acciones := acciones || b.accion;
    end if;
  end loop;

  if n = 0 then
    return jsonb_build_object('ok', false, 'revertidos', 0,
                              'motivo', 'Esa acción no se puede deshacer');
  end if;

  return jsonb_build_object(
    'ok', true,
    'revertidos', n,
    'acciones', to_jsonb(acciones),
    'mensaje_original', ult.mensaje_origen);
end $$;
