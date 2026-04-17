import re
from dataclasses import dataclass
from typing import Optional


CATEGORIES = {
    "alimentación": ["almuerzo", "cena", "desayuno", "snacks", "comida", "restaurante", "domicilio", "empanadas", "pizza", "hamburguesa"],
    "transporte": ["taxi", "uber", "bus", "gasolina", "metro", "transporte", "moto", "bicicleta", "parqueo", "peaje"],
    "ocio": ["cine", "streaming", "juegos", "libros", "netflix", "spotify", "playstation", "steam", "videojuegos"],
    "salud": ["farmacia", "doctor", "gym", "medicamentos", "medicina", "consulta", "terapia", "vitaminas"],
    "servicios": ["internet", "celular", "suscripciones", "netflix", "spotify", "amazon", "icloud", "dropbox", "github"],
    "entretenimiento": ["conciertos", "eventos", "salida", "fiesta", "bar", "discoteca", "teatro", "muséo"],
}


@dataclass
class ParsedExpense:
    monto: float
    categoria: str
    subcategoria: Optional[str] = None
    descripcion: Optional[str] = None
    fue_impulsivo: Optional[bool] = None
    metodo_pago: Optional[str] = None


def parse_monto(amount_str: str) -> float:
    amount_str = amount_str.lower().replace("$", "").replace(".", "").replace(",", "").strip()
    
    if "mil" in amount_str:
        match = re.search(r"([\d.]+)\s*mil", amount_str)
        if match:
            return float(match.group(1)) * 1000
    elif "k" in amount_str:
        match = re.search(r"([\d.]+)\s*k", amount_str)
        if match:
            return float(match.group(1)) * 1000
    
    match = re.search(r"([\d.]+)", amount_str)
    if match:
        return float(match.group(1))
    
    return 0.0


def detect_payment_method(text: str) -> str | None:
    text_lower = text.lower()
    if any(p in text_lower for p in ["efectivo", "cash", "billetes"]):
        return "efectivo"
    elif any(p in text_lower for p in ["tarjeta", "credito", "débito", "debito"]):
        return "tarjeta"
    elif any(p in text_lower for p in ["transferencia", "transfer", "banco"]):
        return "transferencia"
    elif any(p in text_lower for p in ["nequi", "daviplata", "nequi"]):
        return "nequi"
    return None


def categorize_expense(text: str) -> tuple[str, str | None]:
    text_lower = text.lower()
    
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category, keyword
    
    return "otros", None


def parse_single_expense(text: str) -> ParsedExpense | None:
    text_lower = text.lower().strip()
    
    has_mil = "mil" in text_lower
    number_match = re.search(r'([\d.,]+)\s*(?:mil)?', text_lower)
    
    if not number_match:
        return None
    
    monto = parse_monto(number_match.group(1) + (" mil" if has_mil else ""))
    if monto <= 0:
        return None
    
    descripcion = re.sub(r'(?:gast[eé]|pag[u]?[ée]|compr[eé])\s*[\d.,]+\s*(?:mil)?\s*(?:en\s+)?', '', text_lower, flags=re.IGNORECASE)
    descripcion = re.sub(r'\s+y\s+(?:gast[eé]|pag[u]?[ée]|compr[eé])\s+[\d.,]+\s*(?:mil)?.*', '', descripcion, flags=re.IGNORECASE)
    descripcion = re.sub(r'^(?:gast[eé]|pag[u]?[ée]|compr[eé])\s+', '', descripcion, flags=re.IGNORECASE)
    descripcion = re.sub(r'^[\d.,]+\s*(?:mil)?\s*(?:en\s+)?', '', descripcion)
    descripcion = descripcion.strip()
    
    if not descripcion:
        return None
    
    categoria, subcategoria = categorize_expense(descripcion)
    metodo_pago = detect_payment_method(text)
    
    return ParsedExpense(
        monto=monto,
        categoria=categoria,
        subcategoria=subcategoria,
        descripcion=descripcion,
        metodo_pago=metodo_pago
    )


def parse_multiple_expenses(text: str) -> list[ParsedExpense]:
    text = text.strip()
    
    parts = re.split(r'\s+y\s+', text)
    
    expenses = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        expense = parse_single_expense(part)
        if expense and expense.monto > 0:
            expenses.append(expense)
    
    if not expenses:
        expense = parse_single_expense(text)
        if expense and expense.monto > 0:
            expenses.append(expense)
    
    return expenses


def format_expenses_response(expenses: list[ParsedExpense], total_hoy: float | None = None) -> str:
    lines = ["Listo. Gastos registrados:"]
    
    for exp in expenses:
        lines.append(f"  - {exp.descripcion.title()}: ${exp.monto:,.0f} ({exp.categoria})")
    
    if total_hoy is not None:
        lines.append(f"Total hoy: ${total_hoy:,.0f}")
    
    lines.append("¿Algo más?")
    return "\n".join(lines)


IMPULSIVE_THRESHOLD = 50000


def should_ask_impulsive(expenses: list[ParsedExpense]) -> bool:
    return any(exp.monto >= IMPULSIVE_THRESHOLD for exp in expenses)


def needs_confirmation(text: str) -> bool:
    text_lower = text.lower()
    confirmation_words = ["sí", "si", "yea", "yep", "claro", "dale", "ok", "bueno", "va", "perfect", "afirmativo", "confirmar", "si fue", "sí fue"]
    denial_words = ["no", "nope", "nah", "no fue", "nah", "no importar", "nada", "salir", "listo"]
    
    if any(text_lower.strip().startswith(w) for w in confirmation_words):
        return True
    return False