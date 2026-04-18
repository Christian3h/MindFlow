import re
from dataclasses import dataclass
from typing import Optional


SALARIO_KEYWORDS = ["sueldo", "salario", "honorarios", "pago", "ingreso", "ganancia", "renta", "brazo"]
FUENTES_COMUNES = ["trabajo", "freelance", "consultoria", "negocio", "inversion", "dividendos", "arrendamiento"]


@dataclass
class ParsedIncome:
    monto: float
    fuente: Optional[str] = None
    es_sueldo: bool = False
    notas: Optional[str] = None


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


def detect_fuente(text: str) -> str | None:
    text_lower = text.lower()
    for fuente in FUENTES_COMUNES:
        if fuente in text_lower:
            return fuente.title()
    return None


def is_sueldo(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in SALARIO_KEYWORDS)


def parse_income(text: str) -> ParsedIncome | None:
    text_lower = text.lower().strip()
    
    patterns = [
        r"gan[éeé]\s*([\d.,]+\s*(?:mil)?)",
        r"recib[ií]\s*([\d.,]+\s*(?:mil)?)",
        r"tengo\s*([\d.,]+\s*(?:mil)?)\s*(?:de\s+)?(?:sueldo|ingreso)",
        r"(?:sueldo|salario)\s*de\s*([\d.,]+\s*(?:mil)?)",
        r"mi\s*(?:sueldo|salario)\s*(?:es|de)?\s*([\d.,]+\s*(?:mil)?)",
        r"ingres[oó]\s*(?:de|es)?\s*([\d.,]+\s*(?:mil)?)",
        r"pagaron\s*([\d.,]+\s*(?:mil)?)",
        r"me\s*pagaron\s*([\d.,]+\s*(?:mil)?)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            monto = parse_monto(match.group(1))
            if monto > 0:
                fuente = detect_fuente(text)
                return ParsedIncome(
                    monto=monto,
                    fuente=fuente,
                    es_sueldo=is_sueldo(text)
                )
    
    monto_match = re.search(r"([\d.,]+)\s*(?:mil)?", text_lower)
    if monto_match:
        monto = parse_monto(monto_match.group())
        if monto >= 500000:
            return ParsedIncome(
                monto=monto,
                fuente=detect_fuente(text),
                es_sueldo=is_sueldo(text)
            )
    
    return None


def format_income_response(income: ParsedIncome) -> str:
    lines = [f"Ingreso registrado: ${income.monto:,.0f}"]
    
    if income.fuente:
        lines.append(f"Fuente: {income.fuente}")
    elif income.es_sueldo:
        lines.append("Fuente: Sueldo")
    
    return "\n".join(lines)


def needs_presupuesto_pregunta(income: ParsedIncome) -> bool:
    return income.monto >= 1000000