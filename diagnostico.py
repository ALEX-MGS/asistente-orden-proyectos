"""Revisa la conexión antes de culpar al asistente.

    python diagnostico.py

Prueba en orden: qué dice el .env, si el dominio resuelve, si contesta
por HTTPS, si la llave sirve, y si el proveedor del modelo responde.
El primer paso que falle es el problema.
"""
import os
import socket
import sys
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

OK, MAL = "  ok  ", " FALLA"


def linea(estado, texto, detalle=""):
    print(f"[{estado}] {texto}")
    if detalle:
        for l in str(detalle).splitlines():
            print(f"         {l}")


def main() -> int:
    load_dotenv()
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

    # 1. forma de la URL --------------------------------------------------
    if not url:
        linea(MAL, "SUPABASE_URL está vacía en el .env")
        return 1
    print(f"SUPABASE_URL = {url!r}\n")

    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        linea(MAL, "La URL debe empezar con https:// y no llevar nada más",
              "Supabase → Settings → API → Project URL")
        return 1
    if p.hostname.startswith("db."):
        linea(MAL, f"Ese es el host de la BASE DE DATOS ({p.hostname}), no el de la API",
              "Ese host habla Postgres en el puerto 5432 y tira la conexión si le\n"
              "hablas HTTPS — que es exactamente el 'Connection reset by peer'.\n"
              "Usa el Project URL: https://<ref>.supabase.co (sin el 'db.')")
        return 1
    if p.path.rstrip("/") or p.port:
        linea(MAL, "La URL trae ruta o puerto de más",
              f"Debe ser exactamente: https://{p.hostname}")
        return 1
    linea(OK, "La URL tiene la forma correcta")

    # 2. DNS ---------------------------------------------------------------
    try:
        ip = socket.gethostbyname(p.hostname)
        linea(OK, f"El dominio resuelve ({ip})")
    except socket.gaierror as e:
        linea(MAL, "El dominio no resuelve — revisa que el proyecto exista", e)
        return 1

    # 3. HTTPS -------------------------------------------------------------
    try:
        r = httpx.get(f"{url}/rest/v1/", timeout=15)
        linea(OK, f"Responde por HTTPS (código {r.status_code})")
    except Exception as e:
        linea(MAL, "No se pudo abrir la conexión HTTPS", f"{type(e).__name__}: {e}")
        print("\n  Si la URL está bien, casi siempre es una de estas:\n"
              "   · el proyecto de Supabase está pausado (el plan gratis se\n"
              "     duerme tras días sin uso) — entra al panel y despiértalo\n"
              "   · una VPN o el firewall de la red está cortando la conexión")
        return 1

    # 4. llave -------------------------------------------------------------
    if not key:
        linea(MAL, "SUPABASE_SERVICE_ROLE_KEY está vacía")
        return 1
    try:
        r = httpx.get(f"{url}/rest/v1/personas?select=nombre,rol",
                      headers={"apikey": key, "Authorization": f"Bearer {key}"},
                      timeout=15)
        if r.status_code == 200:
            linea(OK, f"La llave sirve y hay {len(r.json())} persona(s) dadas de alta")
            for x in r.json():
                print(f"         · {x['nombre']} ({x['rol']})")
        else:
            linea(MAL, f"La base contestó {r.status_code}", r.text[:300])
            return 1
    except Exception as e:
        linea(MAL, "Error consultando la tabla personas", e)
        return 1

    # 5. proveedor del modelo ---------------------------------------------
    from app import config
    if not config.API_KEY:
        linea(MAL, f"Falta la llave del proveedor ({config.PROVEEDOR})")
        return 1
    try:
        from app import llm
        modelos = llm.proveedor().modelos()
        hay = config.MODELO in modelos
        linea(OK if hay else MAL,
              f"{config.PROVEEDOR}: {len(modelos)} modelos disponibles"
              + ("" if hay else f" — pero '{config.MODELO}' NO está entre ellos"))
        if not hay:
            print("         Algunos que sí puedes usar:")
            for m in modelos[:12]:
                print(f"         · {m}")
            return 1
    except Exception as e:
        linea(MAL, f"No se pudo hablar con {config.PROVEEDOR}", f"{type(e).__name__}: {e}")
        return 1

    print("\nTodo en orden. Ya puedes correr:  python probar.py \"cómo va silver deer\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
