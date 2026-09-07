"""Adaptador de proveedor.

El resto del código no sabe con qué modelo está hablando. Aquí adentro
viven las dos formas de pedir herramientas que existen hoy: la de
Anthropic y la de OpenAI — que además usan DeepSeek, Groq, Gemini,
Mistral y xAI, así que cambiar de proveedor es cambiar la URL base.

Todo se decide con PROVEEDOR en el .env.
"""
import json
from dataclasses import dataclass, field

from . import config


@dataclass
class Llamada:
    id: str
    nombre: str
    args: dict


@dataclass
class Respuesta:
    texto: str = ""
    llamadas: list[Llamada] = field(default_factory=list)
    crudo: object = None

    @property
    def quiere_herramientas(self) -> bool:
        return bool(self.llamadas)


# =====================================================================
# Anthropic
# =====================================================================
class Anthropico:
    nombre = "anthropic"

    def __init__(self):
        from anthropic import Anthropic
        self.c = Anthropic(api_key=config.API_KEY)

    def herramientas(self, defs):
        return defs  # ya vienen en su formato

    def llamar(self, sistema, mensajes, defs) -> Respuesta:
        r = self.c.messages.create(
            model=config.MODELO,
            max_tokens=config.MAX_TOKENS,
            system=sistema,
            tools=self.herramientas(defs),
            messages=mensajes,
        )
        texto = "".join(b.text for b in r.content if b.type == "text").strip()
        llamadas = [Llamada(b.id, b.name, b.input)
                    for b in r.content if b.type == "tool_use"]
        return Respuesta(texto, llamadas, r.content)

    def anotar_asistente(self, mensajes, r: Respuesta):
        mensajes.append({"role": "assistant", "content": r.crudo})

    def anotar_resultados(self, mensajes, resultados):
        mensajes.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": x["id"],
             "content": x["salida"], "is_error": x["error"]}
            for x in resultados
        ]})

    def modelos(self):
        return [m.id for m in self.c.models.list(limit=30).data]


# =====================================================================
# OpenAI y todo lo compatible (DeepSeek, Groq, Gemini, Mistral, xAI)
# =====================================================================
class CompatibleOpenAI:
    nombre = "openai"

    def __init__(self):
        from openai import OpenAI
        kw = {"api_key": config.API_KEY}
        if config.BASE_URL:
            kw["base_url"] = config.BASE_URL
        self.c = OpenAI(**kw)

    def herramientas(self, defs):
        return [{"type": "function", "function": {
            "name": d["name"],
            "description": d["description"],
            "parameters": d["input_schema"],
        }} for d in defs]

    def llamar(self, sistema, mensajes, defs) -> Respuesta:
        r = self.c.chat.completions.create(
            model=config.MODELO,
            max_completion_tokens=config.MAX_TOKENS,
            messages=[{"role": "system", "content": sistema}] + mensajes,
            tools=self.herramientas(defs),
        )
        m = r.choices[0].message
        llamadas = []
        for tc in (m.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            llamadas.append(Llamada(tc.id, tc.function.name, args))
        return Respuesta((m.content or "").strip(), llamadas, m)

    def anotar_asistente(self, mensajes, r: Respuesta):
        m = {"role": "assistant", "content": r.texto or None}
        if r.llamadas:
            m["tool_calls"] = [{
                "id": l.id, "type": "function",
                "function": {"name": l.nombre, "arguments": json.dumps(l.args)},
            } for l in r.llamadas]
        mensajes.append(m)

    def anotar_resultados(self, mensajes, resultados):
        # OpenAI quiere un mensaje por herramienta, no uno con todos.
        for x in resultados:
            mensajes.append({"role": "tool", "tool_call_id": x["id"],
                             "content": x["salida"]})

    def modelos(self):
        return sorted(m.id for m in self.c.models.list().data)


def proveedor():
    if config.PROVEEDOR == "anthropic":
        return Anthropico()
    return CompatibleOpenAI()
