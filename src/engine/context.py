from typing import Any, Optional
from uuid import uuid4
from datetime import datetime


class ExecutionContext:
    def __init__(self, flow_id: str):
        self.flow_id = flow_id
        self.nodes: dict[str, Any] = {}
        self.flow_data: dict[str, Any] = {}
        self.secrets: dict[str, str] = {}
        self.current_node: Optional[str] = None
        self.execution_id: str = str(uuid4())
        self.started_at: str = datetime.utcnow().isoformat()

    def set_node_output(self, node_id: str, output: Any):
        self.nodes[node_id] = output

    def get_node_output(self, node_id: str) -> Optional[Any]:
        return self.nodes.get(node_id)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "flow_id": self.flow_id,
            "started_at": self.started_at,
            "nodes": self.nodes,
            "flow_data": self.flow_data,
            "secrets": self.secrets
        }
