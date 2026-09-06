-- =====================================================================
-- Asistente de obra · Grupo Morales
-- Esquema base (Fase 0) — Postgres / Supabase
-- Ejecutar completo en el SQL Editor de Supabase.
--
-- Refleja el modelo real del panel: un mueble tiene cinco etapas que se
-- palomean por separado, no una sola etapa actual.
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Catálogo de etapas. El avance de un mueble es la suma de los pesos
-- de sus etapas palomeadas — no se guarda un porcentaje suelto, así que
-- si algún día cambian las etapas o los pesos, nada queda inconsistente.
-- ---------------------------------------------------------------------
create table if not exists etapas (
  id      smallint primary key,
  clave   text not null unique,
  nombre  text not null,
  orden   smallint not null unique,
  peso    numeric(4,3) not null default 0.200
);

-- ---------------------------------------------------------------------
-- Obras. tipo 'interna' es para lo de oficina, que no es obra de cliente
-- pero sí lleva pendientes.
-- ---------------------------------------------------------------------
create table if not exists obras (
  id             uuid primary key default gen_random_uuid(),
  nombre         text not null unique,
  tipo           text not null default 'obra' check (tipo in ('obra','interna')),
  estado         text not null default 'activa'
                 check (estado in ('activa','pausada','cerrada')),
  fecha_entrega  date,
  ubicacion      text,
  nota           text,
  orden          int not null default 0,
  created_at     timestamptz not null default now()
);
create index if not exists obras_nombre_ci on obras (lower(nombre));

-- ---------------------------------------------------------------------
-- Muebles. 'grupo' es el subgrupo dentro de la obra tal como lo usas en
-- el panel: 'Habitación Fátima', 'extras', el nombre del cliente.
-- ---------------------------------------------------------------------
create table if not exists muebles (
  id             uuid primary key default gen_random_uuid(),
  obra_id        uuid not null references obras(id) on delete cascade,
  nombre         text not null,
  grupo          text,
  medidas        text,
  fecha_entrega  date,
  nota           text,
  orden          int not null default 0,
  archivado      boolean not null default false,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists muebles_obra_idx on muebles (obra_id) where not archivado;
create index if not exists muebles_nombre_ci on muebles (obra_id, lower(nombre));

-- ---------------------------------------------------------------------
-- Una fila por mueble y etapa. Guarda cuándo se palomeó y quién lo
-- reportó, que es lo que hace posible medir cuánto tarda cada etapa.
-- ---------------------------------------------------------------------
create table if not exists mueble_etapas (
  mueble_id   uuid not null references muebles(id) on delete cascade,
  etapa_id    smallint not null references etapas(id),
  hecho       boolean not null default false,
  hecho_at    timestamptz,
  persona_id  uuid,
  primary key (mueble_id, etapa_id)
);

-- ---------------------------------------------------------------------
-- Pendientes sueltos por obra ("colocar resbalón puerta dorada").
-- ---------------------------------------------------------------------
create table if not exists pendientes (
  id          uuid primary key default gen_random_uuid(),
  obra_id     uuid references obras(id) on delete cascade,
  mueble_id   uuid references muebles(id) on delete cascade,
  texto       text not null,
  prioridad   smallint not null default 2 check (prioridad between 1 and 3),
  hecho       boolean not null default false,
  hecho_at    timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists pendientes_abiertos_idx on pendientes (obra_id) where not hecho;

-- ---------------------------------------------------------------------
-- Cotizaciones enviadas y su estado.
-- ---------------------------------------------------------------------
create table if not exists cotizaciones (
  id          uuid primary key default gen_random_uuid(),
  cliente     text not null,
  concepto    text,
  monto       numeric(12,2),
  fecha       date,
  estado      text not null default 'enviada'
              check (estado in ('enviada','revision','aprobada','rechazada')),
  obra_id     uuid references obras(id) on delete set null,
  nota        text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Quién puede hablarle al asistente. Un número que no esté aquí no lee
-- ni escribe nada.
-- ---------------------------------------------------------------------
create table if not exists personas (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  telefono    text not null unique,   -- E.164, ej. +5215512345678
  rol         text not null default 'taller' check (rol in ('admin','taller')),
  activo      boolean not null default true,
  created_at  timestamptz not null default now()
);

alter table mueble_etapas
  drop constraint if exists mueble_etapas_persona_fk;
alter table mueble_etapas
  add constraint mueble_etapas_persona_fk
  foreign key (persona_id) references personas(id) on delete set null;

-- ---------------------------------------------------------------------
-- Bitácora: todo cambio hecho por el asistente, con el antes, el después
-- y el mensaje de WhatsApp que lo provocó. De aquí sale 'deshacer'.
-- ---------------------------------------------------------------------
create table if not exists bitacora (
  id              bigserial primary key,
  persona_id      uuid references personas(id) on delete set null,
  accion          text not null,
  tabla           text not null,
  registro_id     uuid,
  antes           jsonb,
  despues         jsonb,
  mensaje_origen  text,
  deshecho        boolean not null default false,
  deshecho_at     timestamptz,
  created_at      timestamptz not null default now()
);
create index if not exists bitacora_reciente_idx on bitacora (persona_id, created_at desc);

-- ---------------------------------------------------------------------
-- Mensajes. wa_message_id es único a propósito: WhatsApp reenvía el
-- mismo webhook si no contestas rápido, y sin esto un mismo mensaje se
-- procesaría dos veces.
-- ---------------------------------------------------------------------
create table if not exists mensajes (
  id             bigserial primary key,
  persona_id     uuid references personas(id) on delete set null,
  telefono       text not null,
  direccion      text not null check (direccion in ('entrante','saliente')),
  texto          text,
  media_url      text,
  wa_message_id  text unique,
  created_at     timestamptz not null default now()
);
create index if not exists mensajes_hilo_idx on mensajes (telefono, created_at desc);

-- ---------------------------------------------------------------------
-- Automatismos
-- ---------------------------------------------------------------------
create or replace function touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists muebles_touch on muebles;
create trigger muebles_touch before update on muebles
  for each row execute function touch_updated_at();

drop trigger if exists cotizaciones_touch on cotizaciones;
create trigger cotizaciones_touch before update on cotizaciones
  for each row execute function touch_updated_at();

-- Cada mueble nuevo nace con sus cinco etapas en falso.
create or replace function crear_etapas_de_mueble() returns trigger
language plpgsql as $$
begin
  insert into mueble_etapas (mueble_id, etapa_id)
  select new.id, id from etapas
  on conflict do nothing;
  return new;
end $$;

drop trigger if exists muebles_etapas_auto on muebles;
create trigger muebles_etapas_auto after insert on muebles
  for each row execute function crear_etapas_de_mueble();

-- Sella la fecha cuando una etapa se palomea, y la borra si se despaloma.
create or replace function sellar_etapa() returns trigger
language plpgsql as $$
begin
  if new.hecho and not old.hecho then
    new.hecho_at = now();
  elsif not new.hecho and old.hecho then
    new.hecho_at = null;
  end if;
  return new;
end $$;

drop trigger if exists mueble_etapas_sello on mueble_etapas;
create trigger mueble_etapas_sello before update on mueble_etapas
  for each row execute function sellar_etapa();

-- ---------------------------------------------------------------------
-- Vista de trabajo. De aquí leen el tablero, los resúmenes de WhatsApp
-- y la imagen PNG: ya trae avance, en qué va, qué sigue y si está atrasado.
-- ---------------------------------------------------------------------
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
  coalesce((
    select sum(e.peso) from mueble_etapas me
    join etapas e on e.id = me.etapa_id
    where me.mueble_id = m.id and me.hecho
  ), 0)::numeric(4,3) as avance,
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
  not exists (
    select 1 from mueble_etapas me
    where me.mueble_id = m.id and not me.hecho
  ) as terminado,
  (m.fecha_entrega is not null
    and m.fecha_entrega < current_date
    and exists (select 1 from mueble_etapas me
                where me.mueble_id = m.id and not me.hecho)
  ) as atrasado,
  (current_date - m.updated_at::date) as dias_sin_movimiento
from muebles m
join obras o on o.id = m.obra_id;

-- ---------------------------------------------------------------------
-- Seguridad: RLS activo y sin políticas = ninguna llave pública puede
-- leer nada. El backend usa la llave service_role, que se salta RLS y
-- nunca sale del servidor.
-- ---------------------------------------------------------------------
alter table obras         enable row level security;
alter table muebles       enable row level security;
alter table mueble_etapas enable row level security;
alter table pendientes    enable row level security;
alter table cotizaciones  enable row level security;
alter table personas      enable row level security;
alter table bitacora      enable row level security;
alter table mensajes      enable row level security;
