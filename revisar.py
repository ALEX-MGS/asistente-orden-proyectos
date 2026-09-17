"""¿Dónde se quedó el mensaje?

    python revisar.py

Revisa la cadena completa hacia atrás: qué funciones existen en la base,
qué mensajes llegaron, y qué escribió el asistente de verdad. El primer
renglón que no cuadre es el problema.
"""
import sys
from datetime import datetime, timedelta, timezone

from app import config, db

ESPERADAS = [
    "buscar_mueble", "buscar_pendiente", "resumen",
    "actualizar_etapa", "marcar_terminado", "reiniciar_mueble",
    "crear_mueble", "fijar_fecha", "agregar_pendiente",
    "cerrar_pendiente", "deshacer",
]


def funciones_presentes():
    """Le pregunta a Postgres qué existe, en vez de llamar cada función.

    La versión anterior las invocaba con valores inofensivos para ver si
    tronaban. crear_mueble y agregar_pendiente NO tronaron con cadenas
    vacías: insertaron basura en la base. Nunca más: esto sólo lee.
    """
    try:
        filas = db.db().rpc("funciones_del_asistente", {}).execute().data
        return {f["nombre"] for f in filas}, None
    except Exception as e:
        if "PGRST202" in str(e) or "Could not find the function" in str(e):
            return None, "falta db/06_utilidades.sql"
        return None, str(e)[:80]


def main() -> int:
    faltan = config.faltantes()
    if faltan:
        print("Faltan variables en .env:", ", ".join(faltan))
        return 1

    print("=" * 66)
    print("1. FUNCIONES EN LA BASE")
    print("=" * 66)
    presentes, problema = funciones_presentes()
    if presentes is None:
        print(f"   No se pudo consultar: {problema}")
        print("   Corre db/06_utilidades.sql en el SQL Editor y vuelve a intentar.")
    else:
        ausentes = [n for n in ESPERADAS if n not in presentes]
        for n in ESPERADAS:
            print(f"   {'ok  ' if n in presentes else 'FALTA'}  {n}")
        if ausentes:
            print(f"\n   >>> Faltan {len(ausentes)}. Corre en el SQL Editor, en orden,")
            print("       db/03_funciones.sql, db/04_terminado.sql,")
            print("       db/05_correcciones.sql y db/06_utilidades.sql.")

    print()
    print("=" * 66)
    print("2. ÚLTIMOS MENSAJES DE WHATSAPP")
    print("=" * 66)
    msgs = (db.db().table("mensajes").select("direccion, texto, created_at, persona_id")
            .order("created_at", desc=True).limit(8).execute().data)
    if not msgs:
        print("   Ninguno. El webhook no está guardando: revisa que Twilio apunte")
        print("   a la URL correcta y que la firma cuadre (403 en el log de ngrok).")
    for m in reversed(msgs):
        h = m["created_at"][5:10] + " " + m["created_at"][11:16]
        quien = "tú " if m["direccion"] == "entrante" else "bot"
        sin_persona = "  [número no autorizado]" if not m["persona_id"] else ""
        print(f"   {h}  {quien}  {(m['texto'] or '')[:64]}{sin_persona}")

    print()
    print("=" * 66)
    print("3. LO QUE EL ASISTENTE ESCRIBIÓ DE VERDAD (bitácora)")
    print("=" * 66)
    filas = (db.db().table("bitacora")
             .select("accion, tabla, antes, despues, mensaje_origen, deshecho, created_at")
             .order("created_at", desc=True).limit(10).execute().data)
    if not filas:
        print("   VACÍA. El bot contesta pero no está escribiendo nada.")
        print("   Casi siempre es una de dos:")
        print("     · faltan funciones en la base (mira el punto 1)")
        print("     · el modelo contesta sin llamar herramientas — pídele algo")
        print("       más explícito: 'palomea barniz del MOB 6 de silver deer'")
    for f in reversed(filas):
        h = f["created_at"][5:10] + " " + f["created_at"][11:16]
        marca = " (deshecho)" if f["deshecho"] else ""
        print(f"   {h}  {f['accion']:<18} {f['tabla']:<14}{marca}")
        if f.get("mensaje_origen"):
            print(f"          por: \"{f['mensaje_origen'][:58]}\"")
        print(f"          antes: {str(f.get('antes'))[:52]}")
        print(f"          desp.: {str(f.get('despues'))[:52]}")

    print()
    print("=" * 66)
    print("4. ESTADO ACTUAL DE UNOS MUEBLES")
    print("=" * 66)
    m = (db.db().table("v_muebles")
         .select("obra, grupo, nombre, pasos_hechos, avance, terminado")
         .order("updated_at", desc=True).limit(6).execute().data)
    for x in m:
        g = f" · {x['grupo']}" if x.get("grupo") else ""
        print(f"   {x['obra']}{g} · {x['nombre'][:28]:<28} "
              f"{x['pasos_hechos']}/6  {round(float(x['avance'])*100):>3}%"
              f"{'  terminado' if x['terminado'] else ''}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
