from pydantic import BaseModel
from typing import Optional


class FlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: Optional[str] = "manual"
    trigger_config: Optional[dict] = None
    nodes: list[dict]


class FlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    nodes: Optional[list[dict]] = None


class FlowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    enabled: bool
    trigger_type: Optional[str]
    trigger_config: Optional[dict]
    nodes: list[dict]
    created_at: str
    updated_at: str


class SecretCreate(BaseModel):
    key: str
    value: str


class SecretResponse(BaseModel):
    key: str
    created_at: str


class ExecutionResponse(BaseModel):
    id: str
    flow_id: str
    status: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error: Optional[str]
    context: Optional[dict]


class ExecutionUpdate(BaseModel):
    status: str
    error: Optional[str] = None
    finished_at: Optional[str] = None


class NodeInfo(BaseModel):
    type: str
    name: str
    category: str
    description: str
    config_schema: dict
