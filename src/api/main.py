from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.models import init_db
from src.api.routes import flows_router, secrets_router, executions_router, nodes_router
from src.api.routes.assistant import router as assistant_router
from src.engine import start_scheduler, stop_scheduler
from src.assistant.db import init_db as init_assistant_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Base de datos engine inicializada")
    await init_assistant_db()
    print("Base de datos assistant inicializada")
    await start_scheduler()
    yield
    await stop_scheduler()
    print("Apagando...")


app = FastAPI(
    title="MindFlow",
    description="Workflow engine con nodos reutilizables",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(flows_router)
app.include_router(secrets_router)
app.include_router(executions_router)
app.include_router(nodes_router)
app.include_router(assistant_router)


@app.get("/")
async def root():
    return {"message": "MindFlow API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
