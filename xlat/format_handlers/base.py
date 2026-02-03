#!/usr/bin/env python3
"""
Base classes for format handlers.

FormatHandler is the abstract base class that all format-specific handlers
must implement. TranslationEntry is the universal data structure for
translatable content across all formats.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TranslationEntry:
    """
    Universal translation entry that works across all formats.

    Attributes:
        id: Unique identifier (index for SRT, dotted key for JSON, msgid for PO)
        text: Source text to translate
        context: Optional context/comment for translator guidance
        metadata: Format-specific data (timings for SRT, placeholders for JSON, etc.)
    """
    id: str
    text: str
    context: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure id is string."""
        self.id = str(self.id)


@dataclass
class PlaceholderPattern:
    """Pattern definition for placeholder detection."""
    name: str
    pattern: str  # Regex pattern

    def find_all(self, text: str) -> list[str]:
        """Find all placeholders matching this pattern."""
        return re.findall(self.pattern, text)


# Common placeholder patterns across formats
PLACEHOLDER_PATTERNS = {
    'i18next': PlaceholderPattern('i18next', r'{{(\w+)}}'),          # {{name}}
    'icu': PlaceholderPattern('icu', r'\{(\w+)\}'),                   # {name}
    'icu_full': PlaceholderPattern('icu_full', r'\{[^}]+\}'),         # {count, plural, ...}
    'printf': PlaceholderPattern('printf', r'%[\d$]*[sd]'),           # %s, %1$s, %d
    'printf_named': PlaceholderPattern('printf_named', r'%\((\w+)\)s'), # %(name)s
    'ruby': PlaceholderPattern('ruby', r'%\{(\w+)\}'),                # %{name}
    'laravel': PlaceholderPattern('laravel', r':(\w+)'),              # :name
    'android': PlaceholderPattern('android', r'%\d+\$[sd]'),          # %1$s, %2$d
    'ios': PlaceholderPattern('ios', r'%@|%d|%ld|%f'),                # %@, %d
}


class FormatHandler(ABC):
    """
    Abstract base class for format-specific handlers.

    Each format handler implements parsing and reconstruction for a specific
    localization file format (SRT, JSON, PO, etc.). The handler is responsible
    for converting between the format-specific structure and the universal
    TranslationEntry format.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable format name."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """List of file extensions this handler supports (without dot)."""
        pass

    @property
    @abstractmethod
    def supports_context(self) -> bool:
        """
        Whether this format benefits from context entries.

        SRT: True (temporal context helps maintain consistency)
        JSON: False (keys are independent)
        PO: False (has built-in comments for context)
        """
        pass

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """
        Placeholder patterns used by this format.

        Override in subclasses to specify format-specific patterns.
        Default returns empty list (no placeholder validation).
        """
        return []

    @abstractmethod
    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse format-specific content into translation entries.

        Args:
            content: Raw file content as string

        Returns:
            List of TranslationEntry objects
        """
        pass

    @abstractmethod
    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct format-specific output from entries and translations.

        Args:
            entries: Original TranslationEntry objects (with metadata)
            translations: Map of entry_id -> translated_text

        Returns:
            Reconstructed file content as string
        """
        pass

    def validate_content(self, content: str) -> list[str]:
        """
        Validate that content is properly formatted for this handler.

        Args:
            content: Raw file content

        Returns:
            List of validation error messages (empty if valid)
        """
        return []

    def extract_placeholders(self, text: str) -> list[str]:
        """
        Extract all placeholders from text using this format's patterns.

        Args:
            text: Text to extract placeholders from

        Returns:
            List of placeholder strings found (deduplicated, order preserved)
        """
        # ICU MessageFormat detection pattern
        ICU_PATTERN = r'\{(\w+),\s*(plural|select|selectordinal)'

        placeholders = []
        for pattern in self.placeholder_patterns:
            # Special handling for ICU full pattern to avoid extracting nested content
            if pattern.name == 'icu_full':
                # Check if this is an ICU MessageFormat string
                icu_matches = re.findall(ICU_PATTERN, text)
                if icu_matches:
                    # Extract only the variable names from ICU syntax
                    for var_name, _ in icu_matches:
                        placeholders.append('{' + var_name + '}')
                else:
                    # Not ICU syntax, use regular extraction
                    for match in re.finditer(pattern.pattern, text):
                        placeholders.append(match.group(0))
            else:
                # Standard extraction for non-ICU patterns
                for match in re.finditer(pattern.pattern, text):
                    placeholders.append(match.group(0))

        # Deduplicate while preserving order
        return list(dict.fromkeys(placeholders))

    def validate_placeholders(
        self,
        source: str,
        translation: str,
    ) -> list[str]:
        """
        Validate that all source placeholders exist in translation.

        Args:
            source: Original source text
            translation: Translated text

        Returns:
            List of missing placeholder error messages
        """
        source_placeholders = set(self.extract_placeholders(source))
        translation_placeholders = set(self.extract_placeholders(translation))

        errors = []
        missing = source_placeholders - translation_placeholders
        for placeholder in missing:
            errors.append(f"Missing placeholder in translation: {placeholder}")

        return errors


class FormatRegistry:
    """Registry of available format handlers."""

    _handlers: dict[str, type[FormatHandler]] = {}
    _extension_map: dict[str, str] = {}  # extension -> handler name

    @classmethod
    def register(cls, handler_class: type[FormatHandler]) -> None:
        """Register a format handler class."""
        # Create instance to get properties
        handler = handler_class()
        cls._handlers[handler.name.lower()] = handler_class
        for ext in handler.file_extensions:
            cls._extension_map[ext.lower()] = handler.name.lower()

    @classmethod
    def get_handler(cls, name: str) -> FormatHandler:
        """Get handler instance by name."""
        name_lower = name.lower()
        if name_lower not in cls._handlers:
            available = ', '.join(cls._handlers.keys())
            raise ValueError(f"Unknown format: {name}. Available: {available}")
        return cls._handlers[name_lower]()

    @classmethod
    def get_handler_for_extension(cls, extension: str) -> FormatHandler:
        """Get handler instance by file extension."""
        ext = extension.lower().lstrip('.')
        if ext not in cls._extension_map:
            available = ', '.join(cls._extension_map.keys())
            raise ValueError(f"Unknown extension: .{ext}. Supported: {available}")
        return cls.get_handler(cls._extension_map[ext])

    @classmethod
    def detect_format(cls, filepath: str, content: str = None) -> FormatHandler:
        """
        Auto-detect format from file path and optionally content.

        Args:
            filepath: Path to the file
            content: Optional file content for content-based detection

        Returns:
            Appropriate FormatHandler instance
        """
        from pathlib import Path
        ext = Path(filepath).suffix.lower().lstrip('.')

        # Special case: .xml could be Android or other XML formats
        if ext == 'xml' and content:
            if '<resources>' in content or '<string ' in content:
                return cls.get_handler('android')

        return cls.get_handler_for_extension(ext)

    @classmethod
    def list_formats(cls) -> list[dict[str, Any]]:
        """List all registered formats with their extensions."""
        result = []
        for name, handler_class in cls._handlers.items():
            handler = handler_class()
            result.append({
                'name': handler.name,
                'extensions': handler.file_extensions,
                'supports_context': handler.supports_context,
            })
        return result
