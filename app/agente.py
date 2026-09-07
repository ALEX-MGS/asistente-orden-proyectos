"""El ciclo del asistente: mensaje → modelo → herramientas → respuesta.

Qué modelo, lo decide app/llm.py según PROVEEDOR en el .env.
"""
from datetime import date

from . import config, db, herramientas, llm

_proveedor = None

INSTRUCCIONES = """Eres el asistente de producción de Grupo Morales, una carpintería \
de la Ciudad de México con más de cien años de oficio. Contestas por WhatsApp a Alex \
y a la gente del taller.

HOY ES {hoy}.

Cómo habla la gente aquí, y cómo debes entenderla:
- "mob" es mueble, y casi siempre viene con número: "el mob 7", "mob 4 y 5".
- "arq" es arquitecto.
- Las obras se llaman por su nombre corto: Silver Deer, Bosque Real, Onofre, Ahuehuetes.
- "salió de barniz" quiere decir que la etapa de barniz ya quedó.
- "ya se entregó", "ya se instaló", "ya lo pusieron" son etapas cumplidas.

Las cinco etapas, en orden, cada una vale 20%: aprobado, carpinteria, barniz, entrega, \
instalacion. Un mueble puede tener palomeadas las que sea; normalmente van en orden.

REGLAS QUE NO SE ROMPEN:

1. Antes de actualizar o fechar un mueble, búscalo. Nunca inventes un mueble_id.
2. Si la búsqueda devuelve más de un candidato razonable, NO adivines: pregunta cuál, \
listando los que encontraste con su obra y su avance.
3. Si la búsqueda no devuelve nada, dilo y pregunta cómo se llama exactamente. No crees \
un mueble nuevo a menos que te lo pidan claramente.
4. Después de CADA cambio, confirma exactamente lo que quedó anotado, con obra, mueble, \
etapa y el avance nuevo. Ejemplo: "Anotado: MOB 7 · Silver Deer → barniz ✓ 60%".
5. Si te dicen que te equivocaste, usa deshacer.
6. Varios cambios en un mismo mensaje se hacen todos, y se confirman todos.

Cómo escribes:
- Es WhatsApp: corto, sin encabezados, sin negritas, sin tablas. Renglones sueltos.
- En un resumen, lo atrasado va primero. Luego lo que está en proceso. Lo terminado se \
menciona en una línea, no se enlista.
- Nada de relleno. Ni "claro", ni "por supuesto", ni repetir la pregunta.
- Usa ✓ para lo hecho y ⚠ sólo para lo atrasado. Nada más de símbolos.
- Si algo no se pudo hacer, dilo claro y di por qué.
"""


def proveedor():
    global _proveedor
    if _proveedor is None:
        _proveedor = llm.proveedor()
    return _proveedor


def responder(texto: str, persona: dict | None = None,
              historial: list[dict] | None = None, max_vueltas: int = 8) -> str:
    """Procesa un mensaje y devuelve la respuesta lista para mandar."""
    persona_id = (persona or {}).get("id")
    nombre = (persona or {}).get("nombre", "alguien del taller")

    sistema = INSTRUCCIONES.format(hoy=date.today().isoformat())
    sistema += f"\n\nQuien te escribe es {nombre}."

    mensajes = list(historial or [])
    mensajes.append({"role": "user", "content": texto})

    p = proveedor()

    for _ in range(max_vueltas):
        r = p.llamar(sistema, mensajes, herramientas.HERRAMIENTAS)
        p.anotar_asistente(mensajes, r)

        if not r.quiere_herramientas:
            return r.texto

        resultados = []
        for l in r.llamadas:
            salida, hubo_error = herramientas.ejecutar(l.nombre, l.args, persona_id, texto)
            resultados.append({"id": l.id, "salida": salida, "error": hubo_error})
        p.anotar_resultados(mensajes, resultados)

    return "Me enredé procesando eso. ¿Me lo dices de otra forma?"


def responder_a(telefono: str, texto: str) -> str:
    """Igual que responder(), pero resolviendo persona e historial desde la base."""
    persona = db.persona_por_telefono(telefono)
    if not persona:
        return ("Este número no está autorizado. Pídele a Alex que lo dé de alta.")
    hist = db.historial(telefono)
    return responder(texto, persona, hist)
