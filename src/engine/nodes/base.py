from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseNode(ABC):
    def __init__(self, node_id: str, config: dict):
        self.node_id = node_id
        self.config = config

    @abstractmethod
    async def execute(self, context: dict) -> Any:
        pass

    def resolve_template(self, template: Optional[str], context: dict) -> Any:
        if template is None:
            return None

        import re

        def replacer(match):
            path = match.group(1).strip()
            parts = path.split(".")

            if path.startswith("secrets."):
                key = parts[1]
                return context.get("secrets", {}).get(key, match.group(0))

            if path.startswith("node."):
                parts = parts[1:]

            node_id = parts[0]
            attr = parts[1] if len(parts) > 1 else "result"

            node_output = context.get("nodes", {}).get(node_id, {})
            return node_output.get(attr, match.group(0))

        return re.sub(r"\{\{([^}]+)\}\}", replacer, template)
