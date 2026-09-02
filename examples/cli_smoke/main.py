from ki_core.adapters.mock.client import MockAIClient
from ki_core.core.models import ChatRequest, Message, Role


def main() -> None:
    client = MockAIClient()
    request = ChatRequest(messages=[Message(role=Role.USER, content="status")])
    response = client.chat(request)
    print(response.message.content)


if __name__ == "__main__":
    main()
