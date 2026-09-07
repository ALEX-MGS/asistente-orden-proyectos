"""Configuración leída del .env."""
import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# --- proveedor del modelo --------------------------------------------
# 'openai'    → OpenAI y todo lo compatible (DeepSeek, Groq, Gemini, xAI)
# 'anthropic' → Claude
PROVEEDOR = os.getenv("PROVEEDOR", "openai").lower().strip()

# Para proveedores compatibles con OpenAI que no son OpenAI, poner su URL:
#   DeepSeek  https://api.deepseek.com
#   Groq      https://api.groq.com/openai/v1
#   Gemini    https://generativelanguage.googleapis.com/v1beta/openai
BASE_URL = os.getenv("BASE_URL", "")

API_KEY = (os.getenv("ANTHROPIC_API_KEY", "") if PROVEEDOR == "anthropic"
           else os.getenv("OPENAI_API_KEY", ""))

# Si el modelo no existe, `python probar.py --modelos` lista los tuyos.
MODELO = os.getenv("MODELO", "gpt-4o" if PROVEEDOR != "anthropic" else "claude-sonnet-4-5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1200"))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# La URL pública exacta que configuraste en Twilio, con /whatsapp al final.
# Twilio firma esa URL; si aquí ponemos otra, la firma nunca cuadra.
URL_PUBLICA = os.getenv("URL_PUBLICA", "")

HISTORIAL = int(os.getenv("HISTORIAL", "12"))


def faltantes() -> list[str]:
    """Variables obligatorias que no están puestas."""
    llave = "ANTHROPIC_API_KEY" if PROVEEDOR == "anthropic" else "OPENAI_API_KEY"
    req = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_KEY,
        llave: API_KEY,
    }
    return [k for k, v in req.items() if not v]
