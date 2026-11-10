-- =====================================================================
-- Semilla de una instalación NUEVA
--
-- Esto es lo mínimo para que el tablero arranque vacío: las cinco etapas
-- del proceso y una persona que pueda entrar. Nada de datos de nadie.
--
-- Usa ESTE archivo en vez de 02_seed.sql, que trae las obras de Grupo
-- Morales. Los dos son excluyentes: corre uno u otro, no los dos.
--
-- Va en el mismo lugar que 02_seed.sql, y por eso lleva el mismo
-- número: son dos semillas para elegir una.
--
--   01_schema.sql
--   02_vacio.sql        <-- instalación nueva
--   02_seed.sql         <-- sólo la copia de Grupo Morales
--   03_funciones.sql … 15_resumen_diario.sql, en orden
--
-- Se puede volver a correr sin romper nada.
-- =====================================================================

-- --- Las cinco etapas del proceso ------------------------------------
-- Si en tu taller el proceso es otro, aquí es donde se cambia: los
-- nombres y el orden son libres. Deja las cinco filas — el tablero y el
-- avance están hechos sobre cinco etapas más la palomita de Terminado.
insert into etapas (id, clave, nombre, orden, peso) values
  (1, 'aprobado',    'Aprobado',    1, 0.200),
  (2, 'carpinteria', 'Carpintería', 2, 0.200),
  (3, 'barniz',      'Barniz',      3, 0.200),
  (4, 'entrega',     'Entrega',     4, 0.200),
  (5, 'instalacion', 'Instalación', 5, 0.200)
on conflict (id) do update set
  clave = excluded.clave, nombre = excluded.nombre,
  orden = excluded.orden, peso  = excluded.peso;

-- --- La obra interna, donde viven los pendientes de oficina ----------
insert into obras (nombre, tipo) values ('Oficina', 'interna')
on conflict (nombre) do nothing;

-- --- La primera persona ----------------------------------------------
-- CAMBIA el nombre y el teléfono por los tuyos ANTES de correr esto.
-- El teléfono va en formato internacional, igual que lo manda WhatsApp:
-- +52 más el número, y en México casi siempre con un 1 después del 52.
--
-- Si no estás seguro del formato, déjalo así, manda un mensaje al bot
-- desde tu teléfono y luego corre:
--
--   select telefono, texto from mensajes
--    where persona_id is null order by created_at desc limit 3;
--
-- y actualiza la fila con el número exacto que aparezca ahí:
--
--   update personas set telefono = '+52...' where rol = 'admin';
insert into personas (nombre, telefono, rol) values
  ('Admin', '+520000000000', 'admin')
on conflict (telefono) do nothing;

-- --- El link del panel para esa persona ------------------------------
-- 12_vista_y_tokens.sql crea la columna y reparte los tokens, así que
-- en una instalación nueva esto no hace nada. Está por si vuelves a
-- correr esta semilla después, cuando la columna ya existe.
do $$
begin
  if exists (select 1 from information_schema.columns
             where table_name = 'personas' and column_name = 'token') then
    update personas set token = encode(gen_random_bytes(16), 'hex')
     where token is null;
  end if;
end $$;
