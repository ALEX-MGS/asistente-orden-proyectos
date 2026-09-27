-- =====================================================================
-- Marcar Terminado cierra también las cinco etapas
--
-- Si un mueble está terminado, por fuerza pasó por carpintería, barniz,
-- entrega e instalación. Palomear sólo Terminado dejaba un mueble en
-- 1/6 que decía estar terminado.
--
-- Desmarcar NO borra las etapas: quitar la palomita de Terminado no
-- significa que el mueble nunca se barnizó.
--
-- Ejecutar después de 08_notas.sql. Se puede volver a correr.
-- =====================================================================

create or replace function marcar_terminado(
  p_mueble_id uuid,
  p_terminado boolean default true,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare
  v_term   boolean;
  v_etapas jsonb;
  v_res    jsonb;
begin
  select terminado into v_term from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  -- El estado completo de antes, para que deshacer devuelva todo.
  select coalesce(jsonb_agg(jsonb_build_object('etapa_id', etapa_id, 'hecho', hecho)
                            order by etapa_id), '[]'::jsonb)
    into v_etapas
  from mueble_etapas where mueble_id = p_mueble_id;

  update muebles set terminado = p_terminado where id = p_mueble_id;

  -- Al marcar, se cierran las cinco. Al desmarcar, no se toca nada más.
  if p_terminado then
    update mueble_etapas set hecho = true
     where mueble_id = p_mueble_id and not hecho;
  end if;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'marcar_terminado', 'muebles', p_mueble_id,
          jsonb_build_object('terminado', v_term, 'etapas', v_etapas),
          jsonb_build_object('terminado', p_terminado), p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, grupo, nombre, avance, pasos_hechos, terminado
        from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- Deshacer tiene que devolver también las etapas que se cerraron de paso.
-- Las entradas viejas de bitácora no traen 'etapas': se siguen deshaciendo
-- como antes.
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

  else
    return false;
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;
  return true;
end $$;
