from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[Message]
    model: str | None = None
    temperature: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResponse:
    message: Message
    provider: str
    model: str


class StreamEventType(str, Enum):
    TOKEN = "token"
    DONE = "done"


@dataclass(frozen=True)
class StreamEvent:
    type: StreamEventType
    text: str = ""
