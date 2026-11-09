-- =====================================================================
-- Resumen automático en la mañana
--
-- Quién lo recibe sale de `personas`: una columna por persona, para que
-- puedas prender el aviso al taller sin tocar código.
--
-- `avisos` es el candado contra mandarlo dos veces. Railway reinicia el
-- servicio cuando despliegas, y sin esto cada reinicio después de la
-- hora volvería a mandar el mensaje. Reclamar el día es una sola
-- operación atómica: si dos procesos lo intentan a la vez, sólo uno se
-- lo queda.
--
-- Ejecutar después de 14_bot_al_dia.sql. Se puede volver a correr.
-- =====================================================================

alter table personas add column if not exists resumen_diario boolean not null default false;

-- El admin lo recibe desde el principio; al taller se lo prendes con
--   update personas set resumen_diario = true where nombre = 'Beto';
update personas set resumen_diario = true
 where rol = 'admin' and not resumen_diario;

create table if not exists avisos (
  clave          text primary key,
  ultimo         date,
  actualizado_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Reclama el día para un aviso. Devuelve true sólo la primera vez que
-- alguien lo pide ese día; las demás, false.
-- ---------------------------------------------------------------------
create or replace function reclamar_aviso(p_clave text, p_dia date)
returns boolean
language plpgsql as $$
declare v_filas int;
begin
  insert into avisos (clave, ultimo) values (p_clave, p_dia)
  on conflict (clave) do update
     set ultimo = p_dia, actualizado_at = now()
   where coalesce(avisos.ultimo, '-infinity'::date) < p_dia;
  get diagnostics v_filas = row_count;
  return v_filas > 0;
end $$;

-- Por si hay que reenviarlo a mano el mismo día.
create or replace function soltar_aviso(p_clave text)
returns void
language sql as $$
  delete from avisos where clave = p_clave;
$$;

create or replace function destinatarios_resumen()
returns table (id uuid, nombre text, telefono text)
language sql stable as $$
  select p.id, p.nombre, p.telefono
  from personas p
  where p.activo and p.resumen_diario
    and p.telefono like '+%'      -- los de 'sólo panel' no tienen WhatsApp
  order by p.rol, p.nombre;
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
      'buscar_obra', 'buscar_grupo',
      'reclamar_aviso', 'soltar_aviso', 'destinatarios_resumen'
    )
  order by 1;
$$;
