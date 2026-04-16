from .base import BaseNode
import re


NODE_CONFIG_IF = {
    "type": "logic.if",
    "name": "Conditional Branch",
    "category": "control",
    "description": "Evalúa una condición y redirige el flujo",
    "config_schema": {
        "type": "object",
        "properties": {
            "condition": {"type": "string"},
            "then": {"type": "string"},
            "else": {"type": "string"}
        },
        "required": ["condition", "then"]
    },
    "handler": "LogicIfNode"
}

NODE_CONFIG_WHILE = {
    "type": "logic.while",
    "name": "While Loop",
    "category": "control",
    "description": "Repite nodos mientras una condición sea verdadera",
    "config_schema": {
        "type": "object",
        "properties": {
            "condition": {"type": "string"},
            "max_iterations": {"type": "integer", "default": 100},
            "nodes": {"type": "array"}
        },
        "required": ["condition"]
    },
    "handler": "LogicWhileNode"
}


def safe_eval_condition(condition: str, context: dict) -> bool:
    def get_value(path: str):
        path = path.strip()
        if path.startswith("node."):
            parts = path.replace("node.", "").split(".")
            node_id = parts[0]
            attr = parts[1] if len(parts) > 1 else "result"
            return context.get("nodes", {}).get(node_id, {}).get(attr, None)
        if path.startswith("secrets."):
            key = path.split(".")[1]
            return context.get("secrets", {}).get(key)
        return path

    resolved = re.sub(r"\{\{([^}]+)\}\}", lambda m: repr(get_value(m.group(1))), condition)

    allowed_names = {"True": True, "False": False, "None": None, "and": lambda a, b: a and b, "or": lambda a, b: a or b, "not": lambda x: not x, "in": lambda a, b: a in b, "not in": lambda a, b: a not in b}
    
    for op in ["==", "!=", "<=", ">=", "<", ">", "+", "-", "*", "/", "(", ")"]:
        resolved = resolved.replace(op, f" {op} ")

    tokens = resolved.split()
    safe_tokens = []
    for token in tokens:
        token = token.strip()
        if token in allowed_names:
            safe_tokens.append(repr(allowed_names[token]))
        elif token in ("and", "or", "not", "==", "!=", "<=", ">=", "<", ">", "in", "not", "(", ")"):
            safe_tokens.append(token)
        elif token.replace(".", "").replace("-", "").isdigit():
            safe_tokens.append(token)
        elif token.startswith('"') and token.endswith('"'):
            safe_tokens.append(token)
        elif token.startswith("'") and token.endswith("'"):
            safe_tokens.append(token)
        else:
            safe_tokens.append("None")

    safe_expr = " ".join(safe_tokens)
    safe_expr = safe_expr.replace("( True )", "(True)").replace("( False )", "(False)").replace("and True", "and True").replace("or True", "or True")

    try:
        result = eval(safe_expr, {"__builtins__": {}}, allowed_names)
        return bool(result)
    except Exception:
        return False


class LogicIfNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        condition = self.config.get("condition", "")

        result = safe_eval_condition(condition, context)

        return {
            "condition_result": result,
            "next_node": self.config.get("then") if result else self.config.get("else")
        }


class LogicWhileNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        max_iterations = self.config.get("max_iterations", 100)
        iterations = 0
        results = []

        while iterations < max_iterations:
            condition = self.config.get("condition", "")

            if not safe_eval_condition(condition, context):
                break

            iterations += 1
            results.append({"iteration": iterations})

        return {
            "iterations": iterations,
            "results": results
        }
