-- =====================================================================
-- Funciones que ejecuta el asistente (Fase 1)
-- Ejecutar después de 01_schema.sql y 02_seed.sql.
--
-- La idea: el modelo NO escribe SQL. Llama a estas funciones, que ya
-- traen adentro la búsqueda difusa, la validación y el registro en
-- bitácora. Si el modelo se equivoca, se equivoca eligiendo una función,
-- no corrompiendo datos.
-- =====================================================================

-- Normaliza para buscar: sin acentos, sin mayúsculas.
-- "Habitación Fátima" y "habitacion fatima" son la misma cosa.
create or replace function norm(t text) returns text
language sql immutable as $$
  select lower(translate(coalesce(t, ''),
    'áàäâéèëêíìïîóòöôúùüûñÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑ',
    'aaaaeeeeiiiioooouuuunAAAAEEEEIIIIOOOOUUUUN'))
$$;

-- ---------------------------------------------------------------------
-- Buscar un mueble por texto parcial. Devuelve candidatos ordenados:
-- primero los que empiezan igual, luego los que contienen el texto.
-- El asistente busca primero y actualiza después, con el id — así nunca
-- le pega al mueble equivocado por una coincidencia parcial.
-- ---------------------------------------------------------------------
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
    and (p_obra is null or norm(v.obra) like '%' || norm(p_obra) || '%')
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

-- ---------------------------------------------------------------------
-- Palomear o despalomear una etapa. Deja rastro en bitácora y devuelve
-- el estado nuevo para que el asistente lo repita de vuelta al usuario.
-- ---------------------------------------------------------------------
create or replace function actualizar_etapa(
  p_mueble_id uuid,
  p_etapa     text,
  p_hecho     boolean default true,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare
  v_etapa_id smallint;
  v_antes    boolean;
  v_res      jsonb;
begin
  select id into v_etapa_id from etapas where clave = norm(p_etapa);
  if v_etapa_id is null then
    raise exception 'Etapa desconocida: %. Son: aprobado, carpinteria, barniz, entrega, instalacion', p_etapa;
  end if;

  select hecho into v_antes
  from mueble_etapas where mueble_id = p_mueble_id and etapa_id = v_etapa_id;
  if not found then
    raise exception 'No existe ese mueble';
  end if;

  update mueble_etapas
     set hecho = p_hecho, persona_id = coalesce(p_persona, persona_id)
   where mueble_id = p_mueble_id and etapa_id = v_etapa_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'actualizar_etapa', 'mueble_etapas', p_mueble_id,
          jsonb_build_object('etapa_id', v_etapa_id, 'hecho', v_antes),
          jsonb_build_object('etapa_id', v_etapa_id, 'hecho', p_hecho),
          p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, grupo, nombre, avance, en, sigue, terminado
        from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- ---------------------------------------------------------------------
-- Alta de mueble. La obra se busca por nombre parcial; si no existe, se
-- crea. El trigger del esquema le pone sus cinco etapas en falso.
-- ---------------------------------------------------------------------
create or replace function crear_mueble(
  p_obra    text,
  p_nombre  text,
  p_grupo   text default null,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare
  v_obra_id uuid;
  v_id      uuid;
  v_res     jsonb;
begin
  select id into v_obra_id from obras
   where norm(nombre) like '%' || norm(p_obra) || '%'
   order by length(nombre) limit 1;

  if v_obra_id is null then
    insert into obras (nombre) values (p_obra) returning id into v_obra_id;
  end if;

  select id into v_id from muebles
   where obra_id = v_obra_id and norm(nombre) = norm(p_nombre)
     and norm(coalesce(grupo, '')) = norm(coalesce(p_grupo, ''));
  if v_id is not null then
    raise exception 'Ya existe un mueble con ese nombre en esa obra';
  end if;

  insert into muebles (obra_id, nombre, grupo, orden)
  values (v_obra_id, p_nombre, p_grupo,
          coalesce((select max(orden) + 1 from muebles where obra_id = v_obra_id), 1))
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'crear_mueble', 'muebles', v_id,
          jsonb_build_object('obra_id', v_obra_id, 'nombre', p_nombre, 'grupo', p_grupo),
          p_mensaje);

  select to_jsonb(v) into v_res
  from (select id, obra, grupo, nombre, avance from v_muebles where id = v_id) v;
  return v_res;
end $$;

-- ---------------------------------------------------------------------
-- Fecha de entrega de un mueble.
-- ---------------------------------------------------------------------
create or replace function fijar_fecha(
  p_mueble_id uuid,
  p_fecha     date,
  p_persona   uuid default null,
  p_mensaje   text default null
) returns jsonb
language plpgsql as $$
declare v_antes date; v_res jsonb;
begin
  select fecha_entrega into v_antes from muebles where id = p_mueble_id;
  if not found then raise exception 'No existe ese mueble'; end if;

  update muebles set fecha_entrega = p_fecha where id = p_mueble_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'fijar_fecha', 'muebles', p_mueble_id,
          jsonb_build_object('fecha_entrega', v_antes),
          jsonb_build_object('fecha_entrega', p_fecha), p_mensaje);

  select to_jsonb(v) into v_res
  from (select obra, nombre, fecha_entrega, avance, atrasado
        from v_muebles where id = p_mueble_id) v;
  return v_res;
end $$;

-- ---------------------------------------------------------------------
-- Pendientes: alta y cierre.
-- ---------------------------------------------------------------------
create or replace function agregar_pendiente(
  p_obra    text,
  p_texto   text,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_obra_id uuid; v_id uuid;
begin
  select id into v_obra_id from obras
   where norm(nombre) like '%' || norm(p_obra) || '%'
   order by length(nombre) limit 1;
  if v_obra_id is null then
    insert into obras (nombre) values (p_obra) returning id into v_obra_id;
  end if;

  insert into pendientes (obra_id, texto) values (v_obra_id, p_texto)
  returning id into v_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, despues, mensaje_origen)
  values (p_persona, 'agregar_pendiente', 'pendientes', v_id,
          jsonb_build_object('obra_id', v_obra_id, 'texto', p_texto), p_mensaje);

  return jsonb_build_object(
    'id', v_id,
    'obra', (select nombre from obras where id = v_obra_id),
    'texto', p_texto);
end $$;

create or replace function cerrar_pendiente(
  p_pendiente_id uuid,
  p_hecho   boolean default true,
  p_persona uuid default null,
  p_mensaje text default null
) returns jsonb
language plpgsql as $$
declare v_antes boolean; v_texto text;
begin
  select hecho, texto into v_antes, v_texto from pendientes where id = p_pendiente_id;
  if not found then raise exception 'No existe ese pendiente'; end if;

  update pendientes
     set hecho = p_hecho, hecho_at = case when p_hecho then now() else null end
   where id = p_pendiente_id;

  insert into bitacora (persona_id, accion, tabla, registro_id, antes, despues, mensaje_origen)
  values (p_persona, 'cerrar_pendiente', 'pendientes', p_pendiente_id,
          jsonb_build_object('hecho', v_antes),
          jsonb_build_object('hecho', p_hecho), p_mensaje);

  return jsonb_build_object('id', p_pendiente_id, 'texto', v_texto, 'hecho', p_hecho);
end $$;

create or replace function buscar_pendiente(p_texto text, p_obra text default null)
returns table (id uuid, obra text, texto text, hecho boolean)
language sql stable as $$
  select p.id, o.nombre, p.texto, p.hecho
  from pendientes p
  join obras o on o.id = p.obra_id
  where not p.hecho
    and (p_obra is null or norm(o.nombre) like '%' || norm(p_obra) || '%')
    and (p_texto is null or norm(p.texto) like '%' || norm(p_texto) || '%')
  order by o.nombre, p.created_at
  limit 15;
$$;

-- ---------------------------------------------------------------------
-- Resumen de una obra, o de todo si no se pasa obra.
-- Lo atrasado y lo detenido va primero: es lo que hay que ver.
-- ---------------------------------------------------------------------
create or replace function resumen(p_obra text default null)
returns jsonb
language sql stable as $$
  with m as (
    select * from v_muebles
    where not archivado
      and (p_obra is null or norm(obra) like '%' || norm(p_obra) || '%')
  )
  select jsonb_build_object(
    'obra', coalesce(p_obra, 'todas'),
    'total', (select count(*) from m),
    'terminados', (select count(*) from m where terminado),
    'sin_empezar', (select count(*) from m where avance = 0),
    'avance_promedio', (select round(coalesce(avg(avance), 0), 2) from m),
    'atrasados', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'obra', obra, 'mueble', nombre, 'avance', avance,
        'sigue', sigue, 'fecha_entrega', fecha_entrega)), '[]'::jsonb)
      from (select * from m where atrasado order by fecha_entrega limit 10) x),
    'en_proceso', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'obra', obra, 'mueble', nombre, 'avance', avance,
        'en', en, 'sigue', sigue, 'dias_sin_movimiento', dias_sin_movimiento)), '[]'::jsonb)
      from (select * from m where not terminado and avance > 0
            order by avance desc, obra, orden limit 15) x),
    'por_obra', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'obra', obra, 'muebles', n, 'terminados', t, 'avance', a)), '[]'::jsonb)
      from (select obra, count(*) n, count(*) filter (where terminado) t,
                   round(avg(avance), 2) a
            from m group by obra order by obra) y),
    'pendientes_abiertos', (
      select coalesce(jsonb_agg(jsonb_build_object('obra', o.nombre, 'texto', p.texto)), '[]'::jsonb)
      from (select p.* from pendientes p
            join obras o2 on o2.id = p.obra_id
            where not p.hecho
              and (p_obra is null or norm(o2.nombre) like '%' || norm(p_obra) || '%')
            order by p.created_at limit 15) p
      join obras o on o.id = p.obra_id)
  );
$$;

-- ---------------------------------------------------------------------
-- Deshacer el último cambio de una persona. Sin esto, un malentendido
-- del modelo se queda escrito para siempre.
-- ---------------------------------------------------------------------
create or replace function deshacer(p_persona uuid)
returns jsonb
language plpgsql as $$
declare b bitacora%rowtype;
begin
  select * into b from bitacora
   where (p_persona is null or persona_id = p_persona)
     and not deshecho
   order by created_at desc limit 1;

  if not found then
    return jsonb_build_object('ok', false, 'motivo', 'No hay nada que deshacer');
  end if;

  if b.accion = 'actualizar_etapa' then
    update mueble_etapas
       set hecho = (b.antes ->> 'hecho')::boolean
     where mueble_id = b.registro_id
       and etapa_id = (b.antes ->> 'etapa_id')::smallint;

  elsif b.accion = 'crear_mueble' then
    delete from muebles where id = b.registro_id;

  elsif b.accion = 'fijar_fecha' then
    update muebles set fecha_entrega = (b.antes ->> 'fecha_entrega')::date
     where id = b.registro_id;

  elsif b.accion = 'agregar_pendiente' then
    delete from pendientes where id = b.registro_id;

  elsif b.accion = 'cerrar_pendiente' then
    update pendientes
       set hecho = (b.antes ->> 'hecho')::boolean,
           hecho_at = case when (b.antes ->> 'hecho')::boolean then hecho_at else null end
     where id = b.registro_id;

  else
    return jsonb_build_object('ok', false, 'motivo', 'Esa acción no se puede deshacer');
  end if;

  update bitacora set deshecho = true, deshecho_at = now() where id = b.id;

  return jsonb_build_object('ok', true, 'accion', b.accion,
                            'mensaje_original', b.mensaje_origen);
end $$;
