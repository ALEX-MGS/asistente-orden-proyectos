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


def estado() -> dict:
    cli = db.db()

    muebles = (cli.table("v_muebles").select("*")
               .eq("archivado", False).order("obra").order("orden")
               .execute().data)
    etapas = cli.table("mueble_etapas").select("mueble_id, etapa_id, hecho").execute().data
    obras = cli.table("obras").select("id, nombre, tipo, fecha_entrega, orden").execute().data
    pends = (cli.table("pendientes").select("id, texto, hecho, obra_id, created_at")
             .order("created_at").execute().data)
    cotiz = (cli.table("cotizaciones")
             .select("id, cliente, concepto, monto, fecha, estado, nota")
             .order("fecha", desc=True).execute().data)

    # --- etapas: de filas a el arreglo de 5 booleanos que espera el panel
    stages: dict[str, list[bool]] = {}
    for e in etapas:
        stages.setdefault(e["mueble_id"], [False] * 5)
        i = int(e["etapa_id"]) - 1
        if 0 <= i < 5:
            stages[e["mueble_id"]][i] = bool(e["hecho"])

    por_id = {o["id"]: o for o in obras}

    # --- proyectos: sólo las obras que tienen muebles
    proyectos: dict[str, dict] = {}
    for m in muebles:
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
            "stages": stages.get(m["id"], [False] * 5),
            "nota": m.get("nota") or "",
            "fecha": m.get("fecha_entrega") or "",
            "terminado": bool(m.get("terminado")),
        })

    # --- pendientes agrupados por obra; los de obra interna van a Oficina
    grupos: dict[str, dict] = {}
    oficina: list[dict] = []
    for t in pends:
        o = por_id.get(t["obra_id"], {})
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
