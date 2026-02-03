#!/usr/bin/env python3
"""
YAML format handler for Rails/Symfony i18n files.

Handles parsing and reconstruction of YAML localization files commonly
used in Ruby on Rails, Symfony, and other backend frameworks.
"""

from typing import Any

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class YamlHandler(FormatHandler):
    """
    Handler for YAML i18n files (Rails/Symfony style).

    YAML i18n structure:
    ```yaml
    en:
      welcome: Welcome
      user:
        greeting: "Hello %{name}"
        messages:
          one: You have one message
          other: "You have %{count} messages"
    ```

    Handles nested structures and Rails-style %{var} placeholders.
    """

    @property
    def name(self) -> str:
        return "yaml"

    @property
    def file_extensions(self) -> list[str]:
        return ["yml", "yaml"]

    @property
    def supports_context(self) -> bool:
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """YAML i18n commonly uses Ruby-style placeholders."""
        return [
            PLACEHOLDER_PATTERNS['ruby'],     # %{name}
            PLACEHOLDER_PATTERNS['i18next'],  # {{name}} (sometimes used)
        ]

    def __init__(self):
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML format support. Install with: pip install pyyaml")

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse YAML content into translation entries.

        Args:
            content: Raw YAML file content

        Returns:
            List of TranslationEntry with flattened keys
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

        if not isinstance(data, dict):
            raise ValueError("YAML root must be a mapping")

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
                str_key = str(key)
                new_prefix = f"{prefix}.{str_key}" if prefix else str_key
                new_path = path_parts + [str_key]
                self._flatten_dict(value, new_prefix, entries, new_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_prefix = f"{prefix}.{i}"
                new_path = path_parts + [str(i)]
                self._flatten_dict(item, new_prefix, entries, new_path)

        elif isinstance(obj, str):
            entries.append(TranslationEntry(
                id=prefix,
                text=obj,
                context=None,
                metadata={
                    'path': path_parts.copy(),
                    'placeholders': self.extract_placeholders(obj),
                    'type': 'string',
                }
            ))

        # Skip numbers, booleans, null - not translatable

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct YAML file from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text

        Returns:
            Complete YAML file content
        """
        result = {}

        for entry in entries:
            translated = translations.get(entry.id, entry.text)
            path = entry.metadata.get('path', entry.id.split('.'))
            self._set_nested(result, path, translated)

        return yaml.dump(
            result,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def _set_nested(self, obj: dict, path: list[str], value: str) -> None:
        """
        Set value at nested path in dict, creating intermediate structures as needed.

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

        final_key = path[-1]
        if final_key.isdigit():
            # Final key is array index
            idx = int(final_key)
            while len(obj) <= idx:
                obj.append(None)
            obj[idx] = value
        else:
            obj[final_key] = value

    def validate_content(self, content: str) -> list[str]:
        """Validate YAML file format."""
        errors = []

        try:
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                errors.append("YAML root must be a mapping (dictionary)")
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML syntax: {e}")

        return errors
