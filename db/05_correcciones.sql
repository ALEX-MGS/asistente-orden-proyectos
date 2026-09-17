-- =====================================================================
-- Correcciones tras la primera prueba real por WhatsApp
--
-- 1. buscar_mueble no encontraba "el frigobar en habitación Fátima":
--    el filtro de obra sólo miraba el nombre de la obra, y "Habitación
--    Fátima" es un grupo. Ahora el filtro acepta cualquiera de los dos.
--
-- 2. Faltaba una forma de borrar TODO el progreso de un mueble de un
--    golpe. El asistente lo intentaba etapa por etapa y se quedaba a
--    medias, dejando el mueble en un estado inventado.
--
-- Ejecutar después de 04_terminado.sql. Se puede volver a correr.
-- =====================================================================

-- --- 1. la obra puede ser también el grupo ---------------------------
create or replace function buscar_mueble(p_texto text, p_obra text default null)
returns table (
  id uuid, obra text, grupo text, nombre text,
  avance numeric, en text, sigue text, terminado boolean, atrasado boolean
)
language sql stable as $$
  select v.id, v.obra, v.grupo, v.nombre,
         v.avance, v.en, v.sigue, v.terminado, v.atrasado
  from v_muebles v
  where not v.archivado
    and (p_obra is null
         or norm(v.obra) like '%' || norm(p_obra) || '%'
         or norm(coalesce(v.grupo, '')) like '%' || norm(p_obra) || '%')
    and (
      norm(v.nombre) like '%' || norm(p_texto) || '%'
      or norm(coalesce(v.grupo, '')) like '%' || norm(p_texto) || '%'
    )
  order by
    (norm(v.nombre) = norm(p_texto)) desc,
    (norm(v.nombre) like norm(p_texto) || '%') desc,
    length(v.nombre),
    v.obra, v.orden
  limit 12;
$$;

-- --- 2. borrar todo el progreso de un mueble, de una sola vez --------
-- Una sola operación y una sola entrada en bitácora: así 'deshacer'
-- lo devuelve completo y no a medias.
create or replace function reiniciar_mueble(
  p_mueble_id uuid,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare
  v_etapas jsonb;
  v_term   boolean;
  v_res    jsonb;
begin
  select terminado into v_term from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  select coalesce(jsonb_agg(jsonb_build_object('etapa_id', etapa_id, 'hecho', hecho)
                            order by etapa_id), '[]'::jsonb)
    into v_etapas
  from mueble_etapas where mueble_id = p_mueble_id;

  update mueble_etapas set hecho = false
   where mueble_id = p_mueble_id and hecho;
  update muebles set terminado = false
   where id = p_mueble_id and terminado;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'reiniciar_mueble', 'muebles', p_mueble_id,
          jsonb_build_object('etapas', v_etapas, 'terminado', v_term),
          jsonb_build_object('etapas', '[]'::jsonb, 'terminado', false),
          p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, grupo, nombre, avance, pasos_hechos, terminado
        from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- --- 3. deshacer aprende las acciones nuevas -------------------------
create or replace function deshacer(p_persona uuid)
returns jsonb
language plpgsql as $$
declare b bitacora%rowtype; e jsonb;
begin
  select * into b from bitacora
   where (p_persona is null or persona_id = p_persona) and not deshecho
   order by created_at desc limit 1;

  if not found then
    return jsonb_build_object('ok', false, 'motivo', 'No hay nada que deshacer');
  end if;

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
    return jsonb_build_object('ok', false, 'motivo', 'Esa acción no se puede deshacer');
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;
  return jsonb_build_object('ok', true, 'accion', b.accion,
                            'mensaje_original', b.mensaje_origen);
end $$;
