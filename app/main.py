"""Servidor que recibe los mensajes de WhatsApp.

Twilio manda un POST aquí cada vez que alguien le escribe al número, y
espera respuesta en unos 15 segundos. El asistente puede tardar más que
eso cuando encadena varias herramientas, así que contestamos vacío de
inmediato y mandamos la respuesta real por la API de Twilio.
"""
import logging
from datetime import datetime

from pathlib import Path

from fastapi import BackgroundTasks, Body, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from . import agente, api, config, db, tablero, whatsapp

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
    if not whatsapp.enviar(telefono, respuesta):
        log.error("La respuesta se guardó en la base pero NO llegó a WhatsApp. "
                  "El renglón de arriba dice por qué.")


@app.get("/")
def salud():
    faltan = config.faltantes()
    return {"ok": not faltan, "faltan": faltan,
            "proveedor": config.PROVEEDOR, "modelo": config.MODELO}


PANEL = Path(__file__).resolve().parent.parent / "estatico" / "panel.html"


def con_token(k: str) -> bool:
    return not config.TABLERO_TOKEN or k == config.TABLERO_TOKEN


@app.get("/panel")
def panel(k: str = ""):
    """El panel de siempre, pero leyendo de la base."""
    if not con_token(k):
        return PlainTextResponse("No autorizado", status_code=403)
    return FileResponse(PANEL, media_type="text/html")


@app.get("/api/estado")
def api_estado(k: str = ""):
    """El estado completo, en la forma que el panel ya espera."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(api.estado())
    except Exception as e:
        log.exception("falló /api/estado")
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)


def marca_panel(accion: str) -> str:
    """Una marca distinta por clic.

    deshacer() agrupa por mensaje_origen: eso es correcto en WhatsApp,
    donde un mensaje puede cambiar varias cosas. En el panel cada clic es
    una acción suelta, así que cada uno lleva su propia marca y se
    deshace solo.
    """
    return f"panel · {accion} · {datetime.now().isoformat(timespec='milliseconds')}"


def quien_edita() -> str | None:
    """A quién se le atribuyen los cambios hechos desde el panel.

    El panel todavía no tiene login: quien trae el token puede editar. Se
    atribuye al admin para que la bitácora y 'deshacer' funcionen igual
    que por WhatsApp. Cuando haya login, esto sale de la sesión.
    """
    r = (db.db().table("personas").select("id")
         .eq("rol", "admin").limit(1).execute().data)
    return r[0]["id"] if r else None


@app.post("/api/etapa")
def api_etapa(k: str = "", cuerpo: dict = Body(...)):
    """Palomear o despalomear una etapa desde el panel."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(db.actualizar_etapa(
            cuerpo["mueble_id"], cuerpo["etapa"], bool(cuerpo.get("hecho", True)),
            quien_edita(), marca_panel("etapa")))
    except Exception as e:
        log.exception("falló /api/etapa")
        return JSONResponse({"error": str(e)[:200]}, status_code=400)


@app.post("/api/terminado")
def api_terminado(k: str = "", cuerpo: dict = Body(...)):
    """Marcar o desmarcar la palomita de Terminado desde el panel."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(db.marcar_terminado(
            cuerpo["mueble_id"], bool(cuerpo.get("terminado", True)),
            quien_edita(), marca_panel("terminado")))
    except Exception as e:
        log.exception("falló /api/terminado")
        return JSONResponse({"error": str(e)[:200]}, status_code=400)


@app.post("/api/deshacer")
def api_deshacer(k: str = ""):
    """Deshacer el último cambio, igual que por WhatsApp."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(db.deshacer(quien_edita()))
    except Exception as e:
        log.exception("falló /api/deshacer")
        return JSONResponse({"error": str(e)[:200]}, status_code=400)


@app.get("/tablero", response_class=HTMLResponse)
def ver_tablero(k: str = ""):
    """Tablero de solo lectura. Se edita por WhatsApp, aquí sólo se mira."""
    if config.TABLERO_TOKEN and k != config.TABLERO_TOKEN:
        return HTMLResponse("No autorizado", status_code=403)
    try:
        return HTMLResponse(tablero.render(tablero.datos()))
    except Exception as e:
        log.exception("falló el tablero")
        return HTMLResponse(f"No se pudo armar el tablero: {type(e).__name__}",
                            status_code=500)


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
