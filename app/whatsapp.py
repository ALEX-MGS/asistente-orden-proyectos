"""Puente con WhatsApp vía Twilio.

Twilio expone el webhook a internet, así que hay que verificar que cada
POST venga de verdad de Twilio. Sin eso, cualquiera que descubra la URL
puede mover muebles en tu tablero.
"""
import logging

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from . import config

log = logging.getLogger("asistente")

_cliente: Client | None = None


def cliente() -> Client:
    global _cliente
    if _cliente is None:
        _cliente = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    return _cliente


def normalizar(numero: str) -> str:
    """'whatsapp:+5215512345678' -> '+5215512345678'"""
    return (numero or "").replace("whatsapp:", "").strip()


def firma_valida(url: str, params: dict, firma: str) -> bool:
    """Comprueba la cabecera X-Twilio-Signature."""
    if not config.TWILIO_AUTH_TOKEN:
        return False
    return RequestValidator(config.TWILIO_AUTH_TOKEN).validate(url, params, firma or "")


def enviar(a: str, texto: str) -> bool:
    """Manda un mensaje. Devuelve si se pudo.

    Si falla, DICE por qué. La versión anterior se tragaba el error y el
    mensaje simplemente no llegaba, sin rastro en ningún lado.
    """
    if not config.TWILIO_ACCOUNT_SID:
        log.error("No se pudo enviar: falta TWILIO_ACCOUNT_SID en el .env")
        return False
    try:
        m = cliente().messages.create(
            from_=config.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{normalizar(a)}",
            body=texto[:1550],  # WhatsApp corta cerca de 1600
        )
        log.info("Enviado a %s (sid %s, estado %s)", a, m.sid, m.status)
        return True
    except Exception as e:
        codigo = getattr(e, "code", None)
        log.error("NO SE PUDO ENVIAR a %s — %s: %s", a, type(e).__name__, e)
        if codigo == 63015 or codigo == 63016:
            log.error("  >>> La sesión del sandbox expiró (dura 3 días).")
            log.error("  >>> Manda otra vez 'join <codigo>' al numero del sandbox.")
        elif codigo == 21608:
            log.error("  >>> Ese numero no esta unido al sandbox de Twilio.")
        elif codigo == 20003:
            log.error("  >>> Credenciales invalidas: revisa TWILIO_AUTH_TOKEN.")
        return False
