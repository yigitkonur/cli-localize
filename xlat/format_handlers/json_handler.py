#!/usr/bin/env python3
"""
JSON format handler for i18next/react-intl style localization files.

Supports nested JSON structures with dot-notation flattening and
placeholder preservation.
"""

import json
import re
from typing import Any

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class JsonHandler(FormatHandler):
    """
    Handler for JSON localization files (i18next, react-intl, vue-i18n).

    Supports structures like:
    ```json
    {
      "welcome": "Welcome",
      "user": {
        "greeting": "Hello {{name}}",
        "messages": {
          "one": "You have one message",
          "other": "You have {{count}} messages"
        }
      }
    }
    ```

    Keys are flattened to dot notation: "user.greeting", "user.messages.one"
    Original structure is preserved in metadata for reconstruction.
    """

    @property
    def name(self) -> str:
        return "json"

    @property
    def file_extensions(self) -> list[str]:
        return ["json"]

    @property
    def supports_context(self) -> bool:
        """JSON keys are independent; no temporal/sequential context."""
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """JSON files commonly use i18next and ICU placeholders."""
        return [
            PLACEHOLDER_PATTERNS['i18next'],  # {{name}}
            PLACEHOLDER_PATTERNS['icu'],       # {name}
            PLACEHOLDER_PATTERNS['icu_full'],  # {count, plural, ...}
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse JSON content into translation entries.

        Args:
            content: Raw JSON file content

        Returns:
            List of TranslationEntry with flattened keys
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        entries = []
        self._flatten_dict(data, "", entries)
        return entries

    def _flatten_dict(
        self,
        obj: Any,
        prefix: str,
        entries: list[TranslationEntry],
        path_parts: list[str] = None,
    ) -> None:
        """
        Recursively flatten nested dict to dot-notation entries.

        Args:
            obj: Current object (dict, list, or scalar)
            prefix: Current key prefix (dot-separated)
            entries: List to append entries to
            path_parts: List of path components for metadata
        """
        if path_parts is None:
            path_parts = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                new_path = path_parts + [key]
                self._flatten_dict(value, new_prefix, entries, new_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_prefix = f"{prefix}.{i}"
                new_path = path_parts + [str(i)]
                self._flatten_dict(item, new_prefix, entries, new_path)

        elif isinstance(obj, str):
            # Skip metadata keys (ARB-style @keys)
            if prefix.startswith('@') or any(p.startswith('@') for p in path_parts):
                return

            # Extract placeholders for metadata
            placeholders = self.extract_placeholders(obj)

            entries.append(TranslationEntry(
                id=prefix,
                text=obj,
                context=None,
                metadata={
                    'path': path_parts.copy(),
                    'placeholders': placeholders,
                    'type': 'string',
                }
            ))

        # Skip other types (numbers, booleans, null) - not translatable

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct nested JSON from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text

        Returns:
            Reconstructed JSON content
        """
        result = {}

        for entry in entries:
            # Get translated text or fall back to original
            translated_text = translations.get(entry.id, entry.text)

            # Get path from metadata
            path = entry.metadata.get('path', entry.id.split('.'))

            # Set nested value
            self._set_nested(result, path, translated_text)

        return json.dumps(result, indent=2, ensure_ascii=False)

    def _set_nested(self, obj: dict, path: list[str], value: str) -> None:
        """
        Set value at nested path in dict, creating intermediate dicts as needed.

        Array indices are stored as string digits (e.g., "0", "1") in dot notation.

        Args:
            obj: Root dictionary
            path: List of keys to traverse
            value: Value to set at path
        """
        for i, key in enumerate(path[:-1]):
            # Handle array indices (stored as digit strings like "0", "1")
            if key.isdigit():
                idx = int(key)
                parent_key = path[i - 1] if i > 0 else None

                # Ensure parent is a list
                if parent_key and parent_key in obj and not isinstance(obj[parent_key], list):
                    obj[parent_key] = []

                # Extend list if needed
                while len(obj.get(parent_key, [])) <= idx:
                    obj.setdefault(parent_key, []).append({})

                obj = obj[parent_key][idx]
            else:
                if key not in obj:
                    # Check if next key is array index (digit string)
                    next_key = path[i + 1] if i + 1 < len(path) else None
                    if next_key and next_key.isdigit():
                        obj[key] = []
                    else:
                        obj[key] = {}
                obj = obj[key]

        # Set final value
        final_key = path[-1]
        if final_key.isdigit():
            idx = int(final_key)
            while len(obj) <= idx:
                obj.append(None)
            obj[idx] = value
        else:
            obj[final_key] = value

    def validate_content(self, content: str) -> list[str]:
        """
        Validate JSON file format.

        Args:
            content: Raw JSON content

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                errors.append("Root element must be an object")
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {e.msg} at line {e.lineno}")

        return errors


class NestedJsonHandler(JsonHandler):
    """
    Alternative JSON handler that preserves exact nesting structure.

    Use this when you need to maintain the exact JSON structure without
    flattening to dot notation.
    """

    @property
    def name(self) -> str:
        return "json-nested"

    def parse(self, content: str) -> list[TranslationEntry]:
        """Parse JSON while preserving structure in metadata."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        entries = []
        self._parse_nested(data, "", entries, data)
        return entries

    def _parse_nested(
        self,
        obj: Any,
        prefix: str,
        entries: list[TranslationEntry],
        root: dict,
    ) -> None:
        """Parse nested structure, storing full context."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                self._parse_nested(value, new_prefix, entries, root)

        elif isinstance(obj, str):
            if not prefix.startswith('@'):
                entries.append(TranslationEntry(
                    id=prefix,
                    text=obj,
                    metadata={
                        'original_structure': root,  # Store full structure
                        'placeholders': self.extract_placeholders(obj),
                    }
                ))

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """Reconstruct using original structure from metadata."""
        if not entries:
            return "{}"

        # Get original structure from first entry
        original = entries[0].metadata.get('original_structure', {})

        # Deep copy and replace strings
        result = self._deep_replace(original, translations)

        return json.dumps(result, indent=2, ensure_ascii=False)

    def _deep_replace(self, obj: Any, translations: dict[str, str], prefix: str = "") -> Any:
        """Deep copy structure while replacing translated strings."""
        if isinstance(obj, dict):
            return {
                k: self._deep_replace(
                    v, translations, f"{prefix}.{k}" if prefix else k
                )
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [
                self._deep_replace(item, translations, f"{prefix}.{i}")
                for i, item in enumerate(obj)
            ]
        elif isinstance(obj, str):
            return translations.get(prefix, obj)
        else:
            return obj
