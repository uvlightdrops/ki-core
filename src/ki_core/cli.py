#!/usr/bin/env python3
"""Simple ki-core CLI for testing providers and config management."""

import sys
from pathlib import Path

from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.core.models import ChatRequest, Message, Role


def main():
    """Simple chat CLI."""
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1]

    if command == "mock":
        run_mock_chat()
    elif command == "ollama":
        run_ollama_chat()
    elif command == "openai":
        run_openai_chat()
    elif command == "config-skeleton":
        run_config_skeleton()
    elif command == "cert-diagnose":
        run_cert_diagnose()
    elif command == "help":
        print_help()
    else:
        print(f"Unknown command: {command}")
        print_help()
        sys.exit(1)


def print_help():
    """Print help message."""
    print(
        """
ki-core CLI

Usage:
  ki-chat mock                          # Test with mock provider
  ki-chat ollama                        # Chat with Ollama (local)
  ki-chat openai                        # Chat with OpenAI API
  ki-chat config-skeleton [output_path] # Generate config skeleton with defaults
  ki-chat cert-diagnose <host[:port]>   # Show TLS certificate details for a host
  ki-chat help                          # Show this help

Examples:
  OLLAMA_BASE_URL=http://localhost:11434 ki-chat ollama
  KI_API_KEY=sk-... KI_BASE_URL=https://api.openai.com/v1 ki-chat openai
  ki-chat config-skeleton ./ki.yaml     # Generate default config
  ki-chat cert-diagnose api.openai.com  # Diagnose TLS cert for a provider host
  ki-chat cert-diagnose https://internal.example.com:8443
"""
    )


def run_config_skeleton():
    """Generate config skeleton with defaults."""
    from ki_core.schema_manager import generate_config_skeleton, get_schema_path

    output_path = sys.argv[2] if len(sys.argv) > 2 else "ki.yaml"
    
    try:
        base_schema = get_schema_path()
        
        # Try to load kicli-code-assist schema if available
        kicli_schema = Path.cwd() / "schema" / "kicli.schema.yaml"
        additional = [kicli_schema] if kicli_schema.exists() else None
        
        generate_config_skeleton(base_schema, output_path, additional)
        print(f"✅ Config skeleton generated: {output_path}")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_cert_diagnose():
    """Show TLS certificate details and trust status for a host."""
    if len(sys.argv) < 3:
        print("Usage: ki-chat cert-diagnose <host[:port]|https://host[:port]>")
        sys.exit(1)

    from ki_core.cert_diagnostics import diagnose_certificate

    target = sys.argv[2]
    result = diagnose_certificate(target)
    print(result.render())
    if result.connect_error or not result.verified:
        sys.exit(1)


def run_mock_chat():
    """Run mock chat for testing."""
    print("Mock Chat (non-streaming)")
    print("=" * 50)

    client = MockAIClient(model="mock-test")

    # Non-streaming
    request = ChatRequest(
        messages=[Message(role=Role.USER, content="What is Python?")],
        model="mock",
    )

    response = client.chat(request)
    print(f"Response: {response.message.content}")
    print(f"Provider: {response.provider}, Model: {response.model}")

    # Streaming
    print("\nStreaming:")
    for event in client.chat_stream(request):
        if event.text:
            print(event.text, end="", flush=True)
    print()


def run_ollama_chat():
    """Run Ollama chat."""
    import os

    print("Ollama Chat")
    print("=" * 50)

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama2")

    try:
        client = OllamaClient(base_url=base_url, model=model)

        # Check available models
        print(f"Checking available models at {base_url}...")
        models = OllamaClient.get_available_models(base_url)
        print(f"Available: {models}")

        if not models:
            print("ERROR: No models available. Run: ollama pull llama2")
            sys.exit(1)

        if model not in models:
            print(f"WARNING: {model} not found, using {models[0]}")
            model = models[0]

        print(f"Using model: {model}\n")

        # Interactive chat
        print("Type 'quit' or 'exit' to stop\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ("quit", "exit"):
                    break
                if not user_input:
                    continue

                request = ChatRequest(
                    messages=[Message(role=Role.USER, content=user_input)],
                    model=model,
                )

                print("Assistant: ", end="", flush=True)
                for event in client.chat_stream(request):
                    if event.text:
                        print(event.text, end="", flush=True)
                print()
            except KeyboardInterrupt:
                break

    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Make sure Ollama is running: ollama serve")
        sys.exit(1)


def run_openai_chat():
    """Run OpenAI-compatible chat."""
    import os

    print("OpenAI-Compatible Chat")
    print("=" * 50)

    api_key = os.getenv("KI_API_KEY", "").strip()
    base_url = os.getenv("KI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("KI_MODEL", "gpt-3.5-turbo")

    if not api_key:
        print("ERROR: KI_API_KEY not set")
        print("Export: export KI_API_KEY=sk-...")
        sys.exit(1)

    try:
        client = OpenAICompatibleClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )

        print(f"Using: {base_url}")
        print(f"Model: {model}\n")

        # Interactive chat
        print("Type 'quit' or 'exit' to stop\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ("quit", "exit"):
                    break
                if not user_input:
                    continue

                request = ChatRequest(
                    messages=[Message(role=Role.USER, content=user_input)],
                    model=model,
                )

                print("Assistant: ", end="", flush=True)
                for event in client.chat_stream(request):
                    if event.text:
                        print(event.text, end="", flush=True)
                print()
            except KeyboardInterrupt:
                break

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
