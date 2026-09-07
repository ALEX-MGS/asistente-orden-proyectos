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
                "obra": {"type": "string", "description": "Opcional. Ej: 'silver deer', 'bosque real'"},
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
        "name": "deshacer",
        "description": "Revierte el último cambio que hizo esta persona. Úsala cuando digan que te equivocaste.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Las que escriben. Después de una de estas el asistente debe confirmar
# exactamente lo que quedó anotado.
ESCRITURA = {"actualizar_etapa", "crear_mueble", "fijar_fecha",
             "agregar_pendiente", "cerrar_pendiente", "deshacer"}


def ejecutar(nombre: str, args: dict, persona_id: str | None, mensaje: str | None):
    """Corre una herramienta y devuelve su resultado como texto para el modelo."""
    try:
        if nombre == "buscar_mueble":
            r = db.buscar_mueble(args["texto"], args.get("obra"))
        elif nombre == "actualizar_etapa":
            r = db.actualizar_etapa(args["mueble_id"], args["etapa"],
                                    args.get("hecho", True), persona_id, mensaje)
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
        elif nombre == "deshacer":
            r = db.deshacer(persona_id)
        else:
            return f"Error: no existe la herramienta {nombre}", True
        return json.dumps(r, ensure_ascii=False, default=str), False
    except Exception as e:
        return f"Error: {e}", True
