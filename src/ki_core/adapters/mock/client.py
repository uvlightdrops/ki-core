from __future__ import annotations

from collections.abc import Iterator

from ki_core.core.client import AIClient
from ki_core.core.errors import ValidationError
from ki_core.core.models import ChatRequest, ChatResponse, Message, Role, StreamEvent, StreamEventType


class MockAIClient(AIClient):
    def __init__(self, model: str = "mock-1") -> None:
        self._model = model

    def chat(self, request: ChatRequest) -> ChatResponse:
        if not request.messages:
            raise ValidationError("chat request must include at least one message")

        latest = request.messages[-1].content.strip()
        text = f"mock:{latest}" if latest else "mock:ok"
        return ChatResponse(
            message=Message(role=Role.ASSISTANT, content=text),
            provider="mock",
            model=request.model or self._model,
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        response = self.chat(request)
        for token in response.message.content.split(" "):
            yield StreamEvent(type=StreamEventType.TOKEN, text=token)
        yield StreamEvent(type=StreamEventType.DONE)
