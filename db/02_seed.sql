-- =====================================================================
-- Datos iniciales · Grupo Morales
-- Generado del export del panel (grupomorales20260902.csv).
-- Ejecutar después de 01_schema.sql. Se puede volver a correr sin duplicar.
-- =====================================================================

-- --- Etapas del proceso (20 % cada una) ------------------------------
insert into etapas (id, clave, nombre, orden, peso) values
  (1, 'aprobado',    'Aprobado',    1, 0.200),
  (2, 'carpinteria', 'Carpintería', 2, 0.200),
  (3, 'barniz',      'Barniz',      3, 0.200),
  (4, 'entrega',     'Entrega',     4, 0.200),
  (5, 'instalacion', 'Instalación', 5, 0.200)
on conflict (id) do update set
  clave = excluded.clave, nombre = excluded.nombre,
  orden = excluded.orden, peso  = excluded.peso;

-- --- Personas autorizadas en WhatsApp --------------------------------
-- Cambia el teléfono por el tuyo en formato E.164 y agrega al taller.
insert into personas (nombre, telefono, rol) values
  ('Alex', '+520000000000', 'admin')
on conflict (telefono) do nothing;

-- --- Obras -----------------------------------------------------------
insert into obras (nombre, tipo) values
  ('Silver Deer', 'obra'),
  ('Bosque Real', 'obra'),
  ('Varios', 'obra'),
  ('Ahuehuetes', 'obra'),
  ('Héctor', 'obra'),
  ('Liliana', 'obra'),
  ('Hotel Brik', 'obra'),
  ('Pepe Simón', 'obra'),
  ('Sra. Ana María · Av. Pacífico', 'obra'),
  ('Laredo', 'obra'),
  ('Residencial Torres', 'obra'),
  ('arq hugo', 'obra'),
  ('Amigo Papá', 'obra'),
  ('Oficina', 'interna')
on conflict (nombre) do nothing;

-- --- Muebles ---------------------------------------------------------
-- El trigger de 01_schema.sql crea las 5 etapas de cada mueble en falso;
-- abajo se marcan las que ya estaban palomeadas en el panel.
insert into muebles (obra_id, grupo, nombre, fecha_entrega, nota, orden)
select o.id, v.grupo, v.nombre, v.fecha::date, v.nota, v.orden
from (values
  ('Silver Deer', null, 'MOB 1', null, null, 1),
  ('Silver Deer', null, 'Forrado encino MOB 1', null, null, 2),
  ('Silver Deer', null, 'MOB 2', null, null, 3),
  ('Silver Deer', null, 'MOB 3', null, null, 4),
  ('Silver Deer', null, 'MOB 4 y 5 escritorios', '2026-08-06', null, 5),
  ('Silver Deer', null, 'MOB 4 y 5 gabinetes altos', null, null, 6),
  ('Silver Deer', null, 'MOB 6', null, null, 7),
  ('Silver Deer', null, 'MOB 7', null, null, 8),
  ('Silver Deer', null, 'Forrado encino MOB 7', null, null, 9),
  ('Silver Deer', null, 'MOB 8', null, 'por detallarse', 10),
  ('Silver Deer', null, 'MOB 9', null, 'por detallar', 11),
  ('Silver Deer', null, 'MOB 10', null, 'tapajuntas pendientes', 12),
  ('Silver Deer', null, 'MOB 11', null, 'detallar', 13),
  ('Silver Deer', null, 'MOB 12', null, 'detallar', 14),
  ('Silver Deer', null, 'MOB 13', null, 'pendiente por boiler', 15),
  ('Silver Deer', null, 'Mueble de baño primer nivel', null, null, 16),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 1', null, null, 17),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 2', null, null, 18),
  ('Silver Deer', null, 'Taller Sastre', null, null, 19),
  ('Silver Deer', null, 'Antepecho/Tapa de corniza registrable', null, null, 20),
  ('Silver Deer', null, 'Mueble baño 4 en melamina', null, null, 21),
  ('Silver Deer', null, 'Mueble de área de lavado/Mueble para artículos de limpieza', null, null, 22),
  ('Silver Deer', null, 'mueble de baño melamina', null, null, 23),
  ('Silver Deer', null, 'Entrepaños para mueble metálico', null, null, 24),
  ('Silver Deer', null, 'Lockers', null, null, 25),
  ('Silver Deer', null, 'Mueble de bote de basura', null, null, 26),
  ('Silver Deer', null, 'Mueble para toallas', null, null, 27),
  ('Silver Deer', null, 'Modificación de patas de escritorios', null, null, 28),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', null, null, 1),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', null, 'Se instalará y llevará último módulo cuando se lleve escuadra correspondiente', 2),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', null, null, 3),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', null, null, 4),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', null, null, 5),
  ('Bosque Real', 'extras', 'Armero con puerta corrediza', null, null, 6),
  ('Bosque Real', null, 'mesa auxiliar erick', null, null, 7),
  ('Bosque Real', null, 'Mesa auxiliar fatima', null, null, 8),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', null, null, 9),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', null, null, 10),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', null, null, 11),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', null, null, 12),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', null, null, 13),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', null, null, 14),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', null, null, 15),
  ('Varios', 'skin society dra alejandra', 'mueble archivero', null, null, 1),
  ('Varios', 'moises', 'mueble de nogal', null, null, 2)
) as v(obra, grupo, nombre, fecha, nota, orden)
join obras o on o.nombre = v.obra
where not exists (
  select 1 from muebles m
  where m.obra_id = o.id and m.nombre = v.nombre
    and m.grupo is not distinct from v.grupo
);

-- --- Etapas ya cumplidas de cada mueble -------------------------------
update mueble_etapas me set hecho = true
from muebles m, obras o, etapas e, (values
  ('Silver Deer', null, 'MOB 1', 'aprobado'),
  ('Silver Deer', null, 'MOB 1', 'carpinteria'),
  ('Silver Deer', null, 'MOB 1', 'barniz'),
  ('Silver Deer', null, 'MOB 1', 'entrega'),
  ('Silver Deer', null, 'MOB 1', 'instalacion'),
  ('Silver Deer', null, 'Forrado encino MOB 1', 'aprobado'),
  ('Silver Deer', null, 'Forrado encino MOB 1', 'carpinteria'),
  ('Silver Deer', null, 'Forrado encino MOB 1', 'barniz'),
  ('Silver Deer', null, 'Forrado encino MOB 1', 'entrega'),
  ('Silver Deer', null, 'Forrado encino MOB 1', 'instalacion'),
  ('Silver Deer', null, 'MOB 2', 'aprobado'),
  ('Silver Deer', null, 'MOB 3', 'aprobado'),
  ('Silver Deer', null, 'MOB 4 y 5 escritorios', 'aprobado'),
  ('Silver Deer', null, 'MOB 4 y 5 escritorios', 'carpinteria'),
  ('Silver Deer', null, 'MOB 4 y 5 escritorios', 'barniz'),
  ('Silver Deer', null, 'MOB 4 y 5 gabinetes altos', 'aprobado'),
  ('Silver Deer', null, 'MOB 4 y 5 gabinetes altos', 'carpinteria'),
  ('Silver Deer', null, 'MOB 6', 'aprobado'),
  ('Silver Deer', null, 'MOB 7', 'aprobado'),
  ('Silver Deer', null, 'MOB 7', 'carpinteria'),
  ('Silver Deer', null, 'MOB 7', 'barniz'),
  ('Silver Deer', null, 'MOB 7', 'entrega'),
  ('Silver Deer', null, 'MOB 7', 'instalacion'),
  ('Silver Deer', null, 'Forrado encino MOB 7', 'aprobado'),
  ('Silver Deer', null, 'Forrado encino MOB 7', 'carpinteria'),
  ('Silver Deer', null, 'Forrado encino MOB 7', 'barniz'),
  ('Silver Deer', null, 'Forrado encino MOB 7', 'entrega'),
  ('Silver Deer', null, 'MOB 8', 'aprobado'),
  ('Silver Deer', null, 'MOB 8', 'carpinteria'),
  ('Silver Deer', null, 'MOB 8', 'barniz'),
  ('Silver Deer', null, 'MOB 8', 'entrega'),
  ('Silver Deer', null, 'MOB 8', 'instalacion'),
  ('Silver Deer', null, 'MOB 9', 'aprobado'),
  ('Silver Deer', null, 'MOB 9', 'carpinteria'),
  ('Silver Deer', null, 'MOB 9', 'barniz'),
  ('Silver Deer', null, 'MOB 9', 'entrega'),
  ('Silver Deer', null, 'MOB 9', 'instalacion'),
  ('Silver Deer', null, 'MOB 10', 'aprobado'),
  ('Silver Deer', null, 'MOB 10', 'carpinteria'),
  ('Silver Deer', null, 'MOB 10', 'barniz'),
  ('Silver Deer', null, 'MOB 10', 'entrega'),
  ('Silver Deer', null, 'MOB 10', 'instalacion'),
  ('Silver Deer', null, 'MOB 11', 'aprobado'),
  ('Silver Deer', null, 'MOB 11', 'carpinteria'),
  ('Silver Deer', null, 'MOB 11', 'barniz'),
  ('Silver Deer', null, 'MOB 11', 'entrega'),
  ('Silver Deer', null, 'MOB 11', 'instalacion'),
  ('Silver Deer', null, 'MOB 12', 'aprobado'),
  ('Silver Deer', null, 'MOB 12', 'carpinteria'),
  ('Silver Deer', null, 'MOB 12', 'barniz'),
  ('Silver Deer', null, 'MOB 12', 'entrega'),
  ('Silver Deer', null, 'MOB 12', 'instalacion'),
  ('Silver Deer', null, 'MOB 13', 'aprobado'),
  ('Silver Deer', null, 'Mueble de baño primer nivel', 'aprobado'),
  ('Silver Deer', null, 'Mueble de baño primer nivel', 'carpinteria'),
  ('Silver Deer', null, 'Mueble de baño primer nivel', 'barniz'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 1', 'aprobado'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 1', 'carpinteria'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 1', 'barniz'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 2', 'aprobado'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 2', 'carpinteria'),
  ('Silver Deer', null, 'Mueble de baño segundo nivel 2', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', 'aprobado'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', 'carpinteria'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', 'entrega'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble frigobar', 'instalacion'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', 'aprobado'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', 'carpinteria'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', 'entrega'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble credenza', 'instalacion'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', 'aprobado'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', 'carpinteria'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', 'entrega'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble librero', 'instalacion'),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', 'aprobado'),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', 'carpinteria'),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', 'entrega'),
  ('Bosque Real', 'Habitación Fátima', 'Escritorio con cajones', 'instalacion'),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', 'aprobado'),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', 'carpinteria'),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', 'barniz'),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', 'entrega'),
  ('Bosque Real', 'extras', 'Cambio en librero a puerta corrediza en puertas inferiores', 'instalacion'),
  ('Bosque Real', 'extras', 'Armero con puerta corrediza', 'aprobado'),
  ('Bosque Real', 'extras', 'Armero con puerta corrediza', 'carpinteria'),
  ('Bosque Real', 'extras', 'Armero con puerta corrediza', 'barniz'),
  ('Bosque Real', 'extras', 'Armero con puerta corrediza', 'entrega'),
  ('Bosque Real', null, 'mesa auxiliar erick', 'aprobado'),
  ('Bosque Real', null, 'mesa auxiliar erick', 'carpinteria'),
  ('Bosque Real', null, 'mesa auxiliar erick', 'barniz'),
  ('Bosque Real', null, 'mesa auxiliar erick', 'entrega'),
  ('Bosque Real', null, 'mesa auxiliar erick', 'instalacion'),
  ('Bosque Real', null, 'Mesa auxiliar fatima', 'aprobado'),
  ('Bosque Real', null, 'Mesa auxiliar fatima', 'carpinteria'),
  ('Bosque Real', null, 'Mesa auxiliar fatima', 'barniz'),
  ('Bosque Real', null, 'Mesa auxiliar fatima', 'entrega'),
  ('Bosque Real', null, 'Mesa auxiliar fatima', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Cornisa sobre lambrín', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Lambrín sobre credenza', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Mueble frigobar', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Mueble credenza', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Mueble librero', 'instalacion'),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', 'aprobado'),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', 'carpinteria'),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', 'barniz'),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', 'entrega'),
  ('Bosque Real', 'Habitación Erick', 'Escritorio con cajones', 'instalacion'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', 'aprobado'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', 'carpinteria'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', 'barniz'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', 'entrega'),
  ('Bosque Real', 'Habitación Fátima', 'Mueble impresora', 'instalacion'),
  ('Varios', 'skin society dra alejandra', 'mueble archivero', 'aprobado'),
  ('Varios', 'skin society dra alejandra', 'mueble archivero', 'carpinteria'),
  ('Varios', 'skin society dra alejandra', 'mueble archivero', 'barniz'),
  ('Varios', 'moises', 'mueble de nogal', 'aprobado'),
  ('Varios', 'moises', 'mueble de nogal', 'carpinteria'),
  ('Varios', 'moises', 'mueble de nogal', 'barniz')
) as v(obra, grupo, nombre, etapa)
where m.obra_id = o.id and o.nombre = v.obra
  and m.nombre = v.nombre and m.grupo is not distinct from v.grupo
  and e.clave = v.etapa
  and me.mueble_id = m.id and me.etapa_id = e.id
  and me.hecho = false;

-- --- Pendientes -------------------------------------------------------
insert into pendientes (obra_id, texto, hecho)
select o.id, v.texto, v.hecho
from (values
  ('Ahuehuetes', 'Colocar resbalón puerta dorada, comprar resortes', false),
  ('Ahuehuetes', 'Ajustar puertas de comunicación de nogal', false),
  ('Ahuehuetes', 'Hacer retoques que faltaron', false),
  ('Héctor', 'Colocar piezas de bisagras cocina', false),
  ('Liliana', 'Entregar patas y hacer retoques faltantes', true),
  ('Liliana', 'Revisar que estén soportes de entrepaños — juntar todos los buenos entrepaños (Tuxpan 54 Alejandra / mueble archivero)', false),
  ('Liliana', 'Programar entrega e instalación de mueble archivero (Tuxpan 54 Alejandra)', false),
  ('Liliana', 'Llevar silicón blanco brillante (Tuxpan 54 Alejandra)', false),
  ('Hotel Brik', 'Pruebas para plafón', true),
  ('Pepe Simón', 'Poner luz', false),
  ('Pepe Simón', 'Colocar vidrios', false),
  ('Pepe Simón', 'Hacer lambrín', false),
  ('Sra. Ana María · Av. Pacífico', 'Instalación de closets', true),
  ('Laredo', 'Fábrica de cajones', true),
  ('Residencial Torres', 'Hacer mediciones', true),
  ('arq hugo', 'mandar resumen de cuentas', false),
  ('Amigo Papá', 'Mueble Trolam: programar instalación', false),
  ('Amigo Papá', 'Entrepaños: buscar broca para muro del tamaño de varilla roscada', false),
  ('Amigo Papá', 'Entrepaños: llevar clavos, herramienta, silicones y retoques', false),
  ('Oficina', 'comprar baleros', true)
) as v(obra, texto, hecho)
join obras o on o.nombre = v.obra
where not exists (
  select 1 from pendientes p where p.obra_id = o.id and p.texto = v.texto
);

-- --- Cotizaciones -----------------------------------------------------
insert into cotizaciones (cliente, concepto, monto, fecha, estado, nota)
select v.cliente, v.concepto, v.monto::numeric, v.fecha::date, v.estado, v.nota
from (values
  ('chain + siman', 'oficina cobre', '425000', '2026-08-03', 'revision', null)
) as v(cliente, concepto, monto, fecha, estado, nota)
where not exists (
  select 1 from cotizaciones c
  where c.cliente = v.cliente and c.concepto is not distinct from v.concepto
);

