"""Parse multi-part LLM responses (text + code + commands).

LLM responses often contain mixed content:
- Regular text explanation
- Code blocks (```python ...```)
- Shell commands (```bash ...```)
- Markdown formatting

This parser extracts and categorizes different response parts.
"""

import re
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class ResponsePartType(str, Enum):
    """Type of response part."""
    TEXT = "text"
    CODE = "code"
    SHELL = "shell"
    MARKDOWN = "markdown"


@dataclass
class ResponsePart:
    """Single part of parsed response."""
    type: ResponsePartType
    content: str
    language: Optional[str] = None  # For code blocks: python, javascript, bash, etc.


class ResponseParser:
    """Parse multi-part LLM responses."""

    # Regex patterns
    CODE_BLOCK_PATTERN = r'```(\w*)\n(.*?)\n```'
    SHELL_BLOCK_PATTERN = r'```(bash|sh|shell|zsh)\n(.*?)\n```'
    MARKDOWN_PATTERN = r'(?:^|\n)(#+\s+.*?)(?=\n#|\n|$)'

    def __init__(self):
        """Initialize response parser."""
        self.parts: List[ResponsePart] = []

    def parse(self, response: str) -> List[ResponsePart]:
        """Parse LLM response into parts.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            List of ResponsePart objects
        """
        if not response:
            return []

        self.parts = []
        remaining = response
        position = 0

        # Find all code blocks
        code_blocks = list(re.finditer(self.CODE_BLOCK_PATTERN, response, re.MULTILINE | re.DOTALL))

        if not code_blocks:
            # No code blocks, treat entire response as text
            self.parts.append(ResponsePart(
                type=ResponsePartType.TEXT,
                content=response.strip()
            ))
            return self.parts

        # Process segments before, between, and after code blocks
        last_end = 0

        for match in code_blocks:
            start = match.start()
            end = match.end()

            # Add text before code block
            if start > last_end:
                text_before = response[last_end:start].strip()
                if text_before:
                    self.parts.append(ResponsePart(
                        type=ResponsePartType.TEXT,
                        content=text_before
                    ))

            # Extract code block
            language = match.group(1) or "text"
            code_content = match.group(2).strip()

            # Determine if it's shell or code
            if language in ("bash", "sh", "shell", "zsh"):
                part_type = ResponsePartType.SHELL
            else:
                part_type = ResponsePartType.CODE

            self.parts.append(ResponsePart(
                type=part_type,
                content=code_content,
                language=language if language else None
            ))

            last_end = end

        # Add remaining text
        if last_end < len(response):
            text_after = response[last_end:].strip()
            if text_after:
                self.parts.append(ResponsePart(
                    type=ResponsePartType.TEXT,
                    content=text_after
                ))

        return self.parts

    def get_parts_by_type(self, part_type: ResponsePartType) -> List[ResponsePart]:
        """Get all parts of specific type.
        
        Args:
            part_type: Type to filter by
            
        Returns:
            List of matching parts
        """
        return [p for p in self.parts if p.type == part_type]

    def extract_code_blocks(self) -> List[ResponsePart]:
        """Extract all code blocks (excluding shell).
        
        Returns:
            List of code parts
        """
        return self.get_parts_by_type(ResponsePartType.CODE)

    def extract_shell_commands(self) -> List[ResponsePart]:
        """Extract all shell command blocks.
        
        Returns:
            List of shell parts
        """
        return self.get_parts_by_type(ResponsePartType.SHELL)

    def extract_text(self) -> str:
        """Extract all text parts concatenated.
        
        Returns:
            Full text content
        """
        text_parts = self.get_parts_by_type(ResponsePartType.TEXT)
        return "\n\n".join(p.content for p in text_parts)

    def has_code(self) -> bool:
        """Check if response contains code blocks."""
        return bool(self.extract_code_blocks())

    def has_shell(self) -> bool:
        """Check if response contains shell commands."""
        return bool(self.extract_shell_commands())

    def __str__(self) -> str:
        """String representation for debugging."""
        summary = f"ResponseParser(parts={len(self.parts)})"
        for i, part in enumerate(self.parts):
            lang = f" [{part.language}]" if part.language else ""
            content_preview = part.content[:50].replace("\n", " ") + ("..." if len(part.content) > 50 else "")
            summary += f"\n  {i+1}. {part.type.value}{lang}: {content_preview}"
        return summary


class ResponseFormatter:
    """Format parsed response parts for display or processing."""

    @staticmethod
    def format_for_diff(parts: List[ResponsePart]) -> str:
        """Format response parts for diff display.
        
        Args:
            parts: List of ResponsePart objects
            
        Returns:
            Formatted string for diff viewer
        """
        output = []

        for part in parts:
            if part.type == ResponsePartType.TEXT:
                output.append(f"# {part.content}\n")
            elif part.type == ResponsePartType.CODE:
                lang = part.language or "text"
                output.append(f"```{lang}\n{part.content}\n```\n")
            elif part.type == ResponsePartType.SHELL:
                output.append(f"```bash\n{part.content}\n```\n")

        return "\n".join(output)

    @staticmethod
    def format_for_approval(parts: List[ResponsePart], max_preview: int = 100) -> str:
        """Format response parts for user approval.
        
        Args:
            parts: List of ResponsePart objects
            max_preview: Max chars to show per part
            
        Returns:
            Formatted string for approval dialog
        """
        output = []

        for i, part in enumerate(parts, 1):
            if part.type == ResponsePartType.TEXT:
                content = part.content[:max_preview]
                if len(part.content) > max_preview:
                    content += "..."
                output.append(f"{i}. Text: {content}")

            elif part.type == ResponsePartType.CODE:
                lines = part.content.split("\n")
                output.append(f"{i}. Code [{part.language}]: {len(lines)} lines")

            elif part.type == ResponsePartType.SHELL:
                lines = part.content.split("\n")
                output.append(f"{i}. Shell: {len(lines)} command(s)")

        return "\n".join(output)

    @staticmethod
    def format_for_editor(code_parts: List[ResponsePart]) -> str:
        """Format code parts for editor display.
        
        Args:
            code_parts: List of code ResponsePart objects
            
        Returns:
            Code formatted for editor
        """
        output = []

        for part in code_parts:
            output.append(part.content)

        return "\n\n".join(output)
