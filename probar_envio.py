"""¿Puede el bot mandarte un WhatsApp?

    python probar_envio.py

Aísla el único tramo que no se puede ver desde la base: el envío de
vuelta por Twilio. Si esto llega a tu celular, el problema está en otro
lado; si no, aquí sale el error exacto con su código.
"""
import sys

from app import config, db, whatsapp


def main() -> int:
    if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
        print("Faltan TWILIO_ACCOUNT_SID o TWILIO_AUTH_TOKEN en el .env")
        return 1

    admin = (db.db().table("personas").select("nombre, telefono")
             .eq("rol", "admin").limit(1).execute().data or [None])[0]
    if not admin:
        print("No hay nadie con rol admin en la tabla personas.")
        return 1

    destino = admin["telefono"]
    print(f"Desde: {config.TWILIO_WHATSAPP_FROM}")
    print(f"Hacia: {destino}  ({admin['nombre']})")
    print()

    try:
        m = whatsapp.cliente().messages.create(
            from_=config.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{whatsapp.normalizar(destino)}",
            body="Prueba de envío del asistente de obra.",
        )
        print(f"Twilio lo aceptó.  sid={m.sid}  estado={m.status}")
        if m.error_code:
            print(f"Pero trae error {m.error_code}: {m.error_message}")
        print()
        print("Si NO te llegó al celular aunque diga 'accepted' o 'queued',")
        print("casi siempre es que la sesión del sandbox expiró: dura 3 días.")
        print("Manda otra vez 'join <tu codigo>' al número del sandbox y repite.")
        return 0
    except Exception as e:
        codigo = getattr(e, "code", None)
        print(f"FALLÓ — {type(e).__name__}: {e}")
        print()
        if codigo in (63015, 63016, 21608):
            print(">>> Tu número no está unido al sandbox, o la sesión expiró.")
            print(">>> En Twilio: Messaging → Try it out → Send a WhatsApp message.")
            print(">>> Ahí sale el código; mándalo por WhatsApp como 'join <codigo>'.")
        elif codigo == 20003:
            print(">>> Credenciales inválidas. Revisa TWILIO_AUTH_TOKEN en el .env.")
        elif codigo == 21211:
            print(f">>> Twilio no reconoce el número {destino}.")
            print(">>> Debe ir en formato E.164, con + y código de país.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
