#!/usr/bin/env python3
"""
iOS .strings format handler.

Handles parsing and reconstruction of Apple .strings localization files
used in iOS, macOS, watchOS, and tvOS applications.
"""

import re
from typing import Optional

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class IosStringsHandler(FormatHandler):
    """
    Handler for iOS/macOS .strings files.

    .strings format structure:
    ```
    /* Comment about the string */
    "key.name" = "Value text";

    // Another style of comment
    "greeting" = "Hello, %@!";
    ```

    Preserves comments and handles Apple-style format specifiers.
    """

    @property
    def name(self) -> str:
        return "strings"

    @property
    def file_extensions(self) -> list[str]:
        return ["strings"]

    @property
    def supports_context(self) -> bool:
        """iOS strings have comment context built in."""
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """iOS uses Objective-C/Swift format specifiers."""
        return [
            PLACEHOLDER_PATTERNS['ios'],     # %@, %d, %ld, %f
            PLACEHOLDER_PATTERNS['printf'],  # %s, %d
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse .strings content into translation entries.

        Args:
            content: Raw .strings file content

        Returns:
            List of TranslationEntry objects
        """
        entries = []
        current_comment = []

        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Block comment /* ... */
            if line.startswith('/*'):
                comment_text = line[2:]
                while '*/' not in comment_text and i < len(lines) - 1:
                    i += 1
                    comment_text += '\n' + lines[i]
                # Remove closing */
                comment_text = comment_text.replace('*/', '').strip()
                current_comment.append(comment_text)

            # Line comment // ...
            elif line.startswith('//'):
                current_comment.append(line[2:].strip())

            # Key-value pair: "key" = "value";
            elif '=' in line and line.endswith(';'):
                match = re.match(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*;', line)
                if match:
                    key = self._unescape_string(match.group(1))
                    value = self._unescape_string(match.group(2))

                    entries.append(TranslationEntry(
                        id=key,
                        text=value,
                        context='\n'.join(current_comment) if current_comment else None,
                        metadata={
                            'comments': current_comment.copy(),
                            'placeholders': self.extract_placeholders(value),
                        }
                    ))
                    current_comment = []

            # Multi-line value
            elif '=' in line and not line.endswith(';'):
                match = re.match(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*=\s*"(.*)$', line)
                if match:
                    key = self._unescape_string(match.group(1))
                    value = match.group(2)

                    # Continue reading until we find ";
                    while not value.rstrip().endswith('";') and i < len(lines) - 1:
                        i += 1
                        value += '\n' + lines[i]

                    # Remove trailing ";
                    value = value.rstrip()
                    if value.endswith('";'):
                        value = value[:-2]

                    value = self._unescape_string(value)

                    entries.append(TranslationEntry(
                        id=key,
                        text=value,
                        context='\n'.join(current_comment) if current_comment else None,
                        metadata={
                            'comments': current_comment.copy(),
                            'placeholders': self.extract_placeholders(value),
                        }
                    ))
                    current_comment = []

            i += 1

        return entries

    def _unescape_string(self, s: str) -> str:
        """Unescape .strings file escapes."""
        return (
            s.replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\"', '"')
            .replace('\\\\', '\\')
        )

    def _escape_string(self, s: str) -> str:
        """Escape string for .strings format."""
        return (
            s.replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\t', '\\t')
        )

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct .strings file from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text

        Returns:
            Complete .strings file content
        """
        lines = []

        for entry in entries:
            # Add comments
            comments = entry.metadata.get('comments', [])
            for comment in comments:
                if '\n' in comment:
                    lines.append(f'/* {comment} */')
                else:
                    lines.append(f'/* {comment} */')

            # Add key-value pair
            translated = translations.get(entry.id, entry.text)
            escaped_key = self._escape_string(entry.id)
            escaped_value = self._escape_string(translated)
            lines.append(f'"{escaped_key}" = "{escaped_value}";')
            lines.append('')

        return '\n'.join(lines)

    def validate_content(self, content: str) -> list[str]:
        """Validate .strings file format."""
        errors = []

        # Check for basic structure
        if '=' not in content:
            errors.append("No key-value pairs found (expected format: \"key\" = \"value\";)")

        # Check for mismatched quotes
        in_string = False
        for i, char in enumerate(content):
            if char == '"' and (i == 0 or content[i-1] != '\\'):
                in_string = not in_string

        if in_string:
            errors.append("Unmatched quote found")

        return errors
