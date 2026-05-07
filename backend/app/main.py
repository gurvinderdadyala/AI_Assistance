from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import ChatRequest, ChatResponse, HealthResponse
from app.rag_service import ITKnowledgeBot
from app.settings import get_settings

settings = get_settings()
bot = ITKnowledgeBot(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if bot.configured:
        bot.initialize()
    yield


app = FastAPI(title="Sample IT AI Assistance API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", configured=bot.configured, indexed=bot.indexed)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer, sources = await bot.answer(request.message, request.history)
        return ChatResponse(answer=answer, sources=sources)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/reindex")
async def reindex() -> dict[str, int | str]:
    try:
        document_count = bot.rebuild_index()
        return {"status": "ok", "documents": document_count}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
