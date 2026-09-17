-- =====================================================================
-- 1. Limpieza de la basura que dejó el diagnóstico
-- 2. Una forma de SOLO LECTURA de saber qué funciones existen
--
-- Ejecutar después de 05_correcciones.sql. Se puede volver a correr.
-- =====================================================================

-- --- 1. Borrar los registros vacíos ----------------------------------
-- revisar.py probaba crear_mueble y agregar_pendiente con cadenas
-- vacías creyendo que iban a fallar. No fallaron: insertaron. Esto
-- borra exactamente eso y nada más.
delete from pendientes where btrim(coalesce(texto, '')) = '';
delete from muebles    where btrim(coalesce(nombre, '')) = '';
delete from obras o    where btrim(coalesce(o.nombre, '')) = ''
  and not exists (select 1 from muebles m    where m.obra_id = o.id)
  and not exists (select 1 from pendientes p where p.obra_id = o.id);

-- Y las entradas de bitácora de esas pruebas, para que 'deshacer' no
-- intente revertir algo que ya no existe.
update bitacora set deshecho = true, deshecho_at = now()
where not deshecho
  and accion in ('crear_mueble', 'agregar_pendiente')
  and (despues ->> 'nombre' = '' or despues ->> 'texto' = '');

-- --- 2. Catálogo de funciones, sin efectos secundarios ---------------
-- Preguntarle a Postgres qué existe es infinitamente más seguro que
-- llamar cada función a ver si truena.
create or replace function funciones_del_asistente()
returns table (nombre text)
language sql stable as $$
  select p.proname::text
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname in (
      'buscar_mueble', 'buscar_pendiente', 'resumen',
      'actualizar_etapa', 'marcar_terminado', 'reiniciar_mueble',
      'crear_mueble', 'fijar_fecha', 'agregar_pendiente',
      'cerrar_pendiente', 'deshacer'
    )
  order by 1;
$$;

-- --- 3. Candado para que no se repita --------------------------------
-- Un mueble o un pendiente sin nombre no significa nada. Que la base
-- lo rechace, venga de donde venga.
alter table muebles    drop constraint if exists muebles_nombre_no_vacio;
alter table muebles    add  constraint muebles_nombre_no_vacio
  check (btrim(nombre) <> '');
alter table pendientes drop constraint if exists pendientes_texto_no_vacio;
alter table pendientes add  constraint pendientes_texto_no_vacio
  check (btrim(texto) <> '');
alter table obras      drop constraint if exists obras_nombre_no_vacio;
alter table obras      add  constraint obras_nombre_no_vacio
  check (btrim(nombre) <> '');
