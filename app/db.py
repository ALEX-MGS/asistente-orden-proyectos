"""Acceso a Supabase.

Todas las escrituras pasan por las funciones SQL de db/03_funciones.sql.
Aquí no se arma SQL a mano: cada función de abajo es una llamada a una
función que ya validó, buscó y dejó rastro en bitácora.
"""
from typing import Any, Optional

from supabase import Client, create_client

from . import config

_cliente: Optional[Client] = None


def db() -> Client:
    global _cliente
    if _cliente is None:
        _cliente = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _cliente


def _rpc(nombre: str, **params) -> Any:
    return db().rpc(nombre, params).execute().data


# --- lectura ----------------------------------------------------------

def buscar_mueble(texto: str, obra: str | None = None):
    return _rpc("buscar_mueble", p_texto=texto, p_obra=obra)


def buscar_pendiente(texto: str | None = None, obra: str | None = None):
    return _rpc("buscar_pendiente", p_texto=texto, p_obra=obra)


def resumen(obra: str | None = None):
    return _rpc("resumen", p_obra=obra)


# --- escritura --------------------------------------------------------

def actualizar_etapa(mueble_id, etapa, hecho=True, persona=None, mensaje=None):
    return _rpc("actualizar_etapa", p_mueble_id=mueble_id, p_etapa=etapa,
                p_hecho=hecho, p_persona=persona, p_mensaje=mensaje)


def crear_mueble(obra, nombre, grupo=None, persona=None, mensaje=None):
    return _rpc("crear_mueble", p_obra=obra, p_nombre=nombre, p_grupo=grupo,
                p_persona=persona, p_mensaje=mensaje)


def fijar_fecha(mueble_id, fecha, persona=None, mensaje=None):
    return _rpc("fijar_fecha", p_mueble_id=mueble_id, p_fecha=fecha,
                p_persona=persona, p_mensaje=mensaje)


def agregar_pendiente(obra, texto, persona=None, mensaje=None):
    return _rpc("agregar_pendiente", p_obra=obra, p_texto=texto,
                p_persona=persona, p_mensaje=mensaje)


def cerrar_pendiente(pendiente_id, hecho=True, persona=None, mensaje=None):
    return _rpc("cerrar_pendiente", p_pendiente_id=pendiente_id, p_hecho=hecho,
                p_persona=persona, p_mensaje=mensaje)


def deshacer(persona):
    return _rpc("deshacer", p_persona=persona)


# --- personas y mensajes ---------------------------------------------

def persona_por_telefono(telefono: str) -> dict | None:
    """El candado. Un número que no esté en `personas` no existe."""
    r = (db().table("personas").select("*")
         .eq("telefono", telefono).eq("activo", True).execute().data)
    return r[0] if r else None


def guardar_mensaje(telefono, direccion, texto, persona_id=None, wa_id=None):
    try:
        db().table("mensajes").insert({
            "telefono": telefono, "direccion": direccion, "texto": texto,
            "persona_id": persona_id, "wa_message_id": wa_id,
        }).execute()
    except Exception:
        pass  # un mensaje repetido choca con wa_message_id: es lo correcto


def ya_procesado(wa_id: str) -> bool:
    if not wa_id:
        return False
    r = db().table("mensajes").select("id").eq("wa_message_id", wa_id).execute().data
    return bool(r)


def historial(telefono: str, limite: int | None = None) -> list[dict]:
    n = limite or config.HISTORIAL
    r = (db().table("mensajes").select("direccion, texto")
         .eq("telefono", telefono).order("created_at", desc=True)
         .limit(n).execute().data)
    return [
        {"role": "user" if m["direccion"] == "entrante" else "assistant",
         "content": m["texto"]}
        for m in reversed(r) if m.get("texto")
    ]
