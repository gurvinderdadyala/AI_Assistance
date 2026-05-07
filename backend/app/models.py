from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[ChatHistoryItem] = Field(default_factory=list)


class Source(BaseModel):
    title: str
    path: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    configured: bool
    indexed: bool
    provider: str
