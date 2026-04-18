import re
from dataclasses import dataclass
from typing import Optional


BANCO_PATTERNS = [
    "bancolombia", "davivienda", "bogota", "bbva", "banco de bogota",
    "nequi", "daviplata", "movii", "avia", "contra entrega"
]

CUOTA_PATTERNS = [
    "cuota", "mensualidad", "pago mensual", "abono"
]


@dataclass
class ParsedDebt:
    entidad: str
    monto_original: float
    monto_actual: Optional[float] = None
    cuota_valor: Optional[float] = None
    cuotas_totales: Optional[int] = None
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


def detect_banco(text: str) -> str | None:
    text_lower = text.lower()
    for banco in BANCO_PATTERNS:
        if banco in text_lower:
            return banco.title()
    return None


def detect_cuota(text: str) -> tuple[float | None, int | None]:
    text_lower = text.lower()
    
    cuota_match = re.search(r"cuota[s]?\s*(?:de\s*)?([\d.,]+\s*(?:mil)?)", text_lower)
    if cuota_match:
        valor_cuota = parse_monto(cuota_match.group(1))
    else:
        valor_cuota = None
    
    total_match = re.search(r"(\d+)\s*cuota[s]?", text_lower)
    if total_match:
        num_cuotas = int(total_match.group(1))
    else:
        num_cuotas = None
    
    return valor_cuota, num_cuotas


def parse_debt_creation(text: str) -> ParsedDebt | None:
    text_lower = text.lower().strip()
    
    monto_match = re.search(r"([\d.,]+)\s*(?:mil)?", text_lower)
    if not monto_match:
        return None
    
    monto = parse_monto(monto_match.group())
    if monto <= 0:
        return None
    
    entidad = detect_banco(text) or "Otra"
    
    valor_cuota, num_cuotas = detect_cuota(text)
    
    return ParsedDebt(
        entidad=entidad,
        monto_original=monto,
        monto_actual=monto,
        cuota_valor=valor_cuota,
        cuotas_totales=num_cuotas
    )


def parse_debt_payment(text: str) -> float | None:
    text_lower = text.lower().strip()
    
    monto_match = re.search(r"([\d.,]+)\s*(?:mil)?", text_lower)
    if not monto_match:
        return None
    
    monto = parse_monto(monto_match.group())
    if monto <= 0:
        return None
    
    return monto


def format_debt_response(debt: ParsedDebt) -> str:
    lines = [f"Deuda registrada en {debt.entidad}:"]
    lines.append(f"  - Monto original: ${debt.monto_original:,.0f}")
    
    if debt.cuota_valor:
        lines.append(f"  - Valor cuota: ${debt.cuota_valor:,.0f}")
    if debt.cuotas_totales:
        lines.append(f"  - Número de cuotas: {debt.cuotas_totales}")
    
    return "\n".join(lines)


def needs_cuota_confirmation(debt: ParsedDebt) -> bool:
    return debt.cuota_valor is None and debt.monto_original >= 100000