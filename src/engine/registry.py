from typing import Type
from .nodes.base import BaseNode
from .nodes import (
    LogNode, LOG_CONFIG,
    HttpNode, HTTP_CONFIG,
    AiNode, AI_CONFIG,
    TelegramNode, TELEGRAM_CONFIG,
    LogicIfNode, NODE_CONFIG_IF,
    LogicWhileNode, NODE_CONFIG_WHILE,
    DataGetNode, NODE_CONFIG_GET,
    DataSetNode, NODE_CONFIG_SET,
    MinimaxChatNode, MINIMAX_CHAT_CONFIG,
    MinimaxTTSNode, MINIMAX_TTS_CONFIG,
    MinimaxImageNode, MINIMAX_IMAGE_CONFIG,
    MinimaxMusicNode, MINIMAX_MUSIC_CONFIG,
    MinimaxVisionNode, MINIMAX_VISION_CONFIG,
    MinimaxUsageNode, MINIMAX_USAGE_CONFIG,
)


class NodeRegistry:
    _handlers: dict[str, Type[BaseNode]] = {}
    _metadata: dict[str, dict] = {}

    @classmethod
    def register(cls, metadata: dict, handler: Type[BaseNode]):
        node_type = metadata["type"]
        cls._handlers[node_type] = handler
        cls._metadata[node_type] = metadata

    @classmethod
    def get_handler(cls, node_type: str) -> Type[BaseNode]:
        if node_type not in cls._handlers:
            raise ValueError(f"Nodo desconocido: {node_type}")
        return cls._handlers[node_type]

    @classmethod
    def get_metadata(cls, node_type: str) -> dict:
        if node_type not in cls._metadata:
            raise ValueError(f"Metadata de nodo no encontrada: {node_type}")
        return cls._metadata[node_type]

    @classmethod
    def list_nodes(cls) -> dict[str, dict]:
        return cls._metadata.copy()

    @classmethod
    def initialize(cls):
        cls.register(LOG_CONFIG, LogNode)
        cls.register(HTTP_CONFIG, HttpNode)
        cls.register(AI_CONFIG, AiNode)
        cls.register(TELEGRAM_CONFIG, TelegramNode)
        cls.register(NODE_CONFIG_IF, LogicIfNode)
        cls.register(NODE_CONFIG_WHILE, LogicWhileNode)
        cls.register(NODE_CONFIG_GET, DataGetNode)
        cls.register(NODE_CONFIG_SET, DataSetNode)
        cls.register(MINIMAX_CHAT_CONFIG, MinimaxChatNode)
        cls.register(MINIMAX_TTS_CONFIG, MinimaxTTSNode)
        cls.register(MINIMAX_IMAGE_CONFIG, MinimaxImageNode)
        cls.register(MINIMAX_MUSIC_CONFIG, MinimaxMusicNode)
        cls.register(MINIMAX_VISION_CONFIG, MinimaxVisionNode)
        cls.register(MINIMAX_USAGE_CONFIG, MinimaxUsageNode)


NodeRegistry.initialize()
