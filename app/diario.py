"""El resumen de la mañana.

Corre dentro del mismo servicio web, sin un segundo servicio en Railway:
un ciclo que despierta cada minuto y pregunta si ya toca. El candado de
`avisos` (15_resumen_diario.sql) es lo que hace eso seguro — cada
despliegue reinicia el proceso, y sin él un reinicio después de la hora
volvería a mandar el mensaje.

La ventana de alcance existe por lo mismo: si el servicio estaba caído a
las 8 y arranca a las 9, el resumen sale igual; si arranca a las 11 de la
noche, ya no, porque a esa hora no le sirve a nadie.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, db, whatsapp

log = logging.getLogger("asistente")

CLAVE = "resumen_diario"
VENTANA = timedelta(hours=3)   # cuánto después de la hora todavía vale mandarlo
LATIDO = 60                    # segundos entre revisiones

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def zona() -> ZoneInfo:
    try:
        return ZoneInfo(config.ZONA)
    except Exception:
        log.warning("ZONA '%s' no existe; uso America/Mexico_City", config.ZONA)
        return ZoneInfo("America/Mexico_City")


def hora_objetivo() -> tuple[int, int] | None:
    """(hora, minuto) de RESUMEN_HORA, o None si está apagado."""
    bruto = (config.RESUMEN_HORA or "").strip()
    if not bruto:
        return None
    try:
        h, m = bruto.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except Exception:
        pass
    log.error("RESUMEN_HORA='%s' no se entiende; usa HH:MM, por ejemplo 08:47", bruto)
    return None


def toca(ahora: datetime | None = None) -> bool:
    hm = hora_objetivo()
    if hm is None:
        return False
    ahora = ahora or datetime.now(zona())
    objetivo = ahora.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    return objetivo <= ahora < objetivo + VENTANA


def _dia(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]}"


def _pct(v) -> str:
    try:
        return f"{round(float(v) * 100)}%"
    except Exception:
        return "—"


def armar(datos: dict, nombre: str, hoy: date | None = None) -> str:
    """El mensaje, sin modelo: es siempre el mismo y no hay qué interpretar."""
    hoy = hoy or date.today()
    saludo = nombre.split()[0] if nombre else ""
    l = [f"Buenos días{', ' + saludo if saludo else ''}. {_dia(hoy)}.", ""]

    atrasados = datos.get("atrasados") or []
    if atrasados:
        l.append(f"⚠ Atrasados ({len(atrasados)})")
        for a in atrasados[:8]:
            f = a.get("fecha_entrega")
            cuando = f" — era {_dia(date.fromisoformat(f))}" if f else ""
            sigue = f", sigue {(a.get('sigue') or '').lower()}" if a.get("sigue") else ""
            l.append(f"{a.get('obra')} · {a.get('mueble')}{cuando}{sigue}")
        if len(atrasados) > 8:
            l.append(f"y {len(atrasados) - 8} más")
        l.append("")

    proceso = datos.get("en_proceso") or []
    if proceso:
        l.append(f"En proceso ({len(proceso)})")
        for p in proceso[:8]:
            sigue = f" → {(p.get('sigue') or '').lower()}" if p.get("sigue") else ""
            quieto = p.get("dias_sin_movimiento")
            parado = f" · {quieto} días sin moverse" if quieto and quieto >= 7 else ""
            l.append(f"{p.get('obra')} · {p.get('mueble')} "
                     f"{_pct(p.get('avance'))}{sigue}{parado}")
        if len(proceso) > 8:
            l.append(f"y {len(proceso) - 8} más")
        l.append("")

    pend = datos.get("pendientes_abiertos") or []
    if pend:
        l.append(f"Pendientes abiertos ({len(pend)})")
        for p in pend[:6]:
            l.append(f"{p.get('obra')} — {p.get('texto')}")
        if len(pend) > 6:
            l.append(f"y {len(pend) - 6} más")
        l.append("")

    total = datos.get("total") or 0
    if not atrasados and not proceso and not pend:
        l.append("Nada atrasado y nada en proceso. Todo al día.")
        l.append("")
    l.append(f"{total} muebles · {datos.get('terminados') or 0} terminados · "
             f"{_pct(datos.get('avance_promedio'))} de avance")
    return "\n".join(l).strip()


def enviar(forzar: bool = False) -> dict:
    """Manda el resumen. Devuelve qué pasó, para el log y para la ruta manual."""
    hoy = datetime.now(zona()).date()

    if not forzar and not db.reclamar_aviso(CLAVE, hoy):
        return {"ok": False, "motivo": "ya se mandó hoy"}

    gente = db.destinatarios_resumen()
    if not gente:
        return {"ok": False, "motivo": "nadie tiene resumen_diario prendido"}

    datos = db.resumen()
    enviados, fallidos = [], []
    for p in gente:
        texto = armar(datos, p.get("nombre") or "", hoy)
        db.guardar_mensaje(p["telefono"], "saliente", texto, p.get("id"))
        if whatsapp.enviar(p["telefono"], texto):
            enviados.append(p.get("nombre"))
        else:
            fallidos.append(p.get("nombre"))

    if fallidos:
        log.error("El resumen no llegó a: %s. Si es el sandbox de Twilio, la "
                  "sesión caduca a los 3 días y hay que volver a mandar "
                  "'join <codigo>'. Con número propio de Meta, un mensaje que "
                  "inicia el bot necesita plantilla aprobada.", ", ".join(fallidos))

    return {"ok": bool(enviados), "enviados": enviados, "fallidos": fallidos,
            "dia": hoy.isoformat()}


async def vigilar():
    """El ciclo. Arranca con el servicio y no vuelve a hacer ruido."""
    if hora_objetivo() is None:
        log.info("Resumen diario apagado (RESUMEN_HORA vacía).")
        return
    h, m = hora_objetivo()
    log.info("Resumen diario a las %02d:%02d (%s).", h, m, config.ZONA)
    while True:
        try:
            if toca():
                r = await asyncio.to_thread(enviar)
                if r.get("ok"):
                    log.info("Resumen diario enviado a %s", r.get("enviados"))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("falló la revisión del resumen diario")
        await asyncio.sleep(LATIDO)
