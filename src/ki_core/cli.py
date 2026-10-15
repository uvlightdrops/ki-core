#!/usr/bin/env python3
"""Simple ki-core CLI for testing providers and config management."""

import sys
from pathlib import Path

from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.commands import (
    run_doctor as _run_doctor,
    run_resolve,
    run_verify,
    run_skeleton,
    run_show,
    run_profile_list,
    run_profile_set,
    run_profile_active,
    run_stage_list,
    run_stage_set,
    run_stage_active,
)
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
    elif command == "doctor":
        run_doctor()
    elif command == "config":
        run_config_command()
    elif command == "profile":
        run_profile_command()
    elif command == "stage":
        run_stage_command()
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
ki-core CLI (shared base for all apps)

Usage:
  ki-chat mock                          # Test with mock provider
  ki-chat ollama                        # Chat with Ollama (local)
  ki-chat openai                        # Chat with OpenAI API
  ki-chat doctor                        # Show config resolution chain & defaults
  ki-chat config-skeleton [output_path] # Generate config skeleton with defaults
  ki-chat cert-diagnose <host[:port]>   # Show TLS certificate details for a host
  
  ki-chat config resolve                # Resolve and display full config
  ki-chat config verify                 # Verify config against schema
  ki-chat config skeleton [output]      # Generate config skeleton
  ki-chat config show [key]             # Show config or specific key
  
  ki-chat profile list                  # List available profiles
  ki-chat profile set <name>            # Set active profile
  ki-chat profile active                # Show active profile
  
  ki-chat stage list                    # List available stages
  ki-chat stage set <name>              # Set active stage
  ki-chat stage active                  # Show active stage
  
  ki-chat help                          # Show this help

Examples:
  ki-chat doctor                        # Show where defaults come from
  OLLAMA_BASE_URL=http://localhost:11434 ki-chat ollama
  KI_API_KEY=sk-... KI_BASE_URL=https://api.openai.com/v1 ki-chat openai
  ki-chat config-skeleton ./ki.yaml     # Generate default config
  ki-chat config resolve                # Show full resolved config
  ki-chat profile list                  # See all profiles
  ki-chat profile set dev               # Activate dev profile
  ki-chat stage list                    # See all stages
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


def run_doctor():
    """Show config resolution chain and where defaults come from."""
    _run_doctor(echo_fn=print, show_config_path=False)


def run_config_command():
    """Handle config subcommands."""
    if len(sys.argv) < 3:
        print("Config subcommands: resolve, verify, skeleton, show")
        sys.exit(1)
    
    subcommand = sys.argv[2]
    
    try:
        if subcommand == "resolve":
            run_resolve(echo_fn=print)
        elif subcommand == "verify":
            config_file = sys.argv[3] if len(sys.argv) > 3 else None
            schema_file = sys.argv[4] if len(sys.argv) > 4 else None
            run_verify(echo_fn=print, config_file=config_file, schema_file=schema_file)
        elif subcommand == "skeleton":
            output_file = sys.argv[3] if len(sys.argv) > 3 else "ki.yaml"
            run_skeleton(echo_fn=print, output_file=output_file)
        elif subcommand == "show":
            key = sys.argv[3] if len(sys.argv) > 3 else None
            run_show(echo_fn=print, key=key)
        else:
            print(f"Unknown config subcommand: {subcommand}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_profile_command():
    """Handle profile subcommands."""
    if len(sys.argv) < 3:
        print("Profile subcommands: list, set <name>, active")
        sys.exit(1)
    
    subcommand = sys.argv[2]
    
    try:
        if subcommand == "list":
            run_profile_list(echo_fn=print)
        elif subcommand == "set":
            if len(sys.argv) < 4:
                print("Usage: ki-chat profile set <name>")
                sys.exit(1)
            profile_name = sys.argv[3]
            run_profile_set(echo_fn=print, profile_name=profile_name)
        elif subcommand == "active":
            run_profile_active(echo_fn=print)
        else:
            print(f"Unknown profile subcommand: {subcommand}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_stage_command():
    """Handle stage subcommands."""
    if len(sys.argv) < 3:
        print("Stage subcommands: list, set <name>, active")
        sys.exit(1)
    
    subcommand = sys.argv[2]
    
    try:
        if subcommand == "list":
            run_stage_list(echo_fn=print)
        elif subcommand == "set":
            if len(sys.argv) < 4:
                print("Usage: ki-chat stage set <name>")
                sys.exit(1)
            stage_name = sys.argv[3]
            run_stage_set(echo_fn=print, stage_name=stage_name)
        elif subcommand == "active":
            run_stage_active(echo_fn=print)
        else:
            print(f"Unknown stage subcommand: {subcommand}")
            sys.exit(1)
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
