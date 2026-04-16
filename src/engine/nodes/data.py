from .base import BaseNode

NODE_CONFIG_GET = {
    "type": "data.get",
    "name": "Get Flow Data",
    "category": "utility",
    "description": "Obtiene un valor del almacenamiento del flow",
    "config_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string"}
        },
        "required": ["key"]
    },
    "handler": "DataGetNode"
}

NODE_CONFIG_SET = {
    "type": "data.set",
    "name": "Set Flow Data",
    "category": "utility",
    "description": "Guarda un valor en el almacenamiento del flow",
    "config_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "value": {"type": "string"}
        },
        "required": ["key", "value"]
    },
    "handler": "DataSetNode"
}


class DataGetNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        key = self.config.get("key")
        flow_data = context.get("flow_data", {})

        return {
            "key": key,
            "value": flow_data.get(key)
        }


class DataSetNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        key = self.config.get("key")
        value = self.resolve_template(self.config.get("value"), context)

        if "flow_data" not in context:
            context["flow_data"] = {}
        context["flow_data"][key] = value

        return {
            "key": key,
            "value": value
        }
