#!/usr/bin/env python3
"""
SRT (SubRip) format handler.

Handles parsing and reconstruction of .srt subtitle files while preserving
timing information in metadata for accurate reconstruction.
"""

from .base import FormatHandler, TranslationEntry


class SrtHandler(FormatHandler):
    """
    Handler for SubRip subtitle (.srt) files.

    SRT format structure:
    ```
    1
    00:00:00,160 --> 00:00:05,120
    First subtitle text
    can be multi-line

    2
    00:00:05,200 --> 00:00:10,779
    Second subtitle text
    ```

    The handler preserves timing information in entry metadata for accurate
    reconstruction after translation.
    """

    @property
    def name(self) -> str:
        return "srt"

    @property
    def file_extensions(self) -> list[str]:
        return ["srt"]

    @property
    def supports_context(self) -> bool:
        """SRT benefits from temporal context to maintain translation consistency."""
        return True

    def parse(self, content: str) -> list[TranslationEntry]:
        """
        Parse SRT content into translation entries.

        Uses a state machine approach to handle blank lines within subtitle text.
        A new subtitle block is detected when:
        1. Line is a sequence number (digits only)
        2. Next line contains " --> " (timing line)

        This preserves intentional blank lines within subtitle text (e.g., poetry,
        dramatic pauses) that would otherwise be lost with simple \n\n splitting.

        Args:
            content: Raw SRT file content

        Returns:
            List of TranslationEntry with timing metadata
        """
        entries = []
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            # Skip empty lines between blocks
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            if i >= len(lines):
                break

            # Try to parse sequence number
            try:
                index = int(lines[i].strip())
            except ValueError:
                i += 1
                continue

            i += 1
            if i >= len(lines):
                break

            # Parse timing line
            timing_line = lines[i].strip()
            if " --> " not in timing_line:
                continue

            time_parts = timing_line.split(" --> ")
            if len(time_parts) != 2:
                i += 1
                continue

            start_time = time_parts[0].strip()
            end_time = time_parts[1].strip()
            i += 1

            # Collect text lines until we hit the next subtitle block
            # A new block starts with: empty line(s) followed by a number, then timing
            text_lines = []
            while i < len(lines):
                current_line = lines[i]

                # Check if this could be the start of a new subtitle block
                # We need to look ahead: is this line a number AND is the next line a timing?
                if current_line.strip() == "":
                    # Check if after this blank line, there's a new subtitle block
                    # Look ahead to find next non-empty line
                    lookahead = i + 1
                    while lookahead < len(lines) and lines[lookahead].strip() == "":
                        lookahead += 1

                    if lookahead < len(lines):
                        potential_index = lines[lookahead].strip()
                        # Check if it's a sequence number followed by timing
                        if potential_index.isdigit() and lookahead + 1 < len(lines):
                            next_line = lines[lookahead + 1].strip()
                            if " --> " in next_line:
                                # This blank line is a block separator, stop collecting text
                                break

                    # This blank line is part of the subtitle text
                    text_lines.append("")
                else:
                    text_lines.append(current_line)

                i += 1

            # Remove trailing empty lines from text (they're block separators)
            while text_lines and text_lines[-1] == "":
                text_lines.pop()

            text = "\n".join(text_lines)

            if text:  # Only add entries with actual text
                entries.append(TranslationEntry(
                    id=str(index),
                    text=text,
                    context=None,  # SRT uses temporal context instead
                    metadata={
                        'index': index,
                        'start_time': start_time,
                        'end_time': end_time,
                    }
                ))

        return entries

    def reconstruct(
        self,
        entries: list[TranslationEntry],
        translations: dict[str, str],
    ) -> str:
        """
        Reconstruct SRT file from entries and translations.

        Args:
            entries: Original TranslationEntry objects with timing metadata
            translations: Map of entry_id -> translated_text

        Returns:
            Complete SRT file content
        """
        output_lines = []

        for entry in entries:
            # Get translated text or fall back to original
            translated_text = translations.get(entry.id, entry.text)

            # Get timing from metadata
            index = entry.metadata.get('index', entry.id)
            start_time = entry.metadata.get('start_time', '00:00:00,000')
            end_time = entry.metadata.get('end_time', '00:00:01,000')

            # Reconstruct SRT block
            srt_block = f"{index}\n{start_time} --> {end_time}\n{translated_text}\n"
            output_lines.append(srt_block)

        return "\n".join(output_lines)

    def validate_content(self, content: str) -> list[str]:
        """
        Validate SRT file format.

        Uses the same state machine logic as parse() to correctly handle
        blank lines within subtitle text.

        Args:
            content: Raw SRT content

        Returns:
            List of validation error messages
        """
        errors = []
        lines = content.split("\n")
        block_count = 0

        i = 0
        while i < len(lines):
            # Skip empty lines between blocks
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            if i >= len(lines):
                break

            block_count += 1

            # Check index
            index_line = lines[i].strip()
            try:
                int(index_line)
            except ValueError:
                errors.append(f"Block {block_count}: Invalid index '{index_line}'")
                i += 1
                continue

            i += 1
            if i >= len(lines):
                errors.append(f"Block {block_count}: Missing timing line")
                break

            # Check timing
            timing_line = lines[i].strip()
            if " --> " not in timing_line:
                errors.append(f"Block {block_count}: Invalid timing format '{timing_line}'")

            i += 1

            # Skip text lines until next block (using same lookahead logic as parse)
            has_text = False
            while i < len(lines):
                current_line = lines[i]

                if current_line.strip() == "":
                    # Look ahead to check for new block
                    lookahead = i + 1
                    while lookahead < len(lines) and lines[lookahead].strip() == "":
                        lookahead += 1

                    if lookahead < len(lines):
                        potential_index = lines[lookahead].strip()
                        if potential_index.isdigit() and lookahead + 1 < len(lines):
                            next_line = lines[lookahead + 1].strip()
                            if " --> " in next_line:
                                break
                else:
                    has_text = True

                i += 1

            if not has_text:
                errors.append(f"Block {block_count}: Missing subtitle text")

        return errors
