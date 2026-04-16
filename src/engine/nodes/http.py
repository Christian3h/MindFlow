from .base import BaseNode

NODE_CONFIG = {
    "type": "http.request",
    "name": "HTTP Request",
    "category": "action",
    "description": "Realiza una petición HTTP",
    "config_schema": {
        "type": "object",
        "properties": {
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "body": {"type": "string"}
        },
        "required": ["method", "url"]
    },
    "handler": "HttpNode"
}


class HttpNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        method = self.resolve_template(self.config.get("method", "GET"), context)
        url = self.resolve_template(self.config.get("url"), context)
        headers = self.config.get("headers", {})
        body = self.resolve_template(self.config.get("body", ""), context)

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method, url, headers=headers, json=body if body else None
            )

        return {
            "status": response.status_code,
            "body": response.text,
            "headers": dict(response.headers)
        }
