-- =====================================================================
-- El bot al día con el tablero
--
-- El panel ya archiva, renombra y edita obras; el asistente de WhatsApp
-- no sabía hacer nada de eso. Las funciones de escritura ya existen
-- (10 a 13) — lo único que faltaba era una forma de encontrar una obra,
-- porque archivar_obra, editar_obra, archivar_grupo y renombrar_grupo
-- piden su id y el bot no tenía de dónde sacarlo.
--
-- Ejecutar después de 13_archivar.sql. Se puede volver a correr.
-- =====================================================================

create or replace function buscar_obra(p_texto text default null)
returns table (
  id uuid, nombre text, tipo text, es_proyecto boolean,
  fecha_entrega date, muebles int, pendientes_abiertos int
)
language sql stable as $$
  select o.id, o.nombre, o.tipo, o.es_proyecto, o.fecha_entrega,
         (select count(*)::int from muebles m
           where m.obra_id = o.id and not m.archivado),
         (select count(*)::int from pendientes p
           where p.obra_id = o.id and not p.hecho and not p.archivado)
  from obras o
  where not o.archivado
    and (p_texto is null or norm(o.nombre) like '%' || norm(p_texto) || '%')
  order by
    (norm(o.nombre) = norm(coalesce(p_texto, ''))) desc,
    (norm(o.nombre) like norm(coalesce(p_texto, '')) || '%') desc,
    length(o.nombre),
    o.nombre
  limit 40;        -- sin texto sirve de "lístame las obras": que no corte
$$;

-- Los grupos / habitaciones de una obra, para poder renombrarlos o
-- archivarlos por nombre sin adivinar.
create or replace function buscar_grupo(p_obra_id uuid)
returns table (grupo text, muebles int)
language sql stable as $$
  select coalesce(m.grupo, '') as grupo, count(*)::int
  from muebles m
  where m.obra_id = p_obra_id and not m.archivado
  group by 1
  order by 1;
$$;

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
      'archivar_pendiente', 'archivar_cotizacion', 'acomodar_muebles',
      'buscar_obra', 'buscar_grupo'
    )
  order by 1;
$$;
