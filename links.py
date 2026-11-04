"""Los links del panel, uno por persona.

    python links.py                     # los imprime
    python links.py --renovar "Beto"    # le da token nuevo a esa persona

Cada quien entra con el suyo, y la bitácora guarda su nombre en cada
cambio. Repártelos uno por uno, nunca todos en el mismo mensaje: un link
es la llave del panel.

Si alguien deja el taller, no hace falta renovar nada — basta
desactivarlo en Supabase:

    update personas set activo = false where nombre = 'Beto';
"""
import sys

from app import config, db

BASE = (config.TABLERO_URL or "").rstrip("/").removesuffix("/panel")


def main() -> int:
    faltan = config.faltantes()
    if faltan:
        print("Faltan variables en .env:", ", ".join(faltan))
        return 1

    if "--renovar" in sys.argv:
        i = sys.argv.index("--renovar")
        if i + 1 >= len(sys.argv):
            print('Falta el nombre: python links.py --renovar "Beto"')
            return 1
        quien = sys.argv[i + 1].strip().lower()
        gente = db._rpc("links_del_panel")
        encontrado = [p for p in gente if quien in (p["nombre"] or "").lower()]
        if len(encontrado) != 1:
            print(f"'{sys.argv[i+1]}' coincide con {len(encontrado)} personas. "
                  "Usa el nombre completo.")
            return 1
        p = encontrado[0]
        pid = db.db().table("personas").select("id").eq("telefono", p["telefono"]) \
                .execute().data[0]["id"]
        nuevo = db._rpc("renovar_token", p_persona_id=pid)
        print(f"\nToken nuevo para {p['nombre']}. El anterior ya no sirve.\n")
        print(f"  {enlace(nuevo)}\n")
        return 0

    gente = db._rpc("links_del_panel")
    if not gente:
        print("No hay nadie en `personas`. Corre db/02_seed.sql.")
        return 1

    if not BASE:
        print("Aviso: TABLERO_URL no está en el .env, así que abajo va sólo\n"
              "       el token. Ponla (ej. https://tu-app.up.railway.app)\n"
              "       y vuelve a correr esto para ver el link completo.\n")

    print(f"{'PERSONA':<22} {'ROL':<8} LINK")
    print("-" * 78)
    for p in gente:
        estado = "" if p["activo"] else "  (DESACTIVADO: no entra)"
        print(f"{(p['nombre'] or '')[:21]:<22} {p['rol']:<8} "
              f"{enlace(p['token'])}{estado}")
    print("\nMándalos por separado. Quien tenga el link puede editar el tablero.")
    return 0


def enlace(token: str) -> str:
    return f"{BASE}/panel?k={token}" if BASE else f"?k={token}"


if __name__ == "__main__":
    sys.exit(main())
