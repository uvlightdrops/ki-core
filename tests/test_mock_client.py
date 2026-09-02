from ki_core.adapters.mock.client import MockAIClient
from ki_core.core.errors import ValidationError
from ki_core.core.models import ChatRequest, Message, Role, StreamEventType


def test_chat_returns_mock_prefixed_response() -> None:
    client = MockAIClient()
    req = ChatRequest(messages=[Message(role=Role.USER, content="hello")])

    res = client.chat(req)

    assert res.provider == "mock"
    assert res.message.role == Role.ASSISTANT
    assert res.message.content == "mock:hello"


def test_chat_raises_on_empty_messages() -> None:
    client = MockAIClient()
    req = ChatRequest(messages=[])

    try:
        client.chat(req)
        assert False, "expected ValidationError"
    except ValidationError:
        assert True


def test_chat_stream_emits_tokens_then_done() -> None:
    client = MockAIClient()
    req = ChatRequest(messages=[Message(role=Role.USER, content="hi there")])

    events = list(client.chat_stream(req))

    assert events[-1].type == StreamEventType.DONE
    assert [e.text for e in events[:-1]] == ["mock:hi", "there"]
