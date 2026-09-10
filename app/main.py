"""Servidor que recibe los mensajes de WhatsApp.

Twilio manda un POST aquí cada vez que alguien le escribe al número, y
espera respuesta en unos 15 segundos. El asistente puede tardar más que
eso cuando encadena varias herramientas, así que contestamos vacío de
inmediato y mandamos la respuesta real por la API de Twilio.
"""
import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import PlainTextResponse

from . import agente, config, db, whatsapp

log = logging.getLogger("asistente")
app = FastAPI(title="Asistente de obra · Grupo Morales")

VACIO = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def twiml(texto: str = "") -> PlainTextResponse:
    if not texto:
        return PlainTextResponse(VACIO, media_type="application/xml")
    seguro = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return PlainTextResponse(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{seguro}</Message></Response>',
        media_type="application/xml",
    )


def atender(telefono: str, texto: str, persona: dict):
    """Corre el asistente y manda la respuesta. Va en segundo plano."""
    try:
        respuesta = agente.responder(texto, persona, db.historial(telefono))
    except Exception as e:
        log.exception("falló el asistente")
        respuesta = f"Se me atoró algo procesando eso ({type(e).__name__}). Inténtalo otra vez."
    db.guardar_mensaje(telefono, "saliente", respuesta, persona["id"])
    whatsapp.enviar(telefono, respuesta)


@app.get("/")
def salud():
    faltan = config.faltantes()
    return {"ok": not faltan, "faltan": faltan,
            "proveedor": config.PROVEEDOR, "modelo": config.MODELO}


@app.post("/whatsapp")
async def entrante(request: Request, fondo: BackgroundTasks):
    form = dict(await request.form())

    # 1. ¿Viene de Twilio? La URL debe ser la pública, la que Twilio firmó.
    url = config.URL_PUBLICA or str(request.url)
    if not whatsapp.firma_valida(url, form, request.headers.get("X-Twilio-Signature", "")):
        log.warning(
            "FIRMA INVÁLIDA\n"
            "  URL_PUBLICA del .env : %s\n"
            "  URL que vio el server: %s\n"
            "  Ambas deben ser IGUALES a la que pusiste en Twilio.\n"
            "  Si acabas de editar el .env, reinicia uvicorn: --reload no recarga el .env.",
            config.URL_PUBLICA or "(vacía)", request.url)
        return PlainTextResponse("firma inválida", status_code=403)

    telefono = whatsapp.normalizar(form.get("From", ""))
    texto = (form.get("Body") or "").strip()
    sid = form.get("MessageSid", "")

    # 2. Twilio reintenta si tardamos. Sin este candado un mismo mensaje
    #    se procesaría dos veces y el mueble avanzaría dos etapas.
    if db.ya_procesado(sid):
        return twiml()

    persona = db.persona_por_telefono(telefono)
    db.guardar_mensaje(telefono, "entrante", texto, (persona or {}).get("id"), sid)

    if not persona:
        return twiml("Este número no está autorizado. Pídele a Alex que lo dé de alta.")
    if not texto:
        return twiml("Por ahora sólo entiendo texto. Las notas de voz vienen después.")

    # 3. Contestamos vacío ya, y el trabajo real sigue en segundo plano.
    fondo.add_task(atender, telefono, texto, persona)
    return twiml()
