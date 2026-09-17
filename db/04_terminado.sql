-- =====================================================================
-- El sexto paso: "Terminado"
--
-- El panel cuenta seis pasos por mueble — las cinco etapas más una
-- palomita de Terminado que se marca aparte — y el avance es esa cuenta
-- entre seis. La base sólo tenía las cinco etapas y derivaba "terminado"
-- como "ya tiene todas". Esto lo alinea con el panel.
--
-- Ejecutar después de 03_funciones.sql. Se puede volver a correr.
-- =====================================================================

alter table muebles add column if not exists terminado boolean not null default false;

-- Los que hoy tienen las cinco etapas ya estaban terminados de hecho:
-- se marca una vez, para no perder el estado actual.
update muebles m set terminado = true
where not m.terminado
  and not exists (
    select 1 from mueble_etapas me
    where me.mueble_id = m.id and not me.hecho
  );

-- La vista pasa a contar sobre seis, igual que el panel.
-- Se respeta el orden de columnas de la vista anterior: Postgres no deja
-- reordenarlas con CREATE OR REPLACE, y las funciones dependen de ella.
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
  -- numeric(4,3) para no cambiarle el tipo a la columna que ya existía
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
  )::int as pasos_hechos
from muebles m
join obras o on o.id = m.obra_id;

-- --- marcar terminado desde el asistente -----------------------------
create or replace function marcar_terminado(
  p_mueble_id uuid,
  p_terminado boolean default true,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_res jsonb;
begin
  select terminado into v_antes from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  update muebles set terminado = p_terminado where id = p_mueble_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'marcar_terminado', 'muebles', p_mueble_id,
          jsonb_build_object('terminado', v_antes),
          jsonb_build_object('terminado', p_terminado), p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, nombre, avance, terminado from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- deshacer() tiene que saber revertir la acción nueva
create or replace function deshacer(p_persona uuid)
returns jsonb
language plpgsql as $$
declare b bitacora%rowtype;
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
