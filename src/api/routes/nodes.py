from fastapi import APIRouter

from src.engine import NodeRegistry
from src.api.schemas import NodeInfo

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeInfo])
async def list_nodes():
    nodes = NodeRegistry.list_nodes()

    return [
        NodeInfo(
            type=n["type"],
            name=n["name"],
            category=n["category"],
            description=n["description"],
            config_schema=json.loads(n["config_schema"]) if isinstance(n["config_schema"], str) else n["config_schema"],
        )
        for n in nodes.values()
    ]


import json
