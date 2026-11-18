"""API JSON para el panel.

Devuelve el estado en la MISMA forma que el panel ya usa
({proyectos, pends, cotizaciones, oficina}), para que el panel no tenga
que cambiar su manera de pensar los datos: sólo cambia de dónde los saca.
"""
from . import db

# Los colores de los pendientes viven en el panel, no en la base. En vez
# de agregar una columna, se derivan del nombre de la obra: así el mismo
# cliente siempre sale del mismo color, sin guardar nada.
COLORES = ["coral", "blue", "pink", "purple", "amber", "green", "teal", "gray"]


def color_de(nombre: str) -> str:
    return COLORES[sum(ord(c) for c in (nombre or "")) % len(COLORES)]


def version() -> str:
    """Huella del estado, para saber si cambió algo sin traérselo todo.

    Cada escritura del asistente y del panel deja una fila en bitacora,
    así que su último id basta. Se suma la fecha del mueble tocado más
    recientemente, para no perderse un cambio hecho a mano en Supabase.
    """
    cli = db.db()
    b = (cli.table("bitacora").select("id")
         .order("id", desc=True).limit(1).execute().data)
    m = (cli.table("muebles").select("updated_at")
         .order("updated_at", desc=True).limit(1).execute().data)
    return f"{b[0]['id'] if b else 0}|{m[0]['updated_at'] if m else ''}"


def palomitas(m: dict) -> list[bool]:
    """Las cinco etapas del mueble, en el orden del tablero.

    Vienen dentro de v_muebles. Antes se traían en su propia consulta,
    cinco filas por mueble, y Supabase corta en 1000 filas sin avisar:
    a los 200 muebles el tablero habría empezado a mentir en silencio.
    """
    v = m.get("etapas") or []
    return [bool(v[i]) if i < len(v) else False for i in range(5)]


def estado() -> dict:
    cli = db.db()

    muebles = (cli.table("v_muebles").select("*")
               .eq("archivado", False).order("obra").order("orden")
               .execute().data)
    obras = (cli.table("obras")
             .select("id, nombre, tipo, fecha_entrega, orden, es_proyecto")
             .eq("archivado", False).execute().data)
    pends = (cli.table("pendientes").select("id, texto, hecho, obra_id, created_at")
             .eq("archivado", False).order("created_at").execute().data)
    cotiz = (cli.table("cotizaciones")
             .select("id, cliente, concepto, monto, fecha, estado, nota")
             .eq("archivado", False).order("fecha", desc=True).execute().data)

    por_id = {o["id"]: o for o in obras}

    # --- proyectos: sólo las obras que tienen muebles
    proyectos: dict[str, dict] = {}
    for m in muebles:
        if m["obra_id"] not in por_id:      # obra archivada
            continue
        p = proyectos.get(m["obra_id"])
        if p is None:
            o = por_id.get(m["obra_id"], {})
            p = proyectos[m["obra_id"]] = {
                "id": m["obra_id"],
                "nombre": m["obra"],
                "fechaEntrega": o.get("fecha_entrega") or "",
                "items": [],
            }
        p["items"].append({
            "id": m["id"],
            "nombre": m["nombre"],
            "grupo": m.get("grupo") or "",
            "stages": palomitas(m),
            "nota": m.get("nota") or "",
            "fecha": m.get("fecha_entrega") or "",
            "terminado": bool(m.get("terminado")),
        })

    # Un proyecto recién creado todavía no tiene muebles. Sin esto
    # desaparecería al recargar, porque la lista de arriba sale de los
    # muebles. Las obras que sólo llevan pendientes no entran: ésas
    # viven en la pestaña de Pendientes, como siempre.
    for o in obras:
        if o.get("es_proyecto") and o["id"] not in proyectos:
            proyectos[o["id"]] = {
                "id": o["id"],
                "nombre": o.get("nombre") or "—",
                "fechaEntrega": o.get("fecha_entrega") or "",
                "items": [],
            }

    # --- pendientes agrupados por obra; los de obra interna van a Oficina
    grupos: dict[str, dict] = {}
    oficina: list[dict] = []
    for t in pends:
        o = por_id.get(t["obra_id"])
        if o is None:                      # obra archivada
            continue
        if o.get("tipo") == "interna":
            oficina.append({"id": t["id"], "text": t["texto"], "done": bool(t["hecho"])})
            continue
        nombre = o.get("nombre", "—")
        g = grupos.get(t["obra_id"])
        if g is None:
            g = grupos[t["obra_id"]] = {"id": t["obra_id"], "obra": nombre,
                                        "color": color_de(nombre), "tasks": []}
        g["tasks"].append({"id": t["id"], "text": t["texto"], "done": bool(t["hecho"])})

    return {
        "v": version(),
        "proyectos": list(proyectos.values()),
        "pends": list(grupos.values()),
        "cotizaciones": [{
            "id": c["id"], "cliente": c["cliente"], "concepto": c.get("concepto") or "",
            "monto": float(c["monto"]) if c.get("monto") is not None else "",
            "fecha": c.get("fecha") or "", "estado": c.get("estado") or "enviada",
            "nota": c.get("nota") or "",
        } for c in cotiz],
        "oficina": oficina,
    }


# ---------------------------------------------------------------------
# Archivados y bitácora
#
# Dos pantallas del panel que sólo leen. Lo archivado se regresa con las
# mismas acciones de siempre (archivar_*(…, false)), así que aquí no hay
# escrituras: sólo se junta lo que hay y se dice quién lo hizo y cuándo.
# ---------------------------------------------------------------------

def _nombres_personas(cli) -> dict:
    return {p["id"]: p["nombre"] for p in
            (cli.table("personas").select("id, nombre").execute().data or [])}


def archivados() -> dict:
    """Todo lo que se sacó del tablero y se puede regresar.

    Un mueble o un pendiente de una obra archivada no sale suelto: regresa
    con su obra. Por eso aquí aparece la obra con cuántos muebles trae, y
    no cada mueble por separado.
    """
    cli = db.db()
    personas = _nombres_personas(cli)

    obras = cli.table("obras").select("id, nombre, tipo, archivado").execute().data or []
    por_obra = {o["id"]: o for o in obras}
    obras_fuera = {o["id"] for o in obras if o.get("archivado")}

    muebles = (cli.table("v_muebles")
               .select("id, nombre, grupo, obra, obra_id, avance, terminado")
               .eq("archivado", True).execute().data or [])
    pends = (cli.table("pendientes").select("id, texto, hecho, obra_id")
             .eq("archivado", True).execute().data or [])
    cotiz = (cli.table("cotizaciones").select("id, cliente, concepto, monto, estado")
             .eq("archivado", True).execute().data or [])

    # Quién lo sacó y cuándo: la entrada más reciente que lo archivó.
    rastro = (cli.table("bitacora")
              .select("created_at, persona_id, accion, registro_id, antes, despues")
              .in_("accion", ["archivar_mueble", "archivar_grupo", "archivar_obra",
                              "archivar_pendiente", "archivar_cotizacion"])
              .eq("deshecho", False)
              .order("id", desc=True).limit(1000).execute().data or [])
    cuando: dict[str, dict] = {}
    for b in rastro:
        sello = {"cuando": b["created_at"], "quien": personas.get(b.get("persona_id"), "")}
        if b["accion"] == "archivar_grupo":
            ids = (b.get("antes") or {}).get("muebles") or []
        elif (b.get("despues") or {}).get("archivado"):
            ids = [b["registro_id"]]
        else:
            continue
        for i in ids:
            cuando.setdefault(i, sello)          # la primera es la más reciente

    def con_sello(d: dict, i: str) -> dict:
        s = cuando.get(i) or {}
        return {**d, "cuando": s.get("cuando") or "", "quien": s.get("quien") or ""}

    salida_obras = []
    for o in obras:
        if not o.get("archivado"):
            continue
        n = sum(1 for m in muebles if m["obra_id"] == o["id"])
        salida_obras.append(con_sello({
            "id": o["id"], "nombre": o["nombre"], "muebles": n,
            "oficina": o.get("tipo") == "interna"}, o["id"]))

    salida_muebles = [con_sello({
        "id": m["id"], "nombre": m["nombre"], "grupo": m.get("grupo") or "",
        "obra": m.get("obra") or "", "avance": float(m.get("avance") or 0),
        "terminado": bool(m.get("terminado"))}, m["id"])
        for m in muebles if m["obra_id"] not in obras_fuera]

    salida_pends = []
    for t in pends:
        if t["obra_id"] in obras_fuera:
            continue
        o = por_obra.get(t["obra_id"]) or {}
        salida_pends.append(con_sello({
            "id": t["id"], "texto": t["texto"], "hecho": bool(t.get("hecho")),
            "obra": o.get("nombre") or "", "oficina": o.get("tipo") == "interna"}, t["id"]))

    salida_cotiz = [con_sello({
        "id": c["id"], "cliente": c["cliente"], "concepto": c.get("concepto") or "",
        "monto": float(c["monto"]) if c.get("monto") is not None else "",
        "estado": c.get("estado") or ""}, c["id"]) for c in cotiz]

    def recientes(lista):
        return sorted(lista, key=lambda x: x["cuando"], reverse=True)

    return {
        "obras": recientes(salida_obras),
        "muebles": recientes(salida_muebles),
        "pendientes": recientes(salida_pends),
        "cotizaciones": recientes(salida_cotiz),
    }


ETAPA_NOMBRE = {1: "Aprobado", 2: "Carpintería", 3: "Barniz", 4: "Entrega", 5: "Instalación"}


def _etapas(cli) -> dict:
    try:
        return {e["id"]: e["nombre"] for e in
                (cli.table("etapas").select("id, nombre").execute().data or [])}
    except Exception:
        return dict(ETAPA_NOMBRE)


MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


def _fecha(f) -> str:
    """'2026-11-28' → '28 nov 2026'. Si no se entiende, tal cual."""
    try:
        a, m, d = str(f)[:10].split("-")
        return f"{int(d)} {MESES[int(m) - 1]} {a}"
    except Exception:
        return str(f)


def _monto(n) -> str:
    try:
        v = float(n)
    except Exception:
        return str(n)
    return f"${v:,.0f}" if v == int(v) else f"${v:,.2f}"


def _sacado(d: dict) -> bool:
    return bool((d or {}).get("archivado"))


def que_hizo(b: dict, etapas: dict) -> str:
    """La entrada de bitácora dicha en una línea, como la diría alguien."""
    a, antes, despues = b["accion"], b.get("antes") or {}, b.get("despues") or {}

    if a == "actualizar_etapa":
        etapa = etapas.get(despues.get("etapa_id")) or "etapa"
        return f"{etapa} ✓" if despues.get("hecho") else f"quitó {etapa}"
    if a == "marcar_terminado":
        return "terminado ✓" if despues.get("terminado") else "quitó terminado"
    if a == "reiniciar_mueble":
        return "regresó el avance a cero"
    if a == "poner_nota":
        n = (despues.get("nota") or "").strip()
        return f"nota: {n}" if n else "borró la nota"
    if a == "fijar_fecha":
        f = despues.get("fecha_entrega")
        return f"entrega: {_fecha(f)}" if f else "quitó la fecha de entrega"
    if a == "crear_mueble":
        return "dio de alta el mueble"
    if a == "crear_obra":
        return "dio de alta la obra"
    if a == "agregar_pendiente":
        return "agregó el pendiente"
    if a == "cerrar_pendiente":
        return "pendiente hecho ✓" if despues.get("hecho") else "reabrió el pendiente"
    if a == "renombrar_mueble":
        return f"renombró: {antes.get('nombre') or '—'} → {despues.get('nombre') or '—'}"
    if a == "renombrar_grupo":
        return f"grupo: {antes.get('grupo') or 'sin grupo'} → {despues.get('grupo') or '—'}"
    if a == "editar_obra":
        if "nombre" in despues:
            return f"renombró la obra: {antes.get('nombre') or '—'} → {despues.get('nombre')}"
        if "fecha_entrega" in despues:
            f = despues.get("fecha_entrega")
            return f"entrega de la obra: {_fecha(f)}" if f else "quitó la fecha de la obra"
        return "editó la nota de la obra"
    if a == "crear_cotizacion":
        return "cotización nueva"
    if a == "editar_cotizacion":
        if "estado" in despues:
            return f"cotización: {despues['estado']}"
        if "monto" in despues:
            return f"monto: {_monto(despues['monto'])}"
        return "editó la cotización"
    if a == "archivar_grupo":
        n = len(antes.get("muebles") or [])
        return f"sacó del tablero el grupo {antes.get('grupo') or 'sin grupo'} ({n} muebles)"
    if a.startswith("archivar_"):
        return "sacó del tablero" if _sacado(despues) else "regresó al tablero"
    if a == "acomodar_muebles":
        return "reordenó los muebles"
    return a.replace("_", " ")


def bitacora(limite: int = 100, antes_de: int | None = None) -> dict:
    """Los cambios más recientes, de los nuevos a los viejos.

    Cada entrada dice quién, qué, sobre qué y desde dónde. 'antes_de'
    pide la página siguiente: las entradas con id menor que ése.
    """
    cli = db.db()
    limite = max(1, min(int(limite or 100), 200))
    q = (cli.table("bitacora")
         .select("id, created_at, persona_id, accion, tabla, registro_id, "
                 "antes, despues, mensaje_origen, deshecho")
         .order("id", desc=True).limit(limite))
    if antes_de:
        q = q.lt("id", int(antes_de))
    filas = q.execute().data or []

    personas = _nombres_personas(cli)
    etapas = _etapas(cli)

    # Los nombres de lo que se tocó, de una vez por tabla. Los ids de
    # obra también llegan en acciones de muebles que tocan toda la obra.
    de_obra = {"renombrar_grupo", "archivar_grupo", "acomodar_muebles"}
    ids_m, ids_o, ids_p, ids_c = set(), set(), set(), set()
    for b in filas:
        r, t = b.get("registro_id"), b.get("tabla")
        if not r:
            continue
        if t == "obras" or b["accion"] in de_obra:
            ids_o.add(r)
        elif t in ("muebles", "mueble_etapas"):
            ids_m.add(r)
        elif t == "pendientes":
            ids_p.add(r)
        elif t == "cotizaciones":
            ids_c.add(r)

    def traer(tabla, campos, ids):
        if not ids:
            return {}
        return {x["id"]: x for x in
                (cli.table(tabla).select(campos).in_("id", list(ids)).execute().data or [])}

    muebles = traer("v_muebles", "id, nombre, obra", ids_m)
    pends = traer("pendientes", "id, texto, obra_id", ids_p)
    ids_o |= {p["obra_id"] for p in pends.values() if p.get("obra_id")}
    obras = traer("obras", "id, nombre", ids_o)
    cotiz = traer("cotizaciones", "id, cliente", ids_c)

    def sobre(b) -> str:
        r, t, d = b.get("registro_id"), b.get("tabla"), b.get("despues") or {}
        if t == "obras" or b["accion"] in de_obra:
            return (obras.get(r) or {}).get("nombre") or d.get("nombre") or ""
        if t in ("muebles", "mueble_etapas"):
            m = muebles.get(r)
            if m:
                return f"{m['nombre']} · {m['obra']}"
            return d.get("nombre") or "(mueble que ya no existe)"
        if t == "pendientes":
            p = pends.get(r)
            if p:
                o = (obras.get(p.get("obra_id")) or {}).get("nombre")
                return f"{p['texto']}" + (f" · {o}" if o else "")
            return d.get("texto") or "(pendiente que ya no existe)"
        if t == "cotizaciones":
            return (cotiz.get(r) or {}).get("cliente") or d.get("cliente") or ""
        return ""

    def origen(b) -> dict:
        m = (b.get("mensaje_origen") or "").strip()
        if not m:
            return {"tipo": "sistema", "texto": ""}
        if m.startswith("panel · "):
            return {"tipo": "panel", "texto": ""}
        return {"tipo": "mensaje", "texto": m[:240]}

    return {
        "entradas": [{
            "id": b["id"],
            "cuando": b["created_at"],
            "quien": personas.get(b.get("persona_id"), "") if b.get("persona_id") else "",
            "que": que_hizo(b, etapas),
            "sobre": sobre(b),
            "origen": origen(b),
            "deshecho": bool(b.get("deshecho")),
        } for b in filas],
        "hay_mas": len(filas) == limite,
    }
