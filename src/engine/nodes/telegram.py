from .base import BaseNode

NODE_CONFIG = {
    "type": "telegram.send",
    "name": "Telegram Send",
    "category": "action",
    "description": "Envía un mensaje por Telegram",
    "config_schema": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["message"]
    },
    "handler": "TelegramNode"
}


class TelegramNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        from telegram import Bot

        token = context.get("secrets", {}).get("TELEGRAM_BOT_TOKEN")
        chat_id = self.resolve_template(self.config.get("chat_id", ""), context)
        message = self.resolve_template(self.config.get("message"), context)

        bot = Bot(token=token)
        sent = await bot.send_message(chat_id=chat_id, text=message)

        return {
            "message_id": sent.message_id,
            "chat_id": chat_id,
            "text": message
        }
