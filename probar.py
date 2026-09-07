"""Probar el asistente desde la terminal, sin WhatsApp.

    python probar.py                      # conversación interactiva
    python probar.py "cómo va bosque real" # una sola pregunta
    python probar.py --modelos            # lista los modelos disponibles

Usa la misma base y las mismas herramientas que usará WhatsApp: lo que
funcione aquí funciona allá.
"""
import sys

from app import agente, config, db


def listar_modelos():
    from app import llm
    print(f"Modelos disponibles en {config.PROVEEDOR}:")
    for m in llm.proveedor().modelos():
        print(" ", m)


def main() -> int:
    faltan = config.faltantes()
    if faltan:
        print("Faltan variables en .env:", ", ".join(faltan))
        return 1

    if "--modelos" in sys.argv:
        listar_modelos()
        return 0

    persona = (db.db().table("personas").select("*")
               .eq("rol", "admin").limit(1).execute().data or [None])[0]
    if not persona:
        print("No hay ninguna persona con rol admin en la tabla personas.")
        return 1

    historial: list[dict] = []

    if len(sys.argv) > 1:
        print(agente.responder(" ".join(sys.argv[1:]), persona))
        return 0

    print(f"Asistente de obra — {config.MODELO} vía {config.PROVEEDOR}, "
          f"hablando como {persona['nombre']}. Ctrl-C para salir.\n")
    while True:
        try:
            texto = input("tú › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not texto:
            continue
        r = agente.responder(texto, persona, historial)
        print(f"\n{r}\n")
        historial.append({"role": "user", "content": texto})
        historial.append({"role": "assistant", "content": r})
        historial = historial[-12:]


if __name__ == "__main__":
    sys.exit(main())
