from .base import BaseNode

NODE_CONFIG = {
    "type": "ai.complete",
    "name": "AI Complete",
    "category": "action",
    "description": "Genera una respuesta usando OpenAI",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "gpt-4o-mini"},
            "prompt": {"type": "string"}
        },
        "required": ["prompt"]
    },
    "handler": "AiNode"
}


class AiNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        from openai import OpenAI

        api_key = context.get("secrets", {}).get("OPENAI_API_KEY")
        model = self.config.get("model", "gpt-4o-mini")
        prompt = self.resolve_template(self.config.get("prompt"), context)

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            "result": response.choices[0].message.content
        }
