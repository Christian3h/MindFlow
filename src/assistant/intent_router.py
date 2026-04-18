import re
from dataclasses import dataclass
from typing import Optional


INTENTS = [
    "saludo", "gasto", "sueno", "checkin", "pregunta", "despedida",
    "confirmacion", "evento_crear", "evento_completar", "evento_ver",
    "pregunta_programada", "rutina_crear", "deuda_registrar", "deuda_pagar",
    "sueldo_registrar", "unknown"
]


GASTO_PATTERNS = [
    re.compile(r"gast[ée]\s+[\d.,]+\s*mil?", re.IGNORECASE),
    re.compile(r"gast[ée]\s+[\d.,]+", re.IGNORECASE),
    re.compile(r"pag[ué]\s+[\d.,]+\s*mil?", re.IGNORECASE),
    re.compile(r"compr[ée]\s+", re.IGNORECASE),
]

SUENO_PATTERNS = [
    re.compile(r"(?:acost[ée]|dorm[íi])\s+\d+\s*(?:am|pm|hrs?)", re.IGNORECASE),
    re.compile(r"(?:levant[ée]|despert[ée])\s+\d+\s*(?:am|pm)?", re.IGNORECASE),
    re.compile(r"dorm[ií]\s+\d+", re.IGNORECASE),
    re.compile(r"sue[ñn]o", re.IGNORECASE),
    re.compile(r"anoche\s+(?:no\s+)?dorm[íi]", re.IGNORECASE),
]

CHECKIN_PATTERNS = [
    re.compile(r"(?:estaba|estoy|estuv[ée])\s+(?:en\s+)?(redes|instagram|tiktok|youtube|facebook)", re.IGNORECASE),
    re.compile(r"(?:no\s+)?estaba\s+(?:en\s+)?(?:el?\s+)?(?:estudio|trabajo|gym|reunión)", re.IGNORECASE),
    re.compile(r"(?:me\s+)?distraj[ée]", re.IGNORECASE),
    re.compile(r"no\s+(?:estoy|en)\s+(?:el|l)\s+\w+", re.IGNORECASE),
]

SALUDO_PATTERNS = [
    re.compile(r"^(?:hola|hi|buenos?\s*d[ií]as|buenas?\s*tardes|buenas?\s*noches|qué\s*tal|cómo\s+vas|cómo\s+estás)", re.IGNORECASE),
    re.compile(r"^(?:saludos|hola\s+bien)", re.IGNORECASE),
]

DESPEDIDA_PATTERNS = [
    re.compile(r"^(?:chau|adiós|nos\s+vemos|hasta\s+luego|me\s+voy|me\s+voy\s+a)", re.IGNORECASE),
    re.compile(r"^(?:buenas?\s+noches)\s*$", re.IGNORECASE),
]

CONFIRMACION_PATTERNS = [
    re.compile(r"^(?:sí|si|yea|yep|claro|dale|ok|bueno|va|perfect|afirmativo)", re.IGNORECASE),
    re.compile(r"^(?:no\s+importa|no\s+pasa|nada)", re.IGNORECASE),
]

EVENTO_CREAR_PATTERNS = [
    re.compile(r"agreg[áa]\s+(?:un[ao]?\s+)?(?:evento|cita|recordatorio)", re.IGNORECASE),
    re.compile(r"cre[áa]\s+(?:un[ao]?\s+)?(?:evento|cita|recordatorio)", re.IGNORECASE),
    re.compile(r"nuevo\s+(?:evento|cita|recordatorio)", re.IGNORECASE),
    re.compile(r"nueva\s+(?:cita|evento)", re.IGNORECASE),
    re.compile(r"program[áa]\s+", re.IGNORECASE),
    re.compile(r"record[áa]me?\s+(?:que|de)", re.IGNORECASE),
    re.compile(r"ten[go]\s+(?:una\s+)?(?:cita|reunión)", re.IGNORECASE),
    re.compile(r"agregar\s+una?\s+(?:cita|reunión)", re.IGNORECASE),
    re.compile(r"(?:a las?|para|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+\d+\s*(?:am|pm)?", re.IGNORECASE),
]

EVENTO_COMPLETAR_PATTERNS = [
    re.compile(r"ya\s+(?:fue|se\s+hizo|lo\s+hice)", re.IGNORECASE),
    re.compile(r"^(?:listo|completo|hecho|hecha|listo\s+ya)", re.IGNORECASE),
    re.compile(r"ya\s+(?:pas[óo]|termin[óo])", re.IGNORECASE),
    re.compile(r"marc[áa]\s+como\s+completad", re.IGNORECASE),
    re.compile(r"complet[áa]?\s+el\s+(?:evento|cita|recordatorio)", re.IGNORECASE),
    re.compile(r"ya\s+no\s+importa", re.IGNORECASE),
]

EVENTO_VER_PATTERNS = [
    re.compile(r"qu[eé]\s+tengo\s+programado", re.IGNORECASE),
    re.compile(r"qu[eé]\s+(?:tengo|tiene)\s+(?:mañana|hoy|esta\s+semana|programado)", re.IGNORECASE),
    re.compile(r"qu[eé]\s+(?:hay|hay\s+algo)\s+(?:mañana|hoy|programado)", re.IGNORECASE),
    re.compile(r"mis\s+(?:eventos|citas|recordatorios)", re.IGNORECASE),
    re.compile(r"qu[eé]\s+viene", re.IGNORECASE),
    re.compile(r"agenda", re.IGNORECASE),
    re.compile(r"(?:que|qué)\s+compromisos?\s+(?:tengo|tiene|para|del|de)?", re.IGNORECASE),
    re.compile(r"(?:que|qué)\s+pendientes?\s+(?:tengo|tiene|para|del|de)?", re.IGNORECASE),
    re.compile(r"(?:que|qué)\s+tareas?\s+(?:tengo|tiene|para|del|de)?", re.IGNORECASE),
]

PREGUNTA_PROGRAMADA_PATTERNS = [
    re.compile(r"preg[úu]ntame\s+(?:cada|en|a\s+las)", re.IGNORECASE),
    re.compile(r"record[áa]me\s+(?:cada|en|a\s+las|en\s+\d+\s*minutos?|en\s+\d+\s*horas?)", re.IGNORECASE),
    re.compile(r"quisiera\s+que\s+me\s+preguntes", re.IGNORECASE),
    re.compile(r"quiero\s+que\s+me\s+preguntes", re.IGNORECASE),
    re.compile(r"program[áa]\s+(?:una\s+)?pregunta", re.IGNORECASE),
    re.compile(r"cre[áa]\s+(?:una\s+)?pregunta\s+programada", re.IGNORECASE),
    re.compile(r"quiero\s+que\s+me\s+recuerdes\s+dentro\s+de", re.IGNORECASE),
    re.compile(r"dentro\s+de\s+\d+\s*(?:minutos?|horas?|dias?)\s+(?:que|de)?", re.IGNORECASE),
]

RUTINA_CREAR_PATTERNS = [
    re.compile(r"agreg[áa]\s+(?:un[ao]?\s+)?rutina", re.IGNORECASE),
    re.compile(r"cre[áa]\s+(?:un[ao]?\s+)?rutina", re.IGNORECASE),
    re.compile(r"nueva\s+rutina", re.IGNORECASE),
    re.compile(r"nuevo\s+bloque\s+de\s+tiempo", re.IGNORECASE),
    re.compile(r"program[áa]\s+mi\s+rutina", re.IGNORECASE),
]

DEUDA_REGISTRAR_PATTERNS = [
    re.compile(r"tengo\s+(?:una\s+)?deuda", re.IGNORECASE),
    re.compile(r"debo\s+(?:en|a)?\s*(?:bancolombia|davivienda|bbva|bogota|nequi)", re.IGNORECASE),
    re.compile(r"tengo\s+(?:un\s+)?cr[eé]dito", re.IGNORECASE),
    re.compile(r"ped[ií]\s+(?:prestado|préstamo)", re.IGNORECASE),
    re.compile(r"saqu[eé]?\s+(?:un\s+)?pr[eé]stamo", re.IGNORECASE),
]

DEUDA_PAGAR_PATTERNS = [
    re.compile(r"voy\s+a\s+pagar\s+(?:la\s+)?(?:cuota|deuda)", re.IGNORECASE),
    re.compile(r"voy\s+a\s+pagar\s+mi\s+(?:cuota|deuda)", re.IGNORECASE),
    re.compile(r"pagu[eé]?\s+(?:la\s+)?(?:cuota|deuda)", re.IGNORECASE),
    re.compile(r"abono\s+a\s+(?:la\s+)?(?:cuota|deuda)", re.IGNORECASE),
    re.compile(r"voy\s+a\s+dar\s+(?:de\s+)?(?:paga|cuota)", re.IGNORECASE),
]

SUELDO_REGISTRAR_PATTERNS = [
    re.compile(r"gan[ée]\s*[\d.,]+\s*(?:mil)?", re.IGNORECASE),
    re.compile(r"tengo\s+(?:un\s+)?(?:sueldo|ingreso)", re.IGNORECASE),
    re.compile(r"mi\s+(?:sueldo|salario)", re.IGNORECASE),
    re.compile(r"recib[ií]\s+(?:mi\s+)?(?:sueldo|pago|ingreso)", re.IGNORECASE),
    re.compile(r"me\s+pagaron", re.IGNORECASE),
    re.compile(r"me\s+va\s+a\s+pagar", re.IGNORECASE),
]


def classify_intent(text: str) -> str:
    text = text.strip()

    if any(p.match(text) for p in SALUDO_PATTERNS):
        return "saludo"
    if any(p.match(text) for p in DESPEDIDA_PATTERNS):
        return "despedida"
    if any(p.search(text) for p in GASTO_PATTERNS):
        return "gasto"
    if any(p.search(text) for p in SUENO_PATTERNS):
        return "sueno"
    if any(p.search(text) for p in CHECKIN_PATTERNS):
        return "checkin"
    if any(p.match(text) for p in CONFIRMACION_PATTERNS):
        return "confirmacion"
    if any(p.search(text) for p in EVENTO_CREAR_PATTERNS):
        return "evento_crear"
    if any(p.search(text) for p in EVENTO_COMPLETAR_PATTERNS):
        return "evento_completar"
    if any(p.search(text) for p in EVENTO_VER_PATTERNS):
        return "evento_ver"
    if any(p.search(text) for p in PREGUNTA_PROGRAMADA_PATTERNS):
        return "pregunta_programada"
    if any(p.search(text) for p in RUTINA_CREAR_PATTERNS):
        return "rutina_crear"
    if any(p.search(text) for p in DEUDA_REGISTRAR_PATTERNS):
        return "deuda_registrar"
    if any(p.search(text) for p in DEUDA_PAGAR_PATTERNS):
        return "deuda_pagar"
    if any(p.search(text) for p in SUELDO_REGISTRAR_PATTERNS):
        return "sueldo_registrar"

    question_words = ["cómo", "qué", "cuándo", "dónde", "por qué", "para qué", "cuánto", "cuál"]
    if any(text.lower().startswith(w) for w in question_words):
        return "pregunta"

    return "unknown"


async def classify_intent_with_minimax(api_key: str, text: str) -> tuple[str, str]:
    """
    Cuando classify_intent devuelve 'unknown', usamos MiniMax para analisar
    el mensaje y determinar qué quiere el usuario.
    
    Returns:
        tuple: (intent, action_description)
            intent puede ser: evento_crear, evento_ver, gasto, sueno, checkin, 
                              despedida, pregunta, oracion_general
            action_description es una descripción corta de lo que el usuario quiere hacer
    """
    system_prompt = """Sos MindFlow, un clasificador de intenciones para un asistente personal.
    Tu trabajo es analizar el mensaje del usuario y determinar qué quiere.

    Devolvé en formato JSON simple (sin markdown, sin asteriscos):
    {
      "intent": "evento_crear|evento_ver|evento_completar|gasto|sueno|checkin|rutina|despedida|pregunta|coach|motivacion|pregunta_programada|rutina_crear|oracion_general",
      "descripcion": "breve descripción de lo que quiere el usuario (máx 10 palabras)"
    }

    Reglas:
    - Si quiere agregar/crear un evento, cita, reunión o recordatorio: "evento_crear"
    - Si quiere ver sus eventos, compromisos o agenda: "evento_ver"
    - Si quiere marcar algo como hecho o completado: "evento_completar"
    - Si menciona dinero/gasto/pagó/compró: "gasto"
    - Si menciona acostarse/levantarse/durmió/energía/sueño: "sueno"
    - Si menciona distracción, estaba en redes, no estaba estudiando: "checkin"
    - Si quiere agregar una rutina o bloque de tiempo: "rutina_crear"
    - Si dice chau/adiós/hasta luego: "despedida"
    - Si hace una pregunta general: "pregunta"
    - Si pide motivación, empujón, está decaído: "coach"
    - Si quiere que el asistente le pregunte algo a cierta hora: "pregunta_programada"
    - Si quiere programarrecordatorios de rutina: "rutina_crear"
    - En cualquier otro caso: "oracion_general"
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.minimax.io/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "MiniMax-M2.1",
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 256
            },
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
    
    raw_content = data["choices"][0]["message"]["content"]
    
    # Parsear el JSON
    import json
    import re
    
    # Buscar JSON en el content
    json_match = re.search(r'\{[^}]+\}', raw_content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return parsed.get("intent", "oracion_general"), parsed.get("descripcion", "")
        except:
            pass
    
    # Si no pudo parsear, default
    return "oracion_general", raw_content[:50]
