"""FastAPI app for Chief of Staff API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chief_router import router as chief_router, set_chief_instance
from agents.chief import ChiefOfStaff, create_chief_of_staff
from agents.guardian import GuardianAgent
from orchestration.event_bus import EventBus
from knowledge_graph.client import KnowledgeGraph


chief_instance: ChiefOfStaff | None = None
guardian_instance: GuardianAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global chief_instance, guardian_instance
    # Initialize components
    kg = KnowledgeGraph("./data/knowledge_graph/api_kuzu.db")
    kg._init_schema()
    eb = EventBus(enabled=False)
    guardian = GuardianAgent()
    chief = create_chief_of_staff(
        kg=kg,
        event_bus=eb,
        guardian=guardian,
    )
    chief.start()
    set_chief_instance(chief, guardian)
    chief_instance = chief
    guardian_instance = guardian
    yield
    chief.stop()
    kg.close()


app = FastAPI(
    title="NEXUS QUANT FLOOR - Chief API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chief_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chief-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)