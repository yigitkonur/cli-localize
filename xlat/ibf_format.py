#!/usr/bin/env python3
"""
IBF (Indexed Block Format) - LLM-Optimized Subtitle Translation Format

Token-efficient, hallucination-resistant format for agent-driven subtitle translation.
~24% fewer tokens than JSON while maintaining strict structure validation.

Format:
    #TRANSLATE:v1:{src}>{tgt}:batch={n}/{total}:entries={count}:ctx={context_size}
    @context_before
    [id] Previous context text...
    @translate
    [id] Entry to translate
    @context_after
    [id] Following context text...
    ---
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IBFMetadata:
    """Metadata parsed from IBF header."""
    version: str = "v1"
    src_lang: str = "en"
    tgt_lang: str = "tr"
    batch_num: int = 1
    total_batches: int = 1
    entry_count: int = 0
    context_size: int = 10
    status: str = "ok"


@dataclass
class IBFEntry:
    """Single entry in IBF format. Supports both integer and string IDs."""
    id: str  # Can be integer (SRT) or dotted string (JSON) or msgid (PO)
    text: str

    def __post_init__(self):
        """Ensure id is always a string."""
        self.id = str(self.id)


class IBFEncoder:
    """Encode SRT entries to IBF format for LLM translation."""

    HEADER_TEMPLATE = "#TRANSLATE:v1:{src}>{tgt}:batch={batch}/{total}:entries={count}:ctx={ctx}"

    def __init__(self, context_size: int = 10):
        """
        Initialize encoder.

        Args:
            context_size: Number of entries to include before/after for context
        """
        self.context_size = context_size

    def encode_batch(
        self,
        entries_to_translate: list[IBFEntry],
        context_before: list[IBFEntry],
        context_after: list[IBFEntry],
        src_lang: str = "en",
        tgt_lang: str = "tr",
        batch_num: int = 1,
        total_batches: int = 1,
    ) -> str:
        """
        Encode a batch of entries to IBF format.

        Args:
            entries_to_translate: Entries that need translation
            context_before: Preceding entries for context (read-only)
            context_after: Following entries for context (read-only)
            src_lang: Source language code
            tgt_lang: Target language code
            batch_num: Current batch number
            total_batches: Total number of batches

        Returns:
            IBF formatted string ready for LLM
        """
        lines = []

        # Header
        header = self.HEADER_TEMPLATE.format(
            src=src_lang,
            tgt=tgt_lang,
            batch=batch_num,
            total=total_batches,
            count=len(entries_to_translate),
            ctx=self.context_size,
        )
        lines.append(header)

        # Context before
        if context_before:
            lines.append("@context_before")
            for entry in context_before:
                lines.append(self._format_entry(entry))

        # Entries to translate
        lines.append("@translate")
        for entry in entries_to_translate:
            lines.append(self._format_entry(entry))

        # Context after
        if context_after:
            lines.append("@context_after")
            for entry in context_after:
                lines.append(self._format_entry(entry))

        # End delimiter
        lines.append("---")

        return "\n".join(lines)

    def _format_entry(self, entry: IBFEntry) -> str:
        """Format single entry as [id] text.

        Escapes newlines in both ID and text to keep IBF entries on single lines
        while preserving multiline content (BUG 2 + BUG 3 fix).
        """
        # Escape newlines in ID (for PO msgid with embedded newlines - BUG 2)
        escaped_id = entry.id.replace("\n", "\\n")
        # Escape newlines in text (for SRT multiline subtitles - BUG 3)
        escaped_text = entry.text.replace("\n", "\\n")
        return f"[{escaped_id}] {escaped_text}"

    @staticmethod
    def from_srt_entries(srt_entries: list) -> list[IBFEntry]:
        """Convert SRT entries to IBF entries."""
        return [IBFEntry(id=e.index, text=e.text) for e in srt_entries]


@dataclass
class ValidationError:
    """Structured validation error for agent-friendly reporting."""
    line_num: int
    error_type: str
    message: str
    suggestion: str

    def to_dict(self) -> dict:
        return {
            "line": self.line_num,
            "type": self.error_type,
            "message": self.message,
            "fix": self.suggestion,
        }


class IBFDecoder:
    """Decode IBF translated output back to structured data."""

    # Regex patterns
    HEADER_PATTERN = re.compile(
        r"#TRANSLATED:v1:batch=(\d+)/(\d+):count=(\d+):status=(\w+)"
    )
    # Entry pattern supports both integer IDs (SRT) and string IDs (JSON, PO, etc.)
    # [123] text  or  [user.greeting] text  or  [buttons.submit] text
    # Changed .+ to .* to allow empty text after ID (BUG 1 fix)
    ENTRY_PATTERN = re.compile(r"\[([^\]]+)\]\s*(.*)")
    SECTION_PATTERN = re.compile(r"@(context_before|translate|context_after)")

    def validate_file_format(self, content: str) -> tuple[bool, list[ValidationError]]:
        """
        Comprehensive file format validation with line numbers.

        Args:
            content: Raw file content

        Returns:
            Tuple of (is_valid, list of ValidationError)
        """
        errors = []
        lines = content.strip().split("\n")

        if not lines or not content.strip():
            errors.append(ValidationError(
                line_num=1,
                error_type="EMPTY_FILE",
                message="File is empty",
                suggestion="File must contain #TRANSLATED header, entries, and --- delimiter"
            ))
            return False, errors

        # Check header (line 1)
        if not lines[0].startswith("#TRANSLATED:"):
            errors.append(ValidationError(
                line_num=1,
                error_type="MISSING_HEADER",
                message=f"Invalid header: '{lines[0][:50]}...'",
                suggestion="First line must be: #TRANSLATED:v1:batch=N/M:count=X:status=ok"
            ))
        else:
            # Validate header format
            if not self.HEADER_PATTERN.match(lines[0]):
                errors.append(ValidationError(
                    line_num=1,
                    error_type="INVALID_HEADER",
                    message=f"Header format incorrect: '{lines[0]}'",
                    suggestion="Header must match: #TRANSLATED:v1:batch=N/M:count=X:status=ok"
                ))

        # Check for delimiter
        has_delimiter = False
        delimiter_line = None
        for i, line in enumerate(lines, 1):
            if line.strip() == "---":
                has_delimiter = True
                delimiter_line = i
                break

        if not has_delimiter:
            errors.append(ValidationError(
                line_num=len(lines),
                error_type="MISSING_DELIMITER",
                message="Missing end delimiter '---'",
                suggestion="File must end with a line containing only '---'"
            ))

        # Check entries (lines between header and delimiter)
        entry_start = 2 if lines[0].startswith("#TRANSLATED:") else 1
        entry_end = delimiter_line - 1 if delimiter_line else len(lines)

        found_entries = 0
        for i in range(entry_start - 1, entry_end):
            if i >= len(lines):
                break
            # Use rstrip('\n') instead of strip() to preserve trailing spaces (BUG 1 fix)
            line = lines[i].rstrip('\n')
            if not line.strip():
                continue  # Allow blank lines

            # Check entry format
            if not self.ENTRY_PATTERN.match(line):
                # Check if it looks like a malformed entry
                if line.startswith("[") or line[0].isdigit():
                    errors.append(ValidationError(
                        line_num=i + 1,
                        error_type="MALFORMED_ENTRY",
                        message=f"Invalid entry format: '{line[:60]}...'",
                        suggestion="Entries must be: [ID] translated text"
                    ))
                # Ignore other lines (comments, etc.)
            else:
                found_entries += 1
                # Empty translations are now allowed (BUG 1 fix)
                # Some use cases require empty strings to be valid translations

        # Check for content after delimiter
        if delimiter_line and delimiter_line < len(lines):
            extra_content = "\n".join(lines[delimiter_line:]).strip()
            if extra_content:
                errors.append(ValidationError(
                    line_num=delimiter_line + 1,
                    error_type="EXTRA_CONTENT",
                    message="Content found after '---' delimiter",
                    suggestion="Remove all content after the '---' delimiter"
                ))

        return len(errors) == 0, errors

    def decode(self, ibf_string: str) -> tuple[IBFMetadata, list[IBFEntry]]:
        """
        Decode IBF translated output.

        Args:
            ibf_string: IBF formatted response from LLM

        Returns:
            Tuple of (metadata, list of translated entries)

        Raises:
            ValueError: If format is invalid
        """
        lines = ibf_string.strip().split("\n")
        metadata = IBFMetadata()
        entries = []

        # Parse header
        if lines and lines[0].startswith("#TRANSLATED:"):
            match = self.HEADER_PATTERN.match(lines[0])
            if match:
                metadata.batch_num = int(match.group(1))
                metadata.total_batches = int(match.group(2))
                metadata.entry_count = int(match.group(3))
                metadata.status = match.group(4)

        # Parse entries (skip header and delimiter)
        for line in lines[1:]:
            line = line.strip()
            if line == "---" or line.startswith("#") or line.startswith("@"):
                continue

            match = self.ENTRY_PATTERN.match(line)
            if match:
                # Unescape newlines in ID and text (BUG 2 + BUG 3 fix)
                entry_id = match.group(1).strip().replace("\\n", "\n")
                text = match.group(2).strip().replace("\\n", "\n")
                entries.append(IBFEntry(id=entry_id, text=text))

        return metadata, entries

    def validate(
        self,
        original_ids: list,  # Can be int or str IDs
        decoded_entries: list[IBFEntry],
        expected_batch: int = None,
        expected_total: int = None,
        metadata: IBFMetadata = None,
    ) -> tuple[bool, list[ValidationError]]:
        """
        Validate decoded output against original input.

        Args:
            original_ids: List of entry IDs that were sent for translation (int or str)
            decoded_entries: Entries decoded from LLM response
            expected_batch: Expected batch number (optional)
            expected_total: Expected total batches (optional)
            metadata: Parsed metadata from header (optional)

        Returns:
            Tuple of (is_valid, list of ValidationError)
        """
        errors = []
        # Normalize IDs to strings for comparison
        original_ids_str = [str(id) for id in original_ids]
        decoded_ids = [str(e.id) for e in decoded_entries]

        # Check batch number if provided
        if expected_batch and metadata and metadata.batch_num != expected_batch:
            errors.append(ValidationError(
                line_num=1,
                error_type="BATCH_MISMATCH",
                message=f"Batch number mismatch: expected {expected_batch}, got {metadata.batch_num}",
                suggestion=f"Header should have batch={expected_batch}/{expected_total or '?'}"
            ))

        # Check count match
        if len(original_ids) != len(decoded_ids):
            errors.append(ValidationError(
                line_num=0,
                error_type="COUNT_MISMATCH",
                message=f"Entry count mismatch: expected {len(original_ids)}, got {len(decoded_ids)}",
                suggestion=f"File must contain exactly {len(original_ids)} entries with IDs: {original_ids}"
            ))

        # Check ID match
        missing_ids = set(original_ids_str) - set(decoded_ids)
        if missing_ids:
            errors.append(ValidationError(
                line_num=0,
                error_type="MISSING_IDS",
                message=f"Missing entry IDs: {sorted(missing_ids)}",
                suggestion=f"Add entries for IDs: {sorted(missing_ids)}"
            ))

        extra_ids = set(decoded_ids) - set(original_ids_str)
        if extra_ids:
            errors.append(ValidationError(
                line_num=0,
                error_type="HALLUCINATED_IDS",
                message=f"Extra/hallucinated entry IDs: {sorted(extra_ids)}",
                suggestion=f"Remove entries with IDs: {sorted(extra_ids)} - these were not requested"
            ))

        # Empty translations are now allowed (BUG 1 fix)
        # Some use cases require empty strings to be valid translations

        # Check header count matches actual count
        if metadata and metadata.entry_count != len(decoded_ids):
            errors.append(ValidationError(
                line_num=1,
                error_type="HEADER_COUNT_MISMATCH",
                message=f"Header declares count={metadata.entry_count} but file has {len(decoded_ids)} entries",
                suggestion=f"Update header to count={len(decoded_ids)} or fix entry count"
            ))

        return len(errors) == 0, errors

    def extract_from_response(self, llm_response: str) -> str:
        """
        Extract IBF block from potentially messy LLM response.

        Args:
            llm_response: Raw LLM response that may contain extra text

        Returns:
            Clean IBF string
        """
        # Find start marker
        start_idx = llm_response.find("#TRANSLATED:")
        if start_idx == -1:
            # Fallback: look for first entry pattern
            match = self.ENTRY_PATTERN.search(llm_response)
            if match:
                start_idx = match.start()
            else:
                return llm_response  # Return as-is, let validation catch errors

        # Find end marker
        end_idx = llm_response.find("---", start_idx)
        if end_idx != -1:
            return llm_response[start_idx:end_idx + 3]

        return llm_response[start_idx:]


def create_translation_prompt(ibf_input: str, target_language: str = "Turkish") -> str:
    """
    Create a complete prompt for LLM translation.

    Args:
        ibf_input: IBF formatted input
        target_language: Target language name

    Returns:
        Complete prompt string
    """
    return f"""Translate the subtitle entries to {target_language}.

INPUT FORMAT:
- @context_before: Previous entries (read-only, for understanding context)
- @translate: Entries you MUST translate
- @context_after: Following entries (read-only, for understanding context)

OUTPUT FORMAT:
Return ONLY the translated entries in this exact format:
#TRANSLATED:v1:batch={{batch_num}}/{{total}}:count={{count}}:status=ok
[id] Translated text
[id+1] Another translated text
---

RULES:
1. Translate ONLY entries under @translate
2. Preserve exact entry IDs [50], [51], etc.
3. Output count MUST match input count
4. Do NOT add explanations or extra text
5. Use context to maintain sentence flow

INPUT:
{ibf_input}

OUTPUT:"""


# Example usage
if __name__ == "__main__":
    # Example encoding
    encoder = IBFEncoder(context_size=3)

    entries = [
        IBFEntry(50, "Hello, how are you?"),
        IBFEntry(51, "I'm doing great, thanks!"),
        IBFEntry(52, "Let's get started."),
    ]
    context_before = [
        IBFEntry(47, "Welcome to the show."),
        IBFEntry(48, "Today we have a special guest."),
        IBFEntry(49, "Please welcome John!"),
    ]
    context_after = [
        IBFEntry(53, "First, let me explain..."),
        IBFEntry(54, "The concept is simple."),
        IBFEntry(55, "Just follow along."),
    ]

    ibf_output = encoder.encode_batch(
        entries_to_translate=entries,
        context_before=context_before,
        context_after=context_after,
        batch_num=1,
        total_batches=10,
    )

    print("=== IBF ENCODED ===")
    print(ibf_output)
    print()

    # Example decoding
    decoder = IBFDecoder()

    sample_response = """#TRANSLATED:v1:batch=1/10:count=3:status=ok
[50] Merhaba, nasilsin?
[51] Cok iyiyim, tesekkurler!
[52] Hadi baslayalim.
---"""

    metadata, decoded = decoder.decode(sample_response)
    is_valid, errors = decoder.validate([50, 51, 52], decoded)

    print("=== IBF DECODED ===")
    print(f"Metadata: batch={metadata.batch_num}/{metadata.total_batches}, status={metadata.status}")
    print(f"Entries: {[(e.id, e.text) for e in decoded]}")
    print(f"Valid: {is_valid}, Errors: {errors}")
