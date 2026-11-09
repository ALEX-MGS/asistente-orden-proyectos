"""Las herramientas que el modelo puede usar, y cómo se ejecutan.

Regla de diseño: buscar y escribir están separados a propósito. El modelo
busca primero, ve los candidatos, y sólo entonces escribe usando un id.
Así nunca actualiza el mueble equivocado por una coincidencia parcial.
"""
import json

from . import db

HERRAMIENTAS = [
    {
        "name": "buscar_mueble",
        "description": (
            "Busca muebles por texto parcial del nombre o del grupo. "
            "Úsala SIEMPRE antes de actualizar o fechar un mueble. "
            "Devuelve candidatos con su id, avance, en qué etapa va y cuál sigue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Ej: 'mob 7', 'credenza', 'baño primer nivel'"},
                "obra": {"type": "string",
                         "description": ("Opcional. La obra o el grupo dentro de ella. "
                                         "Ej: 'silver deer', 'bosque real', "
                                         "'habitación fátima', 'extras'")},
            },
            "required": ["texto"],
        },
    },
    {
        "name": "actualizar_etapa",
        "description": (
            "Palomea o despalomea una etapa de un mueble. Las etapas son: "
            "aprobado, carpinteria, barniz, entrega, instalacion. "
            "Cada una vale 20%. Requiere el mueble_id que devolvió buscar_mueble."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "etapa": {"type": "string",
                          "enum": ["aprobado", "carpinteria", "barniz", "entrega", "instalacion"]},
                "hecho": {"type": "boolean", "description": "true palomea, false despalomea. Default true."},
            },
            "required": ["mueble_id", "etapa"],
        },
    },
    {
        "name": "marcar_terminado",
        "description": (
            "Marca o desmarca la palomita de Terminado de un mueble. Es un paso "
            "APARTE de las cinco etapas: un mueble con las cinco etapas pero sin "
            "esta palomita va en 83%, no en 100%. Requiere el mueble_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "terminado": {"type": "boolean",
                              "description": "true marca, false desmarca. Default true."},
            },
            "required": ["mueble_id"],
        },
    },
    {
        "name": "poner_nota",
        "description": (
            "Escribe o reemplaza la nota de un mueble — eso que en el tablero "
            "aparece bajo su nombre: 'tapajuntas pendientes', 'por detallar'. "
            "Es la nota DEL MUEBLE; si lo que piden es una tarea de la obra, usa "
            "agregar_pendiente. Manda nota vacía para borrarla. Requiere el mueble_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "nota": {"type": "string"},
            },
            "required": ["mueble_id", "nota"],
        },
    },
    {
        "name": "reiniciar_mueble",
        "description": (
            "Borra TODO el progreso de un mueble de una sola vez: las cinco etapas "
            "y la palomita de Terminado quedan en cero. Úsala cuando pidan borrar, "
            "limpiar o reiniciar el progreso de un mueble — NUNCA lo hagas llamando "
            "actualizar_etapa cinco veces, porque se queda a medias."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"mueble_id": {"type": "string"}},
            "required": ["mueble_id"],
        },
    },
    {
        "name": "crear_mueble",
        "description": "Da de alta un mueble nuevo en una obra. La obra se busca por nombre parcial; si no existe se crea.",
        "input_schema": {
            "type": "object",
            "properties": {
                "obra": {"type": "string"},
                "nombre": {"type": "string"},
                "grupo": {"type": "string", "description": "Opcional. Ej: 'Habitación Fátima', 'extras'"},
            },
            "required": ["obra", "nombre"],
        },
    },
    {
        "name": "fijar_fecha",
        "description": "Pone o cambia la fecha de entrega de un mueble. Formato AAAA-MM-DD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "fecha": {"type": "string", "description": "AAAA-MM-DD"},
            },
            "required": ["mueble_id", "fecha"],
        },
    },
    {
        "name": "agregar_pendiente",
        "description": "Agrega un pendiente a una obra. Para lo de oficina usa la obra 'Oficina'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "obra": {"type": "string"},
                "texto": {"type": "string"},
            },
            "required": ["obra", "texto"],
        },
    },
    {
        "name": "buscar_pendiente",
        "description": "Lista pendientes abiertos. Se puede filtrar por obra, por texto, o traer todos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string"},
                "obra": {"type": "string"},
            },
        },
    },
    {
        "name": "cerrar_pendiente",
        "description": "Marca un pendiente como hecho. Requiere el id que devolvió buscar_pendiente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pendiente_id": {"type": "string"},
                "hecho": {"type": "boolean"},
            },
            "required": ["pendiente_id"],
        },
    },
    {
        "name": "resumen",
        "description": (
            "Estado general. Sin obra devuelve todo; con obra devuelve sólo esa. "
            "Trae atrasados, en proceso, avance por obra y pendientes abiertos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "obra": {"type": "string", "description": "Opcional. Ej: 'silver deer'"},
            },
        },
    },
    {
        "name": "buscar_obra",
        "description": (
            "Busca obras o proyectos por nombre parcial. Sin texto devuelve todas. "
            "Úsala SIEMPRE antes de editar o archivar una obra, o de tocar un "
            "grupo: esas herramientas piden el obra_id y sólo de aquí sale. "
            "Devuelve cuántos muebles y cuántos pendientes abiertos tiene cada una."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string",
                          "description": "Opcional. Ej: 'silver', 'bosque'"},
            },
        },
    },
    {
        "name": "buscar_grupo",
        "description": (
            "Lista las habitaciones o grupos de una obra, con cuántos muebles "
            "tiene cada uno. Requiere el obra_id de buscar_obra. Úsala antes de "
            "renombrar o archivar un grupo, para usar el nombre exacto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"obra_id": {"type": "string"}},
            "required": ["obra_id"],
        },
    },
    {
        "name": "renombrar_mueble",
        "description": (
            "Le cambia el nombre a un mueble. Sólo el nombre: no mueve etapas ni "
            "nada más. Requiere el mueble_id de buscar_mueble."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "nombre": {"type": "string"},
            },
            "required": ["mueble_id", "nombre"],
        },
    },
    {
        "name": "archivar_mueble",
        "description": (
            "Saca un mueble del tablero. NO lo borra: la fila se queda en la base "
            "con todo su historial y deshacer lo regresa. Es lo que hay que usar "
            "cuando pidan quitar, eliminar o borrar un mueble del tablero — no "
            "confundir con reiniciar_mueble, que sólo le quita el progreso. "
            "Con archivado:false lo regresa al tablero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mueble_id": {"type": "string"},
                "archivado": {"type": "boolean",
                              "description": "true lo saca, false lo regresa. Default true."},
            },
            "required": ["mueble_id"],
        },
    },
    {
        "name": "renombrar_grupo",
        "description": (
            "Le cambia el nombre a una habitación o grupo dentro de una obra; "
            "se actualiza en todos sus muebles de un golpe. Requiere el obra_id "
            "y el nombre exacto del grupo (de buscar_grupo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "obra_id": {"type": "string"},
                "grupo": {"type": "string", "description": "El nombre actual, exacto"},
                "nuevo": {"type": "string"},
            },
            "required": ["obra_id", "grupo", "nuevo"],
        },
    },
    {
        "name": "archivar_grupo",
        "description": (
            "Saca del tablero todos los muebles de una habitación o grupo. No los "
            "borra; deshacer los regresa. Requiere el obra_id y el nombre exacto "
            "del grupo. PREGUNTA ANTES: avisa cuántos muebles se van y espera el sí."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "obra_id": {"type": "string"},
                "grupo": {"type": "string"},
            },
            "required": ["obra_id", "grupo"],
        },
    },
    {
        "name": "editar_obra",
        "description": (
            "Cambia el nombre, la fecha de entrega o la nota de una obra. Manda "
            "SÓLO los campos que cambian. Requiere el obra_id de buscar_obra. "
            "Para la fecha de entrega de un MUEBLE usa fijar_fecha, no esto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "obra_id": {"type": "string"},
                "nombre": {"type": "string"},
                "fecha_entrega": {"type": "string",
                                  "description": "AAAA-MM-DD, o vacío para quitarla"},
                "nota": {"type": "string"},
            },
            "required": ["obra_id"],
        },
    },
    {
        "name": "archivar_obra",
        "description": (
            "Saca una obra entera del tablero, con todos sus muebles. No borra "
            "nada y deshacer la regresa, pero es el cambio más grande que puedes "
            "hacer: PREGUNTA ANTES SIEMPRE, diciendo el nombre de la obra y "
            "cuántos muebles se van, y espera el sí. Con archivado:false la regresa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "obra_id": {"type": "string"},
                "archivado": {"type": "boolean",
                              "description": "true la saca, false la regresa. Default true."},
            },
            "required": ["obra_id"],
        },
    },
    {
        "name": "archivar_pendiente",
        "description": (
            "Saca un pendiente del tablero porque ya no aplica o estaba mal "
            "escrito. Es DISTINTO de cerrar_pendiente: cerrar es 'ya se hizo', "
            "archivar es 'esto no iba'. Requiere el id de buscar_pendiente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pendiente_id": {"type": "string"},
                "archivado": {"type": "boolean"},
            },
            "required": ["pendiente_id"],
        },
    },
    {
        "name": "deshacer",
        "description": "Revierte el último cambio que hizo esta persona. Úsala cuando digan que te equivocaste.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Las que escriben. Después de una de estas el asistente debe confirmar
# exactamente lo que quedó anotado.
ESCRITURA = {"actualizar_etapa", "marcar_terminado", "reiniciar_mueble", "poner_nota",
             "crear_mueble", "fijar_fecha", "agregar_pendiente",
             "cerrar_pendiente", "deshacer",
             "renombrar_mueble", "archivar_mueble", "renombrar_grupo",
             "archivar_grupo", "editar_obra", "archivar_obra", "archivar_pendiente"}

# Los campos que editar_obra acepta. El modelo manda sólo los que cambian;
# lo que no venga no se toca.
CAMPOS_OBRA = ("nombre", "fecha_entrega", "nota")


def ejecutar(nombre: str, args: dict, persona_id: str | None, mensaje: str | None):
    """Corre una herramienta y devuelve su resultado como texto para el modelo."""
    try:
        if nombre == "buscar_mueble":
            r = db.buscar_mueble(args["texto"], args.get("obra"))
        elif nombre == "actualizar_etapa":
            r = db.actualizar_etapa(args["mueble_id"], args["etapa"],
                                    args.get("hecho", True), persona_id, mensaje)
        elif nombre == "marcar_terminado":
            r = db.marcar_terminado(args["mueble_id"], args.get("terminado", True),
                                    persona_id, mensaje)
        elif nombre == "poner_nota":
            r = db.poner_nota(args["mueble_id"], args.get("nota", ""),
                              persona_id, mensaje)
        elif nombre == "reiniciar_mueble":
            r = db.reiniciar_mueble(args["mueble_id"], persona_id, mensaje)
        elif nombre == "crear_mueble":
            r = db.crear_mueble(args["obra"], args["nombre"], args.get("grupo"),
                                persona_id, mensaje)
        elif nombre == "fijar_fecha":
            r = db.fijar_fecha(args["mueble_id"], args["fecha"], persona_id, mensaje)
        elif nombre == "agregar_pendiente":
            r = db.agregar_pendiente(args["obra"], args["texto"], persona_id, mensaje)
        elif nombre == "buscar_pendiente":
            r = db.buscar_pendiente(args.get("texto"), args.get("obra"))
        elif nombre == "cerrar_pendiente":
            r = db.cerrar_pendiente(args["pendiente_id"], args.get("hecho", True),
                                    persona_id, mensaje)
        elif nombre == "resumen":
            r = db.resumen(args.get("obra"))

        # --- lo que el panel ya hacía y el bot no (14_bot_al_dia.sql) ---
        elif nombre == "buscar_obra":
            r = db.buscar_obra(args.get("texto"))
        elif nombre == "buscar_grupo":
            r = db.buscar_grupo(args["obra_id"])
        elif nombre == "renombrar_mueble":
            r = db.renombrar_mueble(args["mueble_id"], args["nombre"],
                                    persona_id, mensaje)
        elif nombre == "archivar_mueble":
            r = db.archivar_mueble(args["mueble_id"], args.get("archivado", True),
                                   persona_id, mensaje)
        elif nombre == "renombrar_grupo":
            r = db.renombrar_grupo(args["obra_id"], args["grupo"], args["nuevo"],
                                   persona_id, mensaje)
        elif nombre == "archivar_grupo":
            r = db.archivar_grupo(args["obra_id"], args["grupo"], persona_id, mensaje)
        elif nombre == "editar_obra":
            cambios = {c: args[c] for c in CAMPOS_OBRA if c in args}
            if not cambios:
                return ("Error: no mandaste ningún campo que cambiar. "
                        f"Los que acepta son: {', '.join(CAMPOS_OBRA)}."), True
            r = db.editar_obra(args["obra_id"], cambios, persona_id, mensaje)
        elif nombre == "archivar_obra":
            r = db.archivar_obra(args["obra_id"], args.get("archivado", True),
                                 persona_id, mensaje)
        elif nombre == "archivar_pendiente":
            r = db.archivar_pendiente(args["pendiente_id"],
                                      args.get("archivado", True), persona_id, mensaje)

        elif nombre == "deshacer":
            r = db.deshacer(persona_id)
        else:
            return f"Error: no existe la herramienta {nombre}", True
        return json.dumps(r, ensure_ascii=False, default=str), False
    except Exception as e:
        texto = f"Error: {e}"
        # El tropiezo más común: usar un id que devolvió OTRA herramienta.
        # Los ids no son intercambiables entre muebles y pendientes.
        if "No existe ese mueble" in texto or "No existe ese pendiente" in texto:
            texto += ("\nPISTA: ese id no corresponde. Vuelve a llamar a buscar_mueble "
                      "(o buscar_pendiente) y usa el id que ESA búsqueda devuelva. "
                      "Nunca reutilices un id que te dio otra herramienta.")
        elif "No existe esa obra" in texto:
            texto += ("\nPISTA: ese obra_id no corresponde. Llama a buscar_obra y usa "
                      "el id que devuelva. El id de un mueble no sirve como obra_id.")
        elif "No hay muebles" in texto:
            texto += ("\nPISTA: el nombre del grupo tiene que ser exacto. Llama a "
                      "buscar_grupo con ese obra_id para ver cómo se llaman.")
        return texto, True
