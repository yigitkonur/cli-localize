#!/usr/bin/env python3
"""
Android XML strings.xml format handler.

Handles parsing and reconstruction of Android resource files including
strings, plurals, and string arrays.
"""

import re
import html
from xml.etree import ElementTree as ET
from typing import Optional

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class AndroidXmlHandler(FormatHandler):
    """
    Handler for Android strings.xml resource files.

    Android XML structure:
    ```xml
    <?xml version="1.0" encoding="utf-8"?>
    <resources>
        <string name="app_name">My App</string>
        <string name="welcome">Welcome, %1$s!</string>

        <plurals name="items">
            <item quantity="one">%d item</item>
            <item quantity="other">%d items</item>
        </plurals>

        <string-array name="days">
            <item>Monday</item>
            <item>Tuesday</item>
        </string-array>
    </resources>
    ```

    Preserves XML structure and handles format specifiers.
    """

    @property
    def name(self) -> str:
        return "android"

    @property
    def file_extensions(self) -> list[str]:
        return ["xml"]

    @property
    def supports_context(self) -> bool:
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """Android uses numbered printf-style placeholders."""
        return [
            PLACEHOLDER_PATTERNS['android'],  # %1$s, %2$d
            PLACEHOLDER_PATTERNS['printf'],   # %s, %d
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse Android XML content into translation entries.

        Args:
            content: Raw XML file content

        Returns:
            List of TranslationEntry objects
        """
        entries = []

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")

        # Parse <string> elements
        for elem in root.findall('.//string'):
            name = elem.get('name')
            if name:
                text = self._get_element_text(elem)
                entries.append(TranslationEntry(
                    id=name,
                    text=text,
                    metadata={
                        'type': 'string',
                        'translatable': elem.get('translatable', 'true'),
                        'placeholders': self.extract_placeholders(text),
                    }
                ))

        # Parse <plurals> elements
        for plural in root.findall('.//plurals'):
            name = plural.get('name')
            if name:
                for item in plural.findall('item'):
                    quantity = item.get('quantity')
                    text = self._get_element_text(item)
                    entry_id = f"{name}#plural#{quantity}"

                    entries.append(TranslationEntry(
                        id=entry_id,
                        text=text,
                        metadata={
                            'type': 'plural',
                            'plural_name': name,
                            'quantity': quantity,
                            'placeholders': self.extract_placeholders(text),
                        }
                    ))

        # Parse <string-array> elements
        for array in root.findall('.//string-array'):
            name = array.get('name')
            if name:
                for i, item in enumerate(array.findall('item')):
                    text = self._get_element_text(item)
                    entry_id = f"{name}.{i}"

                    entries.append(TranslationEntry(
                        id=entry_id,
                        text=text,
                        metadata={
                            'type': 'array',
                            'array_name': name,
                            'index': i,
                            'placeholders': self.extract_placeholders(text),
                        }
                    ))

        return entries

    def _get_element_text(self, elem: ET.Element) -> str:
        """Extract text content from element, handling CDATA and mixed content."""
        if elem.text:
            text = elem.text
        else:
            text = ''

        # Handle inline elements (like <xliff:g>)
        for child in elem:
            if child.text:
                text += child.text
            if child.tail:
                text += child.tail

        # Unescape Android-specific escapes
        text = self._unescape_android(text)
        return text

    def _unescape_android(self, text: str) -> str:
        """Unescape Android string escapes."""
        # Unescape apostrophes and quotes
        text = text.replace("\\'", "'")
        text = text.replace('\\"', '"')
        # Unescape HTML entities
        text = html.unescape(text)
        return text

    def _escape_android(self, text: str) -> str:
        """Escape string for Android XML."""
        # Escape apostrophes and quotes
        text = text.replace("'", "\\'")
        # Escape special XML characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct Android XML from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text

        Returns:
            Complete XML file content
        """
        lines = ['<?xml version="1.0" encoding="utf-8"?>', '<resources>']

        # Group entries by type
        strings = []
        plurals = {}  # name -> list of (quantity, text)
        arrays = {}   # name -> list of texts

        for entry in entries:
            entry_type = entry.metadata.get('type', 'string')
            translated = translations.get(entry.id, entry.text)

            if entry_type == 'string':
                translatable = entry.metadata.get('translatable', 'true')
                escaped = self._escape_android(translated)
                if translatable == 'false':
                    lines.append(f'    <string name="{entry.id}" translatable="false">{escaped}</string>')
                else:
                    lines.append(f'    <string name="{entry.id}">{escaped}</string>')

            elif entry_type == 'plural':
                plural_name = entry.metadata.get('plural_name')
                quantity = entry.metadata.get('quantity')
                if plural_name not in plurals:
                    plurals[plural_name] = []
                plurals[plural_name].append((quantity, translated))

            elif entry_type == 'array':
                array_name = entry.metadata.get('array_name')
                idx = entry.metadata.get('index', 0)
                if array_name not in arrays:
                    arrays[array_name] = []
                # Ensure list is long enough
                while len(arrays[array_name]) <= idx:
                    arrays[array_name].append('')
                arrays[array_name][idx] = translated

        # Output plurals
        for name, items in plurals.items():
            lines.append(f'    <plurals name="{name}">')
            for quantity, text in items:
                escaped = self._escape_android(text)
                lines.append(f'        <item quantity="{quantity}">{escaped}</item>')
            lines.append('    </plurals>')

        # Output arrays
        for name, items in arrays.items():
            lines.append(f'    <string-array name="{name}">')
            for text in items:
                escaped = self._escape_android(text)
                lines.append(f'        <item>{escaped}</item>')
            lines.append('    </string-array>')

        lines.append('</resources>')
        return '\n'.join(lines)

    def validate_content(self, content: str) -> list[str]:
        """Validate Android XML format."""
        errors = []

        try:
            root = ET.fromstring(content)
            if root.tag != 'resources':
                errors.append(f"Root element must be 'resources', found '{root.tag}'")
        except ET.ParseError as e:
            errors.append(f"Invalid XML syntax: {e}")

        return errors
