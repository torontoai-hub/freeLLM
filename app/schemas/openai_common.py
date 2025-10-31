from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class ChoiceLogprobs(BaseModel):
    token_logprobs: Optional[list[float]] = None


class UsageInfo(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[UsageInfo] = None


class ChatStreamChoiceDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatStreamChoice(BaseModel):
    index: int
    delta: ChatStreamChoiceDelta
    finish_reason: Optional[str] = None


class ChatStreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatStreamChoice]


class CompletionRequest(BaseModel):
    model: str
    prompt: str | list[str]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=1.0)
    top_p: Optional[float] = Field(default=1.0)
    stream: Optional[bool] = False
    stop: Optional[str | list[str]] = None
    seed: Optional[int] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=1.0)
    top_p: Optional[float] = Field(default=1.0)
    stream: Optional[bool] = False
    stop: Optional[str | list[str]] = None
    seed: Optional[int] = None


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]


class EmbeddingData(BaseModel):
    embedding: list[float]
    index: int
    object: str = "embedding"


class EmbeddingResponse(BaseModel):
    data: List[EmbeddingData]
    model: str
    object: str = "list"
