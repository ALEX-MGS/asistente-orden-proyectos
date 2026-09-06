"""Prueba de salida de la Fase 0.

Se conecta a Supabase e imprime el tablero completo desde la base.
Si esto corre, el dato ya vive fuera del panel y todo lo demás
—el bot, los resúmenes, la imagen— se construye encima sin volver a tocarlo.

    python check_db.py
"""
import os
import sys

from dotenv import load_dotenv
from supabase import create_client

ANCHO = 20  # ancho de la barra de avance


def barra(avance: float) -> str:
    lleno = round(avance * ANCHO)
    return "#" * lleno + "." * (ANCHO - lleno)


def main() -> int:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
        print("Cópialas de Supabase → Settings → API.")
        return 1

    db = create_client(url, key)

    muebles = (
        db.table("v_muebles")
        .select("*")
        .eq("archivado", False)
        .order("obra")
        .order("orden")
        .execute()
        .data
    )

    if not muebles:
        print("Conectó bien, pero no hay muebles. ¿Corriste db/02_seed.sql?")
        return 0

    obra_actual = None
    atrasados = []
    for m in muebles:
        if m["obra"] != obra_actual:
            obra_actual = m["obra"]
            print(f"\n  {obra_actual.upper()}")
            print("  " + "-" * 72)

        avance = float(m["avance"])
        estado = "terminado" if m["terminado"] else f"sigue {(m['sigue'] or '').lower()}"
        if m["atrasado"]:
            estado += "  ATRASADO"
            atrasados.append(m)
        print(f"  {barra(avance)} {avance:>4.0%}  {m['nombre'][:38]:<38} {estado}")

    pendientes = (
        db.table("pendientes")
        .select("texto, obras(nombre)")
        .eq("hecho", False)
        .execute()
        .data
    )
    if pendientes:
        print(f"\n  PENDIENTES ABIERTOS ({len(pendientes)})")
        print("  " + "-" * 72)
        for p in pendientes:
            obra = (p.get("obras") or {}).get("nombre", "-")
            print(f"  {obra[:22]:<22} {p['texto'][:50]}")

    cotiz = (
        db.table("cotizaciones")
        .select("cliente, concepto, monto, estado")
        .neq("estado", "rechazada")
        .execute()
        .data
    )
    if cotiz:
        print(f"\n  COTIZACIONES ({len(cotiz)})")
        print("  " + "-" * 72)
        for c in cotiz:
            monto = f"${float(c['monto']):,.0f}" if c.get("monto") else "-"
            print(f"  {c['cliente'][:22]:<22} {(c['concepto'] or '')[:28]:<28} "
                  f"{monto:>12}  {c['estado']}")

    terminados = sum(1 for m in muebles if m["terminado"])
    print(f"\n  {len(muebles)} muebles · {terminados} terminados · "
          f"{len(atrasados)} atrasados. Fase 0 lista.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
