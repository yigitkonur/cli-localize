#!/usr/bin/env python3
"""
Flutter ARB (Application Resource Bundle) format handler.

Handles parsing and reconstruction of .arb files used in Flutter/Dart
applications for internationalization.
"""

import json
import re
from typing import Any, Optional

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class ArbHandler(FormatHandler):
    """
    Handler for Flutter ARB (Application Resource Bundle) files.

    ARB format structure:
    ```json
    {
      "@@locale": "en",
      "welcomeMessage": "Welcome, {name}!",
      "@welcomeMessage": {
        "description": "Welcome message shown on home screen",
        "placeholders": {
          "name": {"type": "String"}
        }
      },
      "itemCount": "{count, plural, =0{No items} =1{One item} other{{count} items}}",
      "@itemCount": {
        "description": "Number of items in cart"
      }
    }
    ```

    Preserves @-prefixed metadata entries and handles ICU MessageFormat.
    """

    @property
    def name(self) -> str:
        return "arb"

    @property
    def file_extensions(self) -> list[str]:
        return ["arb"]

    @property
    def supports_context(self) -> bool:
        """ARB has built-in @key metadata for context."""
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """ARB uses ICU MessageFormat placeholders."""
        return [
            PLACEHOLDER_PATTERNS['icu'],      # {name}
            PLACEHOLDER_PATTERNS['icu_full'], # {count, plural, ...}
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse ARB content into translation entries.

        Args:
            content: Raw ARB file content

        Returns:
            List of TranslationEntry objects
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in ARB file: {e}")

        entries = []

        # Extract @@ prefixed file-level metadata (@@locale, @@context, @@author, etc.)
        file_metadata = {}
        for key, value in data.items():
            if key.startswith('@@'):
                file_metadata[key] = value

        for key, value in data.items():
            # Skip metadata keys (start with @)
            if key.startswith('@'):
                continue

            # Skip non-string values
            if not isinstance(value, str):
                continue

            # Get metadata from @key if it exists
            metadata_key = f"@{key}"
            metadata_value = data.get(metadata_key, {})

            # Extract description for context
            description = None
            if isinstance(metadata_value, dict):
                description = metadata_value.get('description')

            # Extract placeholder info
            placeholders_meta = {}
            if isinstance(metadata_value, dict) and 'placeholders' in metadata_value:
                placeholders_meta = metadata_value['placeholders']

            entries.append(TranslationEntry(
                id=key,
                text=value,
                context=description,
                metadata={
                    'metadata': metadata_value,  # Full @key metadata
                    'placeholders_meta': placeholders_meta,
                    'placeholders': self.extract_placeholders(value),
                    'is_icu': self._is_icu_message(value),
                    'file_metadata': file_metadata,  # Store @@ metadata for reconstruction
                }
            ))

        return entries

    def _is_icu_message(self, text: str) -> bool:
        """Check if text contains ICU MessageFormat syntax."""
        # ICU patterns: {var, plural/select/selectordinal, ...}
        return bool(re.search(r'\{\w+,\s*(plural|select|selectordinal)', text))

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
        target_language: Optional[str] = None,
    ) -> str:
        """
        Reconstruct ARB file from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text
            target_language: Target language code (e.g., 'tr', 'es', 'fr')

        Returns:
            Complete ARB file content
        """
        result = {}

        # Restore @@ file-level metadata from the first entry (all entries have same file_metadata)
        if entries:
            file_metadata = entries[0].metadata.get('file_metadata', {})
            for key, value in file_metadata.items():
                result[key] = value

        # Update @@locale to target language if provided
        if target_language:
            result['@@locale'] = target_language
        elif '@@locale' not in result:
            # Fallback only if no original @@locale and no target specified
            result['@@locale'] = 'translated'

        for entry in entries:
            # Add translated value
            translated = translations.get(entry.id, entry.text)
            result[entry.id] = translated

            # Preserve @key metadata
            metadata = entry.metadata.get('metadata')
            if metadata:
                result[f"@{entry.id}"] = metadata

        return json.dumps(result, indent=2, ensure_ascii=False)

    def validate_content(self, content: str) -> list[str]:
        """Validate ARB file format."""
        errors = []

        try:
            data = json.loads(content)

            if not isinstance(data, dict):
                errors.append("ARB root must be a JSON object")
                return errors

            # Check for @@locale (optional but recommended)
            if '@@locale' not in data:
                errors.append("Warning: Missing @@locale metadata")

            # Validate @key metadata entries
            for key, value in data.items():
                if key.startswith('@') and not key.startswith('@@'):
                    # This should be metadata for a key
                    base_key = key[1:]
                    if base_key not in data:
                        errors.append(f"Metadata key {key} has no corresponding entry {base_key}")
                    if not isinstance(value, dict):
                        errors.append(f"Metadata {key} should be an object")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {e.msg} at line {e.lineno}")

        return errors

    def validate_icu_message(self, text: str) -> list[str]:
        """
        Validate ICU MessageFormat syntax.

        Args:
            text: Text that may contain ICU MessageFormat

        Returns:
            List of validation error messages
        """
        errors = []

        # Check for balanced braces
        depth = 0
        for char in text:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth < 0:
                    errors.append("Unmatched closing brace in ICU message")
                    break

        if depth > 0:
            errors.append("Unmatched opening brace in ICU message")

        # Check for valid plural keywords using brace-aware extraction
        plural_content = self._extract_plural_content(text)
        if plural_content:
            valid_keywords = {'zero', 'one', 'two', 'few', 'many', 'other'}
            # Match keywords like "one{", "other{", "=0{", "=1{", "=123{"
            found_keywords = set(re.findall(r'(\w+|=\d+)\s*\{', plural_content))
            # Filter out numeric keywords (=N format is always valid)
            non_numeric = {k for k in found_keywords if not k.startswith('=')}
            invalid = non_numeric - valid_keywords
            if invalid:
                errors.append(f"Invalid plural keywords: {invalid}")

        return errors

    def _extract_plural_content(self, text: str) -> Optional[str]:
        """
        Extract the full content of a plural block, handling nested braces.

        Args:
            text: ICU message text

        Returns:
            The content inside the plural block, or None if no plural found
        """
        # Find the start of plural: {var, plural,
        match = re.search(r'\{(\w+),\s*plural,\s*', text)
        if not match:
            return None

        start = match.end()
        depth = 1  # We're inside the outer { already
        end = start

        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        return text[start:end]
