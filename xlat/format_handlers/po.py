#!/usr/bin/env python3
"""
GNU gettext PO/POT format handler.

Handles parsing and reconstruction of .po and .pot files used by
WordPress, Django, Rails (via gettext), and many Linux applications.
"""

import re
from typing import Optional

from .base import FormatHandler, TranslationEntry, PlaceholderPattern, PLACEHOLDER_PATTERNS


class PoHandler(FormatHandler):
    """
    Handler for GNU gettext PO/POT files.

    PO format structure:
    ```
    # Translator comment
    #. Extracted comment
    #: file.py:42
    #, fuzzy
    msgctxt "context"
    msgid "Source text"
    msgstr "Translated text"

    # Plural form
    msgid "One item"
    msgid_plural "%d items"
    msgstr[0] "Un élément"
    msgstr[1] "%d éléments"
    ```

    Preserves comments, context, and plural forms in metadata.
    """

    def __init__(self):
        """Initialize handler with empty header metadata."""
        self._header_metadata: str = ""
        self._header_comments: list[str] = []

    @property
    def name(self) -> str:
        return "po"

    @property
    def file_extensions(self) -> list[str]:
        return ["po", "pot"]

    @property
    def supports_context(self) -> bool:
        """PO files have built-in comment context."""
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        """PO files use printf-style placeholders."""
        return [
            PLACEHOLDER_PATTERNS['printf'],       # %s, %d
            PLACEHOLDER_PATTERNS['printf_named'], # %(name)s
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse PO content into translation entries.

        Args:
            content: Raw PO file content

        Returns:
            List of TranslationEntry objects
        """
        entries = []
        current_entry = self._new_entry_dict()

        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].rstrip()

            # Skip empty lines between entries
            if not line:
                if current_entry['msgid'] is not None:
                    entry = self._create_entry(current_entry)
                    if entry:
                        entries.append(entry)
                    current_entry = self._new_entry_dict()
                i += 1
                continue

            # Translator comment
            if line.startswith('#') and not line.startswith('#,') and not line.startswith('#:') and not line.startswith('#.') and not line.startswith('#|'):
                current_entry['translator_comment'].append(line[1:].strip())

            # Extracted comment
            elif line.startswith('#.'):
                current_entry['extracted_comment'].append(line[2:].strip())

            # Reference
            elif line.startswith('#:'):
                current_entry['reference'].append(line[2:].strip())

            # Flags
            elif line.startswith('#,'):
                flags = line[2:].strip().split(',')
                current_entry['flags'].extend([f.strip() for f in flags])

            # Context
            elif line.startswith('msgctxt'):
                current_entry['msgctxt'] = self._extract_string(line, 'msgctxt')
                # Handle multi-line
                i, current_entry['msgctxt'] = self._read_multiline(
                    lines, i, current_entry['msgctxt']
                )

            # Source text
            elif line.startswith('msgid '):
                current_entry['msgid'] = self._extract_string(line, 'msgid')
                i, current_entry['msgid'] = self._read_multiline(
                    lines, i, current_entry['msgid']
                )

            # Plural source
            elif line.startswith('msgid_plural'):
                current_entry['msgid_plural'] = self._extract_string(line, 'msgid_plural')
                i, current_entry['msgid_plural'] = self._read_multiline(
                    lines, i, current_entry['msgid_plural']
                )

            # Translation
            elif line.startswith('msgstr '):
                current_entry['msgstr'] = self._extract_string(line, 'msgstr')
                i, current_entry['msgstr'] = self._read_multiline(
                    lines, i, current_entry['msgstr']
                )

            # Plural translations
            elif line.startswith('msgstr['):
                match = re.match(r'msgstr\[(\d+)\]', line)
                if match:
                    idx = int(match.group(1))
                    value = self._extract_string(line, f'msgstr[{idx}]')
                    i, value = self._read_multiline(lines, i, value)
                    current_entry['msgstr_plural'][idx] = value

            i += 1

        # Don't forget the last entry
        if current_entry['msgid'] is not None:
            entry = self._create_entry(current_entry)
            if entry:
                entries.append(entry)

        return entries

    def _new_entry_dict(self) -> dict:
        """Create empty entry dictionary."""
        return {
            'translator_comment': [],
            'extracted_comment': [],
            'reference': [],
            'flags': [],
            'msgctxt': None,
            'msgid': None,
            'msgid_plural': None,
            'msgstr': None,
            'msgstr_plural': {},
        }

    def _extract_string(self, line: str, prefix: str) -> str:
        """Extract string value from PO line."""
        # Remove prefix and get quoted content
        content = line[len(prefix):].strip()
        if content.startswith('"') and content.endswith('"'):
            return self._unescape_po_string(content[1:-1])
        return ""

    def _read_multiline(
        self, lines: list[str], start: int, initial: str
    ) -> tuple[int, str]:
        """Read continuation lines for multi-line strings."""
        result = initial
        i = start + 1

        while i < len(lines):
            line = lines[i].rstrip()
            if line.startswith('"') and line.endswith('"'):
                result += self._unescape_po_string(line[1:-1])
                i += 1
            else:
                break

        return i - 1, result

    def _unescape_po_string(self, s: str) -> str:
        """Unescape PO string escapes."""
        return (
            s.replace('\\n', '\n')
            .replace('\\t', '\t')
            .replace('\\"', '"')
            .replace('\\\\', '\\')
        )

    def _escape_po_string(self, s: str) -> str:
        """Escape string for PO format."""
        return (
            s.replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\t', '\\t')
        )

    def _format_po_string(self, prefix: str, s: str, wrap_width: int = 76) -> list[str]:
        """
        Format a string for PO output, wrapping long strings at ~76 characters.

        Args:
            prefix: The PO prefix (e.g., 'msgid', 'msgstr', 'msgstr[0]')
            s: The string to format
            wrap_width: Maximum line width for wrapping (default: 76)

        Returns:
            List of formatted lines
        """
        # Handle None or empty strings
        if s is None:
            s = ""
        escaped = self._escape_po_string(s)

        # If short enough, output on single line
        # Account for prefix + space + two quotes
        single_line = f'{prefix} "{escaped}"'
        if len(single_line) <= wrap_width:
            return [single_line]

        # For longer strings, use continuation format:
        # msgid ""
        # "first part "
        # "second part"
        lines = [f'{prefix} ""']

        # Split by escaped newlines first to preserve line breaks
        segments = escaped.split('\\n')

        for i, segment in enumerate(segments):
            # Add back the \n except for the last segment
            if i < len(segments) - 1:
                segment += '\\n'

            # If segment itself is too long, wrap it
            while segment:
                # Reserve space for quotes
                max_chunk = wrap_width - 2
                if len(segment) <= max_chunk:
                    if segment:  # Don't add empty strings
                        lines.append(f'"{segment}"')
                    break
                else:
                    # Find a good break point (prefer space)
                    break_at = max_chunk
                    # Look for space within last 20 chars
                    space_pos = segment.rfind(' ', max_chunk - 20, max_chunk)
                    if space_pos > 0:
                        break_at = space_pos + 1  # Include the space

                    chunk = segment[:break_at]
                    segment = segment[break_at:]
                    lines.append(f'"{chunk}"')

        return lines

    def _create_entry(self, entry_dict: dict) -> Optional[TranslationEntry]:
        """Create TranslationEntry from parsed dictionary."""
        msgid = entry_dict['msgid']

        # Store header entry (empty msgid) for later reconstruction
        if not msgid:
            # Store the header metadata (msgstr contains Plural-Forms, Project-Id-Version, etc.)
            if entry_dict['msgstr']:
                self._header_metadata = entry_dict['msgstr']
            # Store any translator comments from the header
            if entry_dict['translator_comment']:
                self._header_comments = entry_dict['translator_comment']
            return None

        # Create unique ID
        if entry_dict['msgctxt']:
            entry_id = f"{entry_dict['msgctxt']}|{msgid}"
        else:
            entry_id = msgid

        # Build context from comments
        context_parts = []
        if entry_dict['extracted_comment']:
            context_parts.extend(entry_dict['extracted_comment'])
        if entry_dict['reference']:
            context_parts.append(f"References: {', '.join(entry_dict['reference'])}")

        return TranslationEntry(
            id=entry_id,
            text=msgid,
            context='\n'.join(context_parts) if context_parts else None,
            metadata={
                'msgctxt': entry_dict['msgctxt'],
                'msgid_plural': entry_dict['msgid_plural'],
                'msgstr': entry_dict['msgstr'],
                'msgstr_plural': entry_dict['msgstr_plural'],
                'translator_comment': entry_dict['translator_comment'],
                'extracted_comment': entry_dict['extracted_comment'],
                'reference': entry_dict['reference'],
                'flags': entry_dict['flags'],
                'placeholders': self.extract_placeholders(msgid),
            }
        )

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct PO file from entries and translations.

        Args:
            entries: Original TranslationEntry objects
            translations: Map of entry_id -> translated_text

        Returns:
            Complete PO file content
        """
        lines = []

        # Add header - restore original metadata if available
        # Header comments (if any)
        for comment in self._header_comments:
            lines.append(f'# {comment}')

        lines.append('msgid ""')

        if self._header_metadata:
            # Restore the original header with all metadata (Plural-Forms, Project-Id-Version, etc.)
            # Format as multi-line PO string
            lines.append('msgstr ""')
            for header_line in self._header_metadata.split('\n'):
                if header_line:  # Skip empty lines
                    lines.append(f'"{self._escape_po_string(header_line)}\\n"')
        else:
            # Fallback to minimal header if no original header was found
            lines.append('msgstr ""')
            lines.append('"Content-Type: text/plain; charset=UTF-8\\n"')

        lines.append('')

        for entry in entries:
            # Translator comments
            for comment in entry.metadata.get('translator_comment', []):
                lines.append(f'# {comment}')

            # Extracted comments
            for comment in entry.metadata.get('extracted_comment', []):
                lines.append(f'#. {comment}')

            # References
            for ref in entry.metadata.get('reference', []):
                lines.append(f'#: {ref}')

            # Flags
            flags = entry.metadata.get('flags', [])
            if flags:
                lines.append(f'#, {", ".join(flags)}')

            # Context
            msgctxt = entry.metadata.get('msgctxt')
            if msgctxt:
                lines.extend(self._format_po_string('msgctxt', msgctxt))

            # Source
            lines.extend(self._format_po_string('msgid', entry.text))

            # Plural source
            msgid_plural = entry.metadata.get('msgid_plural')
            if msgid_plural:
                lines.extend(self._format_po_string('msgid_plural', msgid_plural))

            # Translation(s)
            translated = translations.get(entry.id, entry.metadata.get('msgstr', '')) or ''

            if msgid_plural:
                # Plural translations
                msgstr_plural = entry.metadata.get('msgstr_plural', {})
                # Use translated text for [0] if provided, else original msgstr_plural[0]
                msgstr_0 = translated if translated else msgstr_plural.get(0, '')
                lines.extend(self._format_po_string('msgstr[0]', msgstr_0))
                for idx in sorted(k for k in msgstr_plural.keys() if k > 0):
                    orig = msgstr_plural.get(idx, '')
                    lines.extend(self._format_po_string(f'msgstr[{idx}]', orig))
            else:
                lines.extend(self._format_po_string('msgstr', translated))

            lines.append('')

        return '\n'.join(lines)

    def validate_content(self, content: str) -> list[str]:
        """Validate PO file format."""
        errors = []

        if 'msgid' not in content:
            errors.append("No msgid entries found")

        # Check for unmatched quotes
        for i, line in enumerate(content.split('\n'), 1):
            if line.startswith(('msgid', 'msgstr', 'msgctxt')):
                quote_count = line.count('"') - line.count('\\"')
                if quote_count % 2 != 0:
                    errors.append(f"Line {i}: Unmatched quotes")

        return errors
