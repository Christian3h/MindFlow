import re
from datetime import datetime, timedelta
from typing import Optional


def parse_sleep_response(text: str) -> dict | None:
    """
    Parsea mensajes como:
    "acosté 11pm, levanté 7am, energía 7"
    "dormí 8 horas, energia 8"
    "me acosté a las 23, desperté 7, energia 6"
    """
    text = text.lower().strip()

    hora_acostado = _extract_bedtime(text)
    hora_levantado = _extract_wakeup(text)
    duracion = _extract_duration(text, hora_acostado, hora_levantado)
    energia = _extract_energy(text)

    if hora_levantado is None:
        return None

    return {
        "hora_acostado": hora_acostado,
        "hora_levantado": hora_levantado,
        "duracion_horas": duracion,
        "energia_al_despertar": energia,
        "fecha": datetime.now().strftime("%Y-%m-%d")
    }


def _extract_bedtime(text: str) -> str | None:
    patterns = [
        r"acost[ée]\s*(?:a\s*las?\s*)?(\d{1,2})\s*(am|pm)?",
        r"dorm[íi]\s*(?:a\s*las?\s*)?(\d{1,2})\s*(am|pm)?",
        r"me\s+acost[ée]\s*a\s*las?\s*(\d{1,2})\s*(am|pm)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            hour = int(match.group(1))
            period = match.group(2)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:00"

    return None


def _extract_wakeup(text: str) -> str | None:
    patterns = [
        r"levant[ée]\s*(?:a\s*las?\s*)?(\d{1,2})\s*(am|pm)?",
        r"despert[ée]\s*(?:a\s*las?\s*)?(\d{1,2})\s*(am|pm)?",
        r"me\s+levant[ée]\s*a\s*las?\s*(\d{1,2})\s*(am|pm)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            hour = int(match.group(1))
            period = match.group(2)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:00"

    return None


def _extract_duration(text: str, hora_acostado: str | None, hora_levantado: str | None) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:horas?|hrs?|h)", text)
    if match:
        return float(match.group(1))

    if hora_acostado and hora_levantado:
        bed_h, bed_m = map(int, hora_acostado.split(":"))
        wake_h, wake_m = map(int, hora_levantado.split(":"))

        if wake_h < bed_h:
            wake_h += 24

        total_minutes = (wake_h * 60 + wake_m) - (bed_h * 60 + bed_m)
        return round(total_minutes / 60, 1)

    return None


def _extract_energy(text: str) -> int | None:
    patterns = [
        r"energ[íi]a\s*(\d+)",
        r"eneerg[íi]a\s*(\d+)",
        r"(\d+)\s*/\s*10",
        r"sent[íi]\s*(\d+)",
        r"([456789]|10)\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 10:
                return value

    if any(word in text for word in ["bien", "bien!", "genial", "excelente"]):
        return 8
    if any(word in text for word in ["mal", "cansado", "dormido"]):
        return 4

    return None


def format_sleep_summary(data: dict) -> str:
    duracion = data.get("duracion_horas", "?")
    energia = data.get("energia_al_despertar", "?")
    acostado = data.get("hora_acostado", "?")
    levantado = data.get("hora_levantado", "?")

    return f"Dormiste {duracion}h ({acostado} → {levantado}), energía {energia}/10"