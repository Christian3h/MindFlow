from .base import BaseNode

DEFAULT_MODEL = "MiniMax-M2.7"

MINIMAX_CHAT_CONFIG = {
    "type": "minimax.chat",
    "name": "MiniMax Chat",
    "category": "action",
    "description": "Genera respuestas de texto usando MiniMax M2.7",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "MiniMax-M2.7"},
            "messages": {"type": "array", "description": "Array de mensajes [{role, content}]"},
            "system": {"type": "string", "description": "Prompt del sistema"},
            "temperature": {"type": "number", "default": 0.7},
            "max_tokens": {"type": "integer", "default": 2048},
            "stream": {"type": "boolean", "default": False}
        },
        "required": ["messages"]
    },
    "handler": "MinimaxChatNode"
}


class MinimaxChatNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        model = self.config.get("model", DEFAULT_MODEL)
        system_prompt = self.config.get("system", "")
        temperature = self.config.get("temperature", 0.7)
        max_tokens = self.config.get("max_tokens", 2048)
        stream = self.config.get("stream", False)

        messages_config = self.config.get("messages", [])
        resolved_messages = []
        for msg in messages_config:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                resolved_content = self.resolve_template(content, context)
            else:
                resolved_content = content
            resolved_messages.append({"role": role, "content": resolved_content})

        if system_prompt:
            resolved_system = self.resolve_template(system_prompt, context)
            resolved_messages.insert(0, {"role": "system", "content": resolved_system})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.io/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": resolved_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": model
        }


MINIMAX_TTS_CONFIG = {
    "type": "minimax.tts",
    "name": "MiniMax TTS",
    "category": "action",
    "description": "Síntesis de voz (texto a audio) con MiniMax",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "speech-2.8-hd"},
            "text": {"type": "string"},
            "voice_id": {"type": "string", "default": "English_expressive_narrator"},
            "speed": {"type": "number", "default": 1.0},
            "emotion": {"type": "string", "default": "happy"},
            "output_format": {"type": "string", "default": "hex"}
        },
        "required": ["text"]
    },
    "handler": "MinimaxTTSNode"
}


class MinimaxTTSNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        model = self.config.get("model", "speech-2.8-hd")
        text = self.resolve_template(self.config.get("text"), context)
        voice_id = self.config.get("voice_id", "English_expressive_narrator")
        speed = self.config.get("speed", 1.0)
        emotion = self.config.get("emotion", "happy")
        output_format = self.config.get("output_format", "hex")

        payload = {
            "model": model,
            "text": text,
            "stream": False,
            "output_format": output_format,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "emotion": emotion
            },
            "audio_setting": {
                "format": "mp3",
                "sample_rate": 32000,
                "bitrate": 128000
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.io/v1/t2a_v2",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

        audio_content = data.get("data", {}).get("audio", "")
        return {
            "audio": audio_content,
            "format": data.get("extra_info", {}).get("audio_format", "mp3"),
            "model": model,
            "text": text,
            "extra_info": data.get("extra_info", {})
        }


MINIMAX_IMAGE_CONFIG = {
    "type": "minimax.image",
    "name": "MiniMax Image",
    "category": "action",
    "description": "Genera imágenes con MiniMax image-01",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "image-01"},
            "prompt": {"type": "string"},
            "aspect_ratio": {"type": "string", "default": "1:1"},
            "response_format": {"type": "string", "default": "url"},
            "n": {"type": "integer", "default": 1}
        },
        "required": ["prompt"]
    },
    "handler": "MinimaxImageNode"
}


class MinimaxImageNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        model = self.config.get("model", "image-01")
        prompt = self.resolve_template(self.config.get("prompt"), context)
        aspect_ratio = self.config.get("aspect_ratio", "1:1")
        response_format = self.config.get("response_format", "url")
        n = self.config.get("n", 1)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.io/v1/image_generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "response_format": response_format,
                    "n": n
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()

        items = data.get("data", {}).get("items", [])
        images = [{"url": item.get("url"), "base64": item.get("base64")} for item in items]

        return {
            "images": images,
            "model": model,
            "prompt": prompt
        }


MINIMAX_MUSIC_CONFIG = {
    "type": "minimax.music",
    "name": "MiniMax Music",
    "category": "action",
    "description": "Genera música con MiniMax music-2.6",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "music-2.6"},
            "prompt": {"type": "string"},
            "lyrics": {"type": "string"},
            "is_instrumental": {"type": "boolean", "default": False},
            "output_format": {"type": "string", "default": "hex"}
        },
        "required": ["prompt"]
    },
    "handler": "MinimaxMusicNode"
}


class MinimaxMusicNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        model = self.config.get("model", "music-2.6")
        prompt = self.resolve_template(self.config.get("prompt"), context)
        lyrics = self.resolve_template(self.config.get("lyrics"), context)
        is_instrumental = self.config.get("is_instrumental", False)
        output_format = self.config.get("output_format", "hex")

        payload = {
            "model": model,
            "prompt": prompt,
            "output_format": output_format,
            "is_instrumental": is_instrumental
        }
        if lyrics:
            payload["lyrics"] = lyrics

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.io/v1/music_generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()

        music_data = data.get("data", {})
        return {
            "audio": music_data.get("audio", ""),
            "status": music_data.get("status"),
            "model": model,
            "extra_info": data.get("extra_info", {})
        }


MINIMAX_VISION_CONFIG = {
    "type": "minimax.vision",
    "name": "MiniMax Vision",
    "category": "action",
    "description": "Análisis de imágenes con MiniMax (multimodal)",
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "MiniMax-M2.7"},
            "messages": {"type": "array", "description": "Array de mensajes con contenido multimodal"}
        },
        "required": ["messages"]
    },
    "handler": "MinimaxVisionNode"
}


class MinimaxVisionNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        import httpx

        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        model = self.config.get("model", "MiniMax-M2.7")
        messages_config = self.config.get("messages", [])

        resolved_messages = []
        for msg in messages_config:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                resolved_content = []
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "text")
                        if item_type == "text":
                            text = item.get("text", "")
                            resolved_content.append({
                                "type": "text",
                                "text": self.resolve_template(text, context)
                            })
                        elif item_type == "image_url":
                            resolved_content.append(item)
                    else:
                        resolved_content.append(item)
            else:
                resolved_content = self.resolve_template(content, context)

            resolved_messages.append({"role": role, "content": resolved_content})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.minimax.io/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": resolved_messages
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": model
        }


MINIMAX_USAGE_CONFIG = {
    "type": "minimax.usage",
    "name": "MiniMax Usage",
    "category": "action",
    "description": "Consulta el uso remaining de Token Plan",
    "config_schema": {
        "type": "object",
        "properties": {},
        "required": []
    },
    "handler": "MinimaxUsageNode"
}


class MinimaxUsageNode(BaseNode):
    async def execute(self, context: dict) -> dict:
        api_key = context.get("secrets", {}).get("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not found in secrets")

        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.minimax.io/v1/api/openplatform/coding_plan/remains",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        return {
            "usage": data,
            "raw": data
        }