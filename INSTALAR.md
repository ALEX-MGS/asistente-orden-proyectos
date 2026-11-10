# Montar una copia para un cliente

Esto es para cuando **tú** montas y operas la copia, y el cliente sólo
recibe dos cosas: un link al tablero y, si se puede, un número de
WhatsApp. No abre ninguna cuenta ni toca nada técnico.

Son unas dos horas la primera vez. Nada requiere programar, pero sí ir
en orden: cada paso usa algo del anterior.

---

## Antes de empezar, tres cosas que conviene tener claras

**Cada copia es un sistema aparte.** Base propia, despliegue propio,
variables propias. No se mezclan datos entre tu taller y el del cliente.
Eso es bueno (nadie ve lo del otro) y es la razón de que montar la
segunda copia sea montar todo otra vez.

**Las cuentas gratis se acaban en la segunda copia.** Supabase da **2
proyectos activos** por organización: el tuyo y el del primer cliente, y
ya. El tercero pide el plan de pago. Railway cobra por uso, unos 5 USD
al mes por servicio, así que dos copias son unos 10.

**Los datos del cliente quedan en tu cuenta.** Sus obras, sus clientes,
sus montos. Si algún día se separan, hay que sacárselos: el panel tiene
**Descargar respaldo (.json)** y **Descargar para Excel (.csv)**, y con
eso se va con todo. Vale la pena decírselo desde el principio.

---

## El número de WhatsApp: léelo antes de prometer nada

Aquí está el único nudo de verdad.

El sandbox de Twilio da **un número por cuenta de Twilio, con un solo
webhook**. Tu taller ya lo está usando apuntando a tu despliegue. Si el
cliente le escribe a ese mismo número, su mensaje llega a **tu** tablero,
no al suyo. **Dos copias no pueden compartir un número.** Tienes tres
caminos:

**1. Sólo el tablero, sin WhatsApp (lo más rápido, y suele bastar).**
El cliente abre su link y trabaja ahí: palomea etapas, agrega muebles, y
—esto es lo que casi nadie espera— **dicta con el micrófono del panel**.
El botón 🎙 usa exactamente el mismo asistente que WhatsApp: entiende
lenguaje natural, busca el mueble, escribe en la base y deja su rastro.
Sin número, sin `join`, sin sesiones que caducan. Para un piloto es
suficiente y se monta hoy.

**2. Una segunda cuenta de Twilio (gratis).** Otra cuenta = otro sandbox
= otro número y otro webhook. El cliente manda el `join xxx` a ESE
número. Funciona ya, pero arrastra lo del sandbox: la sesión caduca a
los 3 días y hay tope de mensajes al día. Sirve para probar, no para
operar.

**3. Número propio con la API de Meta.** Es lo serio, y lo único que
quita las limitaciones. Pide verificación del negocio **dueño del
número** y toma días. Detalle que importa si esto va a ser un producto:
si usas un número a nombre de Grupo Morales para atender a tu cliente,
sus mensajes van a venir de "Grupo Morales". Si la idea es venderlo,
conviene un número a nombre del producto, no de tu carpintería.

Mi sugerencia: arranca con la **1**, y si el cliente pide WhatsApp
después de usarlo un rato, ahí vas por la **3**.

---

## 1. La base de datos

1. En [supabase.com](https://supabase.com): **New project**. Guarda la
   contraseña que te pida, no se vuelve a mostrar.
2. **SQL Editor** → pega y corre los archivos de `db/`, **en este orden**:

   ```
   01_schema.sql
   02_vacio.sql          ← la semilla vacía; NO corras 02_seed.sql,
                           ése trae las obras de Grupo Morales
   03_funciones.sql
   04_terminado.sql
   05_correcciones.sql
   06_utilidades.sql
   07_deshacer_lote.sql
   08_notas.sql
   09_terminado_completa.sql
   10_edicion.sql
   11_crear.sql
   12_vista_y_tokens.sql
   13_archivar.sql
   14_bot_al_dia.sql
   15_resumen_diario.sql
   ```

   Uno por uno. Si alguno marca error, **párate ahí**: los de abajo
   dependen de los de arriba.

3. Antes de correr `02_vacio.sql`, ábrelo y cámbiale el nombre y el
   teléfono al admin — que seas tú, no el cliente: tú lo vas a operar.

4. **Settings → API**: copia `Project URL` y la llave `service_role`.
   Esa llave se salta todos los permisos: nunca en un navegador, nunca
   en el repo, sólo en las variables de Railway.

Comprobar: en el SQL Editor, `select count(*) from funciones_del_asistente();`
debe dar **35**.

---

## 2. El servidor

1. En [railway.com](https://railway.com): **New Project → Deploy from
   GitHub repo**, y elige el mismo repositorio. Es el mismo código para
   todas las copias; lo que cambia son las variables.
2. **Settings → Networking → Generate Domain**. Ésa es la URL de esta copia.
3. **Variables**:

   ```
   SUPABASE_URL=            (el de ESTE proyecto, no el tuyo)
   SUPABASE_SERVICE_ROLE_KEY=
   OPENAI_API_KEY=          (puede ser la misma tuya)
   PROVEEDOR=openai
   MODELO=gpt-4o

   NEGOCIO=Carpintería del cliente
   NEGOCIO_PERFIL=(ver abajo)

   TABLERO_URL=https://ESTA-COPIA.up.railway.app
   TABLERO_TOKEN=(una cadena larga inventada, distinta a la tuya)
   ```

   Si no vas a poner WhatsApp todavía, las variables de Twilio se quedan
   vacías: el panel y el dictado funcionan sin ellas.

Comprobar: abre la URL. Debe contestar `{"ok":true,"faltan":[], ...}`.

---

## 3. `NEGOCIO_PERFIL`, que es lo que hace la diferencia

Es lo que el asistente sabe del taller: a qué se dedica y **cómo habla
su gente**. Entra tal cual en las instrucciones del modelo. Sin esto el
bot funciona, pero no entiende los modismos de la casa.

El de Grupo Morales, de ejemplo:

```
Es una carpintería de la Ciudad de México con más de cien años de oficio.

Cómo habla la gente aquí, y cómo debes entenderla:
- "mob" es mueble, y casi siempre viene con número: "el mob 7", "mob 4 y 5".
- "arq" es arquitecto.
- Las obras se llaman por su nombre corto: Silver Deer, Bosque Real, Onofre.
- "salió de barniz" quiere decir que la etapa de barniz ya quedó.
- "ya se entregó", "ya se instaló", "ya lo pusieron" son etapas cumplidas.
```

Siéntate diez minutos con el cliente a sacar el suyo. Es lo que separa
un bot que entiende de uno al que hay que dictarle como a una máquina —
y es lo único que no se puede copiar de un taller a otro.

---

## 4. Las personas y sus links

Da de alta a cada quien en el SQL Editor. El cliente y su gente van como
`taller`; tú como `admin`.

```sql
insert into personas (nombre, telefono, rol) values
  ('Nombre del cliente', 'solo-panel-cliente', 'taller');

update personas set token = encode(gen_random_bytes(16),'hex')
 where token is null;
```

El teléfono es obligatorio pero sólo lo usa WhatsApp. Si esa persona
nada más va a entrar al tablero, pon cualquier texto que no choque, como
arriba. Cuando haya número, lo cambias por el de verdad.

Luego, desde tu Mac:

```
python links.py
```

Te imprime el link de cada quien. **Mándalos uno por uno.** Quien tiene
el link puede editar ese tablero, y cada cambio queda firmado con su
nombre en la bitácora.

Si uno se filtra: `python links.py --renovar "Nombre"` cambia ése y
ninguno más.

---

## 5. WhatsApp (sólo si vas por el camino 2 o 3)

1. En Twilio: **Messaging → Try it out → Send a WhatsApp message**. Te da
   el número de pruebas y un código tipo `join algo-algo`.
2. Cada teléfono que vaya a usarlo manda ese `join ...` al número.
3. **Sandbox settings** → en *When a message comes in*:
   `https://ESTA-COPIA.up.railway.app/whatsapp`, método **POST**.
   Sin `?k=` ni nada al final: Twilio firma esa URL exacta, y si no
   cuadra carácter por carácter todo da 403.
4. Agrega a Railway `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_WHATSAPP_FROM` y `URL_PUBLICA` (la misma del paso 3).
5. Para no equivocarte con el formato del teléfono: que manden un
   mensaje primero y luego

   ```sql
   select telefono, texto from mensajes
    where persona_id is null order by created_at desc limit 5;

   update personas set telefono = '+52...' where nombre = 'Nombre del cliente';
   ```

---

## 6. El resumen de la mañana (opcional)

En Railway: `RESUMEN_HORA=08:47` y `ZONA=America/Mexico_City`. Quién lo
recibe sale de la base:

```sql
update personas set resumen_diario = true where nombre = 'Nombre';
```

Evita las horas en punto. Y ojo: un mensaje que **inicia** el bot es
justo lo que el sandbox no maneja bien — sin número propio, el resumen
sólo llega si esa persona le escribió al bot hace poco.

---

## Comprobación final

Con el `.env` de esta copia apuntando a su base:

```
python revisar.py
```

Debe listar **35 funciones** en ok. Luego abre el tablero con tu link,
crea un proyecto y un mueble, palomea una etapa y dicta algo con el 🎙.
Si las cuatro cosas responden, está montado.

---

## Si algo falla

| Síntoma | Casi siempre es |
|---|---|
| El panel dice "No autorizado" | el link no trae `?k=`, o el token no existe en `personas` |
| WhatsApp dice "número no autorizado" | falta esa persona en `personas`, o el teléfono tiene otro formato |
| Twilio da 403 en el log | `URL_PUBLICA` no es idéntica a la que pusiste en Twilio |
| Los mensajes del cliente llegan a TU tablero | las dos copias comparten el número de Twilio: lee el apartado del número |
| El bot deja de contestar a los 3 días | caducó la sesión del sandbox: manda otra vez `join ...` |
| El panel carga vacío | falta alguna migración; corre `python revisar.py` |
| El dictado no sirve | falta `OPENAI_API_KEY`, o `MODELO_VOZ` apunta a un modelo que tu cuenta no tiene |
