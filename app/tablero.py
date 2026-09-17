"""Tablero web de solo lectura.

Se arma en el servidor a partir de v_muebles y se manda como una sola
página sin dependencias externas. Esa misma página es la que la Fase 3
va a renderizar a PNG para mandarla por WhatsApp, así que todo lo que
mejore aquí mejora también la imagen.
"""
from datetime import datetime, timezone

from . import config, db

ETAPAS = ["Aprobado", "Carpintería", "Barniz", "Entrega", "Instalación"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
INICIALES = ["A", "C", "B", "E", "I"]


# ---------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------
def datos() -> dict:
    cli = db.db()
    muebles = (cli.table("v_muebles").select("*")
               .eq("archivado", False).order("obra").order("orden")
               .execute().data)
    etapas = cli.table("mueble_etapas").select("mueble_id, etapa_id, hecho").execute().data
    pendientes = (cli.table("pendientes").select("texto, obras(nombre)")
                  .eq("hecho", False).order("created_at").execute().data)
    cotiz = (cli.table("cotizaciones").select("cliente, concepto, monto, estado, fecha")
             .neq("estado", "rechazada").order("fecha", desc=True).execute().data)

    por_mueble: dict[str, list[bool]] = {}
    for e in etapas:
        por_mueble.setdefault(e["mueble_id"], [False] * 5)
        idx = int(e["etapa_id"]) - 1
        if 0 <= idx < 5:
            por_mueble[e["mueble_id"]][idx] = bool(e["hecho"])

    return {"muebles": muebles, "etapas": por_mueble,
            "pendientes": pendientes, "cotizaciones": cotiz}


# ---------------------------------------------------------------------
# Render — función pura: mismos datos, misma página
# ---------------------------------------------------------------------
def fecha_corta(f) -> str:
    """'2026-08-06' -> '6 ago'."""
    try:
        a, m, d = str(f).split("-")
        return f"{int(d)} {MESES[int(m) - 1]}"
    except Exception:
        return str(f or "")


def esc(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def chips(hechas: list[bool]) -> str:
    out = []
    for i, ok in enumerate(hechas):
        out.append(f'<span class="chip{" on" if ok else ""}" '
                   f'title="{ETAPAS[i]}">{INICIALES[i]}</span>')
    return f'<span class="chips">{"".join(out)}</span>'


def fila(m: dict, hechas: list[bool]) -> str:
    pct = round(float(m["avance"]) * 100)
    clases = "fila" + (" atrasado" if m["atrasado"] else "")
    if m["terminado"]:
        estado = '<span class="est ok">terminado</span>'
    elif m["atrasado"]:
        estado = f'<span class="est mal">vencía {esc(fecha_corta(m["fecha_entrega"]))}</span>'
    elif m["sigue"]:
        estado = f'<span class="est">sigue {esc(m["sigue"]).lower()}</span>'
    else:
        estado = '<span class="est">sin empezar</span>'

    nota = f'<div class="nota">{esc(m["nota"])}</div>' if m.get("nota") else ""
    quieto = ""
    if not m["terminado"] and (m.get("dias_sin_movimiento") or 0) >= 14:
        quieto = f'<span class="quieto">{m["dias_sin_movimiento"]} d sin moverse</span>'

    return f"""<tr class="{clases}">
      <td class="nom"><span>{esc(m["nombre"])}</span>{nota}</td>
      <td class="c">{chips(hechas)}</td>
      <td class="pct"><div class="barra"><i style="width:{pct}%"></i></div><b>{pct}%</b></td>
      <td class="st">{estado}{quieto}</td>
    </tr>"""


def render(d: dict) -> str:
    muebles, etapas = d["muebles"], d["etapas"]
    total = len(muebles)
    terminados = sum(1 for m in muebles if m["terminado"])
    atrasados = [m for m in muebles if m["atrasado"]]
    sin_empezar = sum(1 for m in muebles if float(m["avance"]) == 0)
    avance = round(sum(float(m["avance"]) for m in muebles) / total * 100) if total else 0

    # --- bloque de atrasados, hasta arriba porque es lo que urge ----
    bloque_atrasados = ""
    if atrasados:
        filas = "".join(
            f'<li><b>{esc(m["obra"])}</b> · {esc(m["nombre"])} — '
            f'vencía {esc(fecha_corta(m["fecha_entrega"]))}, va en {round(float(m["avance"])*100)}%</li>'
            for m in sorted(atrasados, key=lambda x: x["fecha_entrega"] or ""))
        bloque_atrasados = f"""<section class="alerta">
          <h2>Atrasados<span class="cuenta">{len(atrasados)}</span></h2>
          <ul>{filas}</ul></section>"""

    # --- obras --------------------------------------------------------
    obras: dict[str, list] = {}
    for m in muebles:
        obras.setdefault(m["obra"], []).append(m)

    secciones = []
    for obra, items in obras.items():
        t = sum(1 for m in items if m["terminado"])
        av = round(sum(float(m["avance"]) for m in items) / len(items) * 100)
        grupos: dict[str, list] = {}
        for m in items:
            grupos.setdefault(m.get("grupo") or "", []).append(m)

        # Sin grupo primero: si van después de un encabezado, parecen suyos.
        cuerpo = []
        for g, gm in sorted(grupos.items(), key=lambda kv: (kv[0] != "", kv[0])):
            if g:
                cuerpo.append(f'<tr class="grupo"><td colspan="4">{esc(g)}</td></tr>')
            cuerpo += [fila(m, etapas.get(m["id"], [False] * 5)) for m in gm]

        secciones.append(f"""<section class="obra">
          <header>
            <h2>{esc(obra)}</h2>
            <div class="meta">{t} de {len(items)} terminados · {av}% de avance</div>
          </header>
          <div class="tabla"><table>{"".join(cuerpo)}</table></div>
        </section>""")

    # --- pendientes ---------------------------------------------------
    bloque_pend = ""
    if d["pendientes"]:
        por_obra: dict[str, list] = {}
        for p in d["pendientes"]:
            por_obra.setdefault((p.get("obras") or {}).get("nombre", "—"), []).append(p["texto"])
        tarjetas = "".join(
            f'<div class="tarjeta"><h3>{esc(o)}</h3><ul>'
            + "".join(f"<li>{esc(t)}</li>" for t in ts) + "</ul></div>"
            for o, ts in por_obra.items())
        bloque_pend = f"""<section class="pendientes">
          <h2>Pendientes<span class="cuenta">{len(d["pendientes"])}</span></h2>
          <div class="rejilla">{tarjetas}</div></section>"""

    # --- cotizaciones -------------------------------------------------
    bloque_cot = ""
    if d["cotizaciones"]:
        filas = "".join(
            f'<tr><td>{esc(c["cliente"])}</td><td>{esc(c.get("concepto"))}</td>'
            f'<td class="n">{("$" + format(float(c["monto"]), ",.0f")) if c.get("monto") else "—"}</td>'
            f'<td><span class="est">{esc(c["estado"])}</span></td></tr>'
            for c in d["cotizaciones"])
        bloque_cot = f"""<section class="obra">
          <header><h2>Cotizaciones</h2></header>
          <div class="tabla"><table>{filas}</table></div></section>"""

    hora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    return f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tablero · Grupo Morales</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{{
  --bg:#F0F1EC; --sup:#FFFFFF; --sup2:#E7E9E1; --ink:#1B2018; --mut:#5C6357;
  --linea:#D5D8CD; --suave:#E4E6DD; --verde:#16624A; --ambar:#96601F; --rojo:#9E3A2B;
}}
@media (prefers-color-scheme:dark){{:root{{
  --bg:#12150F; --sup:#1A1E17; --sup2:#232820; --ink:#E9EBE2; --mut:#9AA292;
  --linea:#2E342A; --suave:#262B22; --verde:#5FB394; --ambar:#D3A05C; --rojo:#DE8878;
}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:15px;line-height:1.5}}
.wrap{{max-width:1040px;margin:0 auto;padding:28px 18px 80px}}
h1,h2,h3{{font-family:"Bricolage Grotesque",system-ui,sans-serif;margin:0;letter-spacing:-.015em}}
h1{{font-size:1.7rem;font-weight:700}}
h2{{font-size:1.05rem;font-weight:700}}
h3{{font-size:.85rem;font-weight:600}}
.encabezado{{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:18px}}
.sello{{font-size:.78rem;color:var(--mut);font-variant-numeric:tabular-nums}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;
  background:var(--linea);border:1px solid var(--linea);border-radius:3px;overflow:hidden;margin-bottom:26px}}
.kpi{{background:var(--sup);padding:13px 15px}}
.kpi b{{display:block;font-family:"Bricolage Grotesque",sans-serif;font-size:1.5rem;
  font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}}
.kpi span{{font-size:.76rem;color:var(--mut)}}
.kpi.malo b{{color:var(--rojo)}}
section{{margin-bottom:26px}}
.alerta{{background:var(--sup);border:1px solid var(--rojo);border-left-width:3px;border-radius:3px;padding:15px 18px}}
.alerta h2{{color:var(--rojo)}}
.alerta ul{{margin:8px 0 0;padding-left:18px}}
.alerta li{{margin:3px 0;font-size:.92rem}}
.cuenta{{display:inline-block;margin-left:8px;font-size:.72rem;font-weight:600;
  background:var(--sup2);color:var(--mut);border-radius:99px;padding:1px 8px;vertical-align:2px}}
.obra{{background:var(--sup);border:1px solid var(--linea);border-radius:3px;overflow:hidden}}
.obra>header{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
  flex-wrap:wrap;padding:13px 18px;border-bottom:1px solid var(--linea);background:var(--sup2)}}
.meta{{font-size:.8rem;color:var(--mut);font-variant-numeric:tabular-nums}}
.tabla{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:540px}}
td{{padding:9px 12px;border-bottom:1px solid var(--suave);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr.grupo td{{background:var(--sup2);font-size:.72rem;font-weight:600;letter-spacing:.09em;
  text-transform:uppercase;color:var(--mut);padding:6px 18px}}
td.nom{{padding-left:18px;font-weight:500}}
.nota{{font-size:.78rem;color:var(--mut);font-weight:400;margin-top:1px}}
.chips{{display:inline-flex;gap:3px}}
.chip{{width:19px;height:19px;border-radius:3px;border:1px solid var(--linea);
  background:transparent;color:var(--mut);font-size:.66rem;font-weight:600;
  display:inline-flex;align-items:center;justify-content:center}}
.chip.on{{background:var(--verde);border-color:var(--verde);color:var(--bg)}}
td.pct{{white-space:nowrap;width:150px}}
.barra{{display:inline-block;width:78px;height:6px;background:var(--suave);
  border-radius:99px;overflow:hidden;vertical-align:middle;margin-right:7px}}
.barra i{{display:block;height:100%;background:var(--verde)}}
td.pct b{{font-size:.82rem;font-variant-numeric:tabular-nums;font-weight:600}}
td.st{{text-align:right;padding-right:18px;white-space:nowrap}}
.est{{font-size:.78rem;color:var(--mut)}}
.est.ok{{color:var(--verde)}}
.est.mal{{color:var(--rojo);font-weight:600}}
.quieto{{display:block;font-size:.72rem;color:var(--ambar)}}
tr.atrasado td.nom{{box-shadow:inset 3px 0 0 var(--rojo)}}
.rejilla{{display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:10px;margin-top:10px}}
.tarjeta{{background:var(--sup);border:1px solid var(--linea);border-radius:3px;padding:12px 14px}}
.tarjeta h3{{color:var(--verde);margin-bottom:5px}}
.tarjeta ul{{margin:0;padding-left:16px}}
.tarjeta li{{font-size:.85rem;margin:3px 0}}
td.n{{font-variant-numeric:tabular-nums;text-align:right}}
footer{{color:var(--mut);font-size:.8rem;border-top:1px solid var(--linea);padding-top:14px}}
</style></head><body>
<div class="wrap">
  <div class="encabezado">
    <h1>Proceso y entrega</h1>
    <div class="sello">Actualizado {hora}</div>
  </div>

  <div class="kpis">
    <div class="kpi"><b>{total}</b><span>muebles activos</span></div>
    <div class="kpi"><b>{terminados}</b><span>terminados</span></div>
    <div class="kpi{' malo' if atrasados else ''}"><b>{len(atrasados)}</b><span>atrasados</span></div>
    <div class="kpi"><b>{sin_empezar}</b><span>sin empezar</span></div>
    <div class="kpi"><b>{avance}%</b><span>avance promedio</span></div>
  </div>

  {bloque_atrasados}
  {"".join(secciones)}
  {bloque_pend}
  {bloque_cot}

  <footer>Grupo Morales · se actualiza solo cada 2 minutos.
  Para cambiar algo, escríbele al asistente por WhatsApp.</footer>
</div>
<script>setTimeout(()=>location.reload(),120000);</script>
</body></html>"""
