"""Puente con WhatsApp vía Twilio.

Twilio expone el webhook a internet, así que hay que verificar que cada
POST venga de verdad de Twilio. Sin eso, cualquiera que descubra la URL
puede mover muebles en tu tablero.
"""
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from . import config

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
    """Manda un mensaje. Devuelve si se pudo."""
    if not config.TWILIO_ACCOUNT_SID:
        return False
    try:
        cliente().messages.create(
            from_=config.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{normalizar(a)}",
            body=texto[:1550],  # WhatsApp corta cerca de 1600
        )
        return True
    except Exception:
        return False
