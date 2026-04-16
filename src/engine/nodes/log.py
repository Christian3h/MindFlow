from .base import BaseNode


class LogNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        message = self.config.get("message", "")
        resolved = self.resolve_template(message, context)

        log_entry = {
            "node_id": self.node_id,
            "type": "log",
            "message": resolved,
        }

        print(f"[LOG] {resolved}")

        return log_entry


NODE_CONFIG = {
    "type": "log",
    "name": "Debug Log",
    "category": "utility",
    "description": "Imprime un mensaje durante la ejecución",
    "config_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Mensaje a loguear. Soporta templates: {{ node_id.field }} o {{ secrets.KEY }}"
            }
        },
        "required": ["message"]
    },
    "handler": "LogNode"
}
