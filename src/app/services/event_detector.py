"""Event detection service using OpenAI for NLP.

NOTE: Este servicio es OPCIONAL. El NLP principal corre en n8n.
Solo se usa si OPENAI_API_KEY está configurado y se llama explícitamente.
"""

import json
from datetime import date as date_type
from datetime import datetime, timedelta
from datetime import time as time_type

from ..config.settings import get_settings
from ..schemas.calendar import AgentDetectEventResponse, DetectedEvent

settings = get_settings()

# Initialize OpenAI client only if API key is configured
client = None
if settings.openai_api_key and settings.openai_api_key != "sk-your-openai-key":
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
    except ImportError:
        pass  # OpenAI not installed, that's OK

# System prompt for event detection
EVENT_DETECTION_PROMPT = """Eres un asistente que detecta eventos agendables en mensajes de usuarios.

Tu tarea es analizar el mensaje y determinar si menciona un evento que debería agregarse al calendario.

Tipos de eventos a detectar:
- Turnos médicos, dentista, etc.
- Reuniones de trabajo
- Citas personales
- Eventos familiares (cumpleaños, cenas, etc.)
- Actividades programadas (clases, gimnasio, etc.)
- Deadlines o fechas límite

NO detectes como eventos:
- Comentarios casuales sobre el pasado
- Preguntas generales
- Saludos o conversación sin agenda

Para cada evento detectado, extrae:
- title: Título descriptivo del evento
- date: Fecha en formato YYYY-MM-DD (si no se especifica, asume hoy o mañana según contexto)
- time: Hora en formato HH:MM (24h)
- duration_minutes: Duración estimada (default 60)
- location: Ubicación si se menciona
- is_recurring: Si es un evento recurrente
- recurrence_pattern: Patrón de recurrencia (ej: "todos los lunes", "cada semana")

Responde SIEMPRE en formato JSON con esta estructura:
{
    "detected": true/false,
    "confidence": 0.0-1.0,
    "event": {
        "title": "...",
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "duration_minutes": 60,
        "location": null,
        "is_recurring": false,
        "recurrence_pattern": null
    },
    "missing_fields": ["lista de campos faltantes"],
    "message": "Mensaje para el usuario"
}

Si no detectas ningún evento, responde:
{
    "detected": false,
    "confidence": 0.0,
    "event": null,
    "missing_fields": [],
    "message": "No se detectó ningún evento para agendar."
}

Fecha actual: {current_date}
Día de la semana: {weekday}
"""

WEEKDAYS_ES = [
    "Lunes", "Martes", "Miércoles", "Jueves", 
    "Viernes", "Sábado", "Domingo"
]


async def detect_event_in_message(
    message: str,
    user_phone: str,
    context: list[dict] | None = None,
) -> AgentDetectEventResponse:
    """Detect if a message contains an event that should be scheduled."""
    if not client:
        return AgentDetectEventResponse(
            detected=False,
            confidence=0.0,
            needs_confirmation=False,
            message="Servicio de detección no configurado.",
        )

    today = date.today()
    weekday = WEEKDAYS_ES[today.weekday()]

    system_prompt = EVENT_DETECTION_PROMPT.format(
        current_date=today.isoformat(),
        weekday=weekday,
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    if context:
        for ctx in context[-5:]:
            messages.append({
                "role": ctx.get("role", "user"),
                "content": ctx.get("content", ""),
            })

    messages.append({"role": "user", "content": message})

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500,
        )

        result = json.loads(response.choices[0].message.content)

        if not result.get("detected", False):
            return AgentDetectEventResponse(
                detected=False,
                confidence=result.get("confidence", 0.0),
                needs_confirmation=False,
                message=result.get("message", "No se detectó ningún evento."),
            )

        event_data = result.get("event", {})
        
        detected_event = DetectedEvent(
            title=event_data.get("title", "Evento"),
            event_date=_parse_date(event_data.get("date")),
            start_time=_parse_time(event_data.get("time")),
            duration_minutes=event_data.get("duration_minutes", 60),
            location=event_data.get("location"),
            is_recurring=event_data.get("is_recurring", False),
            recurrence_pattern=event_data.get("recurrence_pattern"),
        )

        missing_fields = result.get("missing_fields", [])
        confidence = result.get("confidence", 0.8)

        needs_confirmation = (
            confidence < 0.9 or
            len(missing_fields) > 0 or
            detected_event.event_date is None or
            detected_event.start_time is None
        )

        if needs_confirmation:
            msg = _build_confirmation_message(detected_event, missing_fields)
        else:
            msg = result.get("message", "Evento detectado.")

        return AgentDetectEventResponse(
            detected=True,
            event_suggestion=detected_event,
            confidence=confidence,
            needs_confirmation=needs_confirmation,
            missing_fields=missing_fields,
            message=msg,
        )

    except Exception as e:
        return AgentDetectEventResponse(
            detected=False,
            confidence=0.0,
            needs_confirmation=False,
            message=f"Error al analizar mensaje: {str(e)}",
        )


def _parse_date(date_str: str | None) -> date_type | None:
    """Parse date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(time_str: str | None) -> time_type | None:
    """Parse time string to time object."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None


def _build_confirmation_message(
    event: DetectedEvent,
    missing_fields: list[str],
) -> str:
    """Build a user-friendly confirmation message."""
    parts = [f"📅 Detecté un posible evento: \"{event.title}\""]

    if event.event_date:
        parts.append(f"📆 Fecha: {_format_date(event.event_date)}")
    
    if event.start_time:
        parts.append(f"🕐 Hora: {event.start_time.strftime('%H:%M')}")

    if event.location:
        parts.append(f"📍 Ubicación: {event.location}")

    if missing_fields:
        missing_es = {
            "date": "fecha",
            "time": "hora",
            "location": "ubicación",
            "duration": "duración",
        }
        missing_text = ", ".join(missing_es.get(f, f) for f in missing_fields)
        parts.append(f"\n⚠️ Falta: {missing_text}")

    parts.append("\n¿Querés que lo agende?")

    return "\n".join(parts)


def _format_date(d: date_type) -> str:
    """Format date in Spanish."""
    today = date_type.today()
    
    if d == today:
        return "Hoy"
    elif d == today + timedelta(days=1):
        return "Mañana"
    elif d == today + timedelta(days=2):
        return "Pasado mañana"
    else:
        weekday = WEEKDAYS_ES[d.weekday()]
        return f"{weekday} {d.day}/{d.month}"
