import json
from typing import Optional
from uuid import uuid4
from datetime import datetime

from .context import ExecutionContext
from .registry import NodeRegistry


class FlowExecutor:
    def __init__(self, session=None):
        self.session = session

    async def execute_flow(
        self,
        flow_id: str,
        flow_data: dict,
        secrets: dict[str, str]
    ) -> dict:
        context = ExecutionContext(flow_id)
        context.secrets = secrets

        nodes_config = json.loads(flow_data["nodes"])
        execution_id = context.execution_id

        if self.session:
            await self._save_execution(
                execution_id=execution_id,
                flow_id=flow_id,
                status="running",
                context=context
            )

        try:
            next_node_id = nodes_config[0]["id"] if nodes_config else None

            while next_node_id:
                node_config = self._find_node(nodes_config, next_node_id)
                if not node_config:
                    raise ValueError(f"Nodo no encontrado: {next_node_id}")

                context.current_node = next_node_id

                node_type = node_config["type"]
                node_class = NodeRegistry.get_handler(node_type)
                node_instance = node_class(next_node_id, node_config.get("config", {}))

                result = await node_instance.execute(context.to_dict())

                context.set_node_output(next_node_id, result)

                if node_type == "logic.if":
                    next_node_id = result.get("next_node")
                elif node_type == "logic.while":
                    next_node_id = nodes_config[nodes_config.index(node_config) + 1]["id"] if nodes_config.index(node_config) + 1 < len(nodes_config) else None
                else:
                    next_node_id = self._get_next_node(nodes_config, next_node_id)

            status = "success"

        except Exception as e:
            status = "failed"
            context.nodes[context.current_node] = {"error": str(e)}

        if self.session:
            await self._save_execution(
                execution_id=execution_id,
                flow_id=flow_id,
                status=status,
                context=context,
                error=str(e) if status == "failed" else None
            )

        return {
            "execution_id": execution_id,
            "status": status,
            "context": context.nodes,
            "error": str(e) if status == "failed" else None
        }

    def _find_node(self, nodes: list, node_id: str) -> Optional[dict]:
        for node in nodes:
            if node["id"] == node_id:
                return node
        return None

    def _get_next_node(self, nodes: list, current_id: str) -> Optional[str]:
        for i, node in enumerate(nodes):
            if node["id"] == current_id:
                if i + 1 < len(nodes):
                    return nodes[i + 1]["id"]
                return None
        return None

    async def _save_execution(
        self,
        execution_id: str,
        flow_id: str,
        status: str,
        context: ExecutionContext,
        error: Optional[str] = None
    ):
        if not self.session:
            return

        from src.models import Execution

        finished_at = datetime.utcnow().isoformat() if status in ("success", "failed") else None

        execution = Execution(
            id=execution_id,
            flow_id=flow_id,
            status=status,
            started_at=context.started_at,
            finished_at=finished_at,
            error=error,
            context=json.dumps(context.nodes)
        )

        await self.session.merge(execution)
        await self.session.flush()
