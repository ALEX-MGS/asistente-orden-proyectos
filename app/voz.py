"""Notas de voz: bajar el audio de Twilio y pasarlo a texto.

Dos cosas que hay que saber de esto:

1. El audio de Twilio NO es público. La URL que manda el webhook pide
   las credenciales de la cuenta; sin ellas devuelve 401 y uno se queda
   pensando que el archivo no existe.

2. La transcripción usa la API de OpenAI, aparte del proveedor que esté
   atendiendo el chat. Así puedes mover PROVEEDOR a anthropic sin perder
   las notas de voz, siempre que OPENAI_API_KEY siga puesta.
"""
import logging

import httpx

from . import config

log = logging.getLogger("asistente")

# El límite de la API son 25 MB. Nos quedamos cortos a propósito: una
# nota de voz de WhatsApp pesa unos 10 KB por segundo, así que 20 MB son
# más de media hora de audio y nadie manda eso por error.
LIMITE_BYTES = 20 * 1024 * 1024
SEGUNDOS = 90


def disponible() -> str | None:
    """Qué falta para poder transcribir, o None si todo está listo."""
    if not config.VOZ_API_KEY:
        return ("falta OPENAI_API_KEY en el .env (la transcripción la hace "
                "OpenAI, aunque el chat lo atienda otro proveedor)")
    if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
        return "faltan las credenciales de Twilio para bajar el audio"
    return None


def es_audio(tipo: str) -> bool:
    return (tipo or "").lower().startswith(("audio/", "video/"))


def bajar(url: str) -> tuple[bytes | None, str | None]:
    """Trae el archivo de Twilio. Devuelve (bytes, motivo_del_fallo)."""
    try:
        r = httpx.get(url, follow_redirects=True, timeout=SEGUNDOS,
                      auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN))
    except Exception as e:
        return None, f"no se pudo bajar el audio ({type(e).__name__})"

    if r.status_code == 401:
        return None, "Twilio rechazó las credenciales al bajar el audio"
    if r.status_code >= 400:
        return None, f"Twilio contestó {r.status_code} al bajar el audio"
    if not r.content:
        return None, "el audio llegó vacío"
    if len(r.content) > LIMITE_BYTES:
        return None, "la nota de voz es demasiado larga"
    return r.content, None


def transcribir(url: str, tipo: str = "") -> tuple[str | None, str | None]:
    """Audio de Twilio a texto. Devuelve (texto, motivo_del_fallo)."""
    falta = disponible()
    if falta:
        return None, falta

    datos, motivo = bajar(url)
    if datos is None:
        return None, motivo

    # WhatsApp manda audio/ogg; el nombre del archivo sólo sirve para que
    # la API adivine el formato, pero si no cuadra la extensión se queja.
    ext = {"audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a",
           "audio/amr": "amr", "audio/aac": "aac", "audio/wav": "wav",
           "audio/x-wav": "wav", "audio/webm": "webm",
           }.get((tipo or "").split(";")[0].strip().lower(), "ogg")

    base = (config.BASE_URL_VOZ or "https://api.openai.com/v1").rstrip("/")
    try:
        r = httpx.post(
            f"{base}/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.VOZ_API_KEY}"},
            files={"file": (f"nota.{ext}", datos, tipo or "audio/ogg")},
            data={"model": config.MODELO_VOZ, "language": "es"},
            timeout=SEGUNDOS,
        )
    except Exception as e:
        return None, f"la transcripción no respondió ({type(e).__name__})"

    if r.status_code >= 400:
        detalle = ""
        try:
            detalle = (r.json().get("error") or {}).get("message", "")
        except Exception:
            detalle = r.text[:120]
        log.error("transcripción falló %s: %s", r.status_code, detalle)
        if r.status_code == 401:
            return None, "la llave de OpenAI no sirve para transcribir"
        if "model" in detalle.lower():
            return None, (f"el modelo de voz '{config.MODELO_VOZ}' no está "
                          "disponible en tu cuenta; cámbialo con MODELO_VOZ")
        return None, f"la transcripción falló ({r.status_code})"

    try:
        texto = (r.json().get("text") or "").strip()
    except Exception:
        return None, "la transcripción vino en un formato que no entendí"

    if not texto:
        return None, "no se oyó nada en la nota"
    return texto, None
