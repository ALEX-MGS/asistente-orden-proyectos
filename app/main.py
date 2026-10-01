"""Servidor que recibe los mensajes de WhatsApp.

Twilio manda un POST aquí cada vez que alguien le escribe al número, y
espera respuesta en unos 15 segundos. El asistente puede tardar más que
eso cuando encadena varias herramientas, así que contestamos vacío de
inmediato y mandamos la respuesta real por la API de Twilio.
"""
import logging
from datetime import datetime

from pathlib import Path

from fastapi import BackgroundTasks, Body, FastAPI, Request, Response
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


@app.get("/favicon.ico")
def favicon():
    """Sin esto cada visita al panel deja un 404 en la bitácora de Railway."""
    return Response(status_code=204)


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


def motivo(e: Exception) -> str:
    """El texto que el panel le enseña a la persona.

    Cuando una función SQL hace `raise exception 'Ya hay otro mueble con
    ese nombre'`, ese texto viene envuelto en el error de PostgREST. Sin
    esto el panel mostraría el JSON completo y nadie entendería nada.
    """
    for atributo in ("message", "details"):
        v = getattr(e, atributo, None)
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    return f"{type(e).__name__}: {e}"[:200]


def con_version(resultado):
    """Le pega la huella nueva a la respuesta de una escritura.

    Así el navegador que hizo el cambio sabe que ya está al día y no se
    recarga completo ocho segundos después por su propio clic.
    """
    try:
        v = api.version()
    except Exception:
        return resultado
    if isinstance(resultado, dict):
        return {**resultado, "v": v}
    return {"r": resultado, "v": v}


# ---------------------------------------------------------------------
# Todo lo que el panel edita entra por /api/accion.
#
# Es una sola puerta con lista blanca: si la acción no está aquí, no
# existe. Agregar un botón nuevo es agregar un renglón, no una ruta — y
# ninguna petición puede llamar a algo que no esté en esta tabla.
#
# Cada renglón es: nombre → (función de db.py, las claves del cuerpo en
# el orden en que la función las espera). Después de esas van siempre
# quién edita y la marca del clic.
# ---------------------------------------------------------------------
ACCIONES: dict[str, tuple] = {
    "nota":              (db.poner_nota,        ("mueble_id", "nota")),
    "fecha":             (db.fijar_fecha,       ("mueble_id", "fecha")),
    "renombrar_mueble":  (db.renombrar_mueble,  ("mueble_id", "nombre")),
    "renombrar_grupo":   (db.renombrar_grupo,   ("obra_id", "grupo", "nuevo")),
    "editar_obra":       (db.editar_obra,       ("obra_id", "cambios")),
    "pendiente":         (db.cerrar_pendiente,  ("pendiente_id", "hecho")),
    "editar_cotizacion": (db.editar_cotizacion, ("cotizacion_id", "cambios")),

    # altas (11_crear.sql)
    "crear_obra":        (db.crear_obra,        ("nombre", "fecha", "proyecto")),
    "crear_mueble":      (db.agregar_mueble,    ("obra_id", "nombre", "grupo")),
    "crear_pendiente":   (db.agregar_pendiente_en, ("obra_id", "texto")),
    # da de alta la obra y su primer pendiente en una sola acción
    "crear_obra_pendiente": (db.agregar_pendiente, ("obra", "texto")),
    "crear_oficina":     (db.pendiente_de_oficina, ("texto",)),
    "crear_cotizacion":  (db.crear_cotizacion,  ("cliente", "concepto", "monto", "fecha")),
}


@app.post("/api/accion")
def api_accion(k: str = "", cuerpo: dict = Body(...)):
    """Una edición del panel."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)

    nombre = (cuerpo or {}).get("accion") or ""
    entrada = ACCIONES.get(nombre)
    if entrada is None:
        return JSONResponse({"error": f"acción desconocida: {nombre}"},
                            status_code=400)

    funcion, claves = entrada
    faltan = [c for c in claves if c not in cuerpo]
    if faltan:
        return JSONResponse({"error": "falta " + ", ".join(faltan)},
                            status_code=400)

    try:
        resultado = funcion(*(cuerpo[c] for c in claves),
                            quien_edita(), marca_panel(nombre))
    except Exception as e:
        log.exception("falló /api/accion %s", nombre)
        return JSONResponse({"error": motivo(e)}, status_code=400)

    return JSONResponse({"ok": True, **con_version({"r": resultado})})


@app.get("/api/version")
def api_version(k: str = ""):
    """Sólo la huella. El panel la consulta seguido; pesa unos bytes."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse({"v": api.version()})
    except Exception as e:
        log.exception("falló /api/version")
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/api/etapa")
def api_etapa(k: str = "", cuerpo: dict = Body(...)):
    """Palomear o despalomear una etapa desde el panel."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(con_version(db.actualizar_etapa(
            cuerpo["mueble_id"], cuerpo["etapa"], bool(cuerpo.get("hecho", True)),
            quien_edita(), marca_panel("etapa"))))
    except Exception as e:
        log.exception("falló /api/etapa")
        return JSONResponse({"error": motivo(e)}, status_code=400)


@app.post("/api/terminado")
def api_terminado(k: str = "", cuerpo: dict = Body(...)):
    """Marcar o desmarcar la palomita de Terminado desde el panel."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(con_version(db.marcar_terminado(
            cuerpo["mueble_id"], bool(cuerpo.get("terminado", True)),
            quien_edita(), marca_panel("terminado"))))
    except Exception as e:
        log.exception("falló /api/terminado")
        return JSONResponse({"error": motivo(e)}, status_code=400)


@app.post("/api/deshacer")
def api_deshacer(k: str = ""):
    """Deshacer el último cambio, igual que por WhatsApp."""
    if not con_token(k):
        return JSONResponse({"error": "no autorizado"}, status_code=403)
    try:
        return JSONResponse(db.deshacer(quien_edita()))
    except Exception as e:
        log.exception("falló /api/deshacer")
        return JSONResponse({"error": motivo(e)}, status_code=400)


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
