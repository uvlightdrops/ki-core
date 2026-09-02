from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from ki_core.core.models import ChatRequest, ChatResponse, StreamEvent


class AIClient(ABC):
    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        raise NotImplementedError
