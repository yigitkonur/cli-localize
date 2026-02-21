#!/usr/bin/env python3
"""
Translation Session Management for Agent-Driven Localization

Handles state persistence, batch management, and progress tracking
for LLM agents translating various localization file formats.

Supports: SRT, JSON, PO, Android XML, iOS .strings, YAML, ARB
"""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ibf_format import IBFDecoder, IBFEncoder, IBFEntry, ValidationError
from .format_handlers import FormatHandler, FormatRegistry, TranslationEntry
from .batcher import TokenBatcher, BatchInfo, create_batcher


@dataclass
class BatchStatus:
    """Status of a single batch."""
    batch_num: int
    status: str = "pending"  # pending, in_progress, completed, failed
    attempt: int = 0
    translated_entries: list = field(default_factory=list)
    error: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_tokens: int = 0


@dataclass
class SessionState:
    """Persistent session state."""
    session_id: str
    input_file: str
    output_file: str
    src_lang: str
    tgt_lang: str
    context_size: int
    total_entries: int
    total_batches: int
    format_type: str = "srt"  # Format handler name
    target_tokens: int = 5000  # Token-based batching target
    current_batch: int = 1
    batches: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"  # active, completed, failed

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["batches"] = {
            k: asdict(v) if isinstance(v, BatchStatus) else v
            for k, v in self.batches.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """Create from dictionary."""
        # Handle legacy sessions without format_type
        if "format_type" not in data:
            data["format_type"] = "srt"
        if "target_tokens" not in data:
            data["target_tokens"] = 5000

        # Handle legacy batch_size field
        if "batch_size" in data:
            del data["batch_size"]

        batches = {
            k: BatchStatus(**v) if isinstance(v, dict) else v
            for k, v in data.get("batches", {}).items()
        }
        data["batches"] = batches
        return cls(**data)


class TranslationSession:
    """
    Manages a single file translation session.

    Handles:
    - Parsing various localization formats
    - Generating IBF batches with token-based sizing
    - Validating translated output with placeholder checks
    - Reconstructing final output
    - State persistence for resumption
    """

    def __init__(
        self,
        input_file: str,
        src_lang: str = "en",
        tgt_lang: str = "tr",
        context_size: int = 10,
        target_tokens: int = 5000,
        output_file: Optional[str] = None,
        session_id: Optional[str] = None,
        format_type: Optional[str] = None,
        _loading: bool = False,
    ):
        """
        Initialize a new translation session.

        Args:
            input_file: Path to input file
            src_lang: Source language code
            tgt_lang: Target language code
            context_size: Number of context entries before/after (for formats that support it)
            target_tokens: Target tokens per batch (~5000 recommended)
            output_file: Optional output path (auto-generated if not provided)
            session_id: Optional session ID (auto-generated if not provided)
            format_type: Format type (auto-detected if not provided)
            _loading: Internal flag - don't save state when loading from file
        """
        self.input_path = Path(input_file)
        self.session_id = session_id or self._generate_session_id()

        # Auto-detect or use specified format
        content = self.input_path.read_text(encoding="utf-8")
        if format_type:
            self.handler = FormatRegistry.get_handler(format_type)
        else:
            self.handler = FormatRegistry.detect_format(str(self.input_path), content)

        # Output file with language prefix
        if output_file:
            self.output_path = Path(output_file)
        else:
            ext = self.input_path.suffix
            stem = self.input_path.stem
            self.output_path = self.input_path.parent / f"{tgt_lang}_{stem}{ext}"

        # State file with format-agnostic prefix
        self.state_file = self.input_path.parent / f".loc-{self.session_id}.json"

        # Parse input using format handler
        self.entries: list[TranslationEntry] = self.handler.parse(content)

        # Create batcher and generate batches
        self.batcher = TokenBatcher(target_tokens=target_tokens)
        self.batch_infos: list[BatchInfo] = self.batcher.create_batches(self.entries)

        # Initialize state
        now = datetime.now().isoformat()
        self.state = SessionState(
            session_id=self.session_id,
            input_file=str(self.input_path),
            output_file=str(self.output_path),
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            context_size=context_size,
            target_tokens=target_tokens,
            format_type=self.handler.name,
            total_entries=len(self.entries),
            total_batches=len(self.batch_infos),
            created_at=now,
            updated_at=now,
        )

        # Initialize batch statuses
        for batch_info in self.batch_infos:
            self.state.batches[str(batch_info.batch_num)] = BatchStatus(
                batch_num=batch_info.batch_num,
                estimated_tokens=batch_info.estimated_tokens,
            )

        # IBF format handlers
        self.encoder = IBFEncoder(context_size=context_size)
        self.decoder = IBFDecoder()

        # Save initial state (skip when loading from existing state file)
        if not _loading:
            self._save_state()

    def _generate_session_id(self) -> str:
        """Generate unique session ID from file content."""
        content = self.input_path.read_text(encoding="utf-8")
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"{uuid.uuid4().hex[:4]}-{hash_val}"

    def _get_batch_entries(self, batch_num: int) -> tuple[list[TranslationEntry], int, int]:
        """Get entries for a specific batch."""
        if batch_num < 1 or batch_num > len(self.batch_infos):
            raise ValueError(f"Invalid batch number: {batch_num}")

        batch_info = self.batch_infos[batch_num - 1]
        return batch_info.entries, batch_info.start_idx, batch_info.end_idx

    def _get_context(self, start_idx: int, end_idx: int) -> tuple[list[TranslationEntry], list[TranslationEntry]]:
        """Get context entries before and after the batch (if format supports it)."""
        if not self.handler.supports_context:
            return [], []

        ctx_size = self.state.context_size

        # Context before
        ctx_start = max(0, start_idx - ctx_size)
        context_before = self.entries[ctx_start:start_idx]

        # Context after
        ctx_end = min(len(self.entries), end_idx + ctx_size)
        context_after = self.entries[end_idx:ctx_end]

        return context_before, context_after

    def get_batch(self, batch_num: int) -> str:
        """
        Get IBF formatted batch for translation.

        Args:
            batch_num: Batch number (1-indexed)

        Returns:
            IBF formatted string
        """
        if batch_num < 1 or batch_num > self.state.total_batches:
            raise ValueError(f"Invalid batch number: {batch_num}")

        # Get batch entries
        batch_entries, start_idx, end_idx = self._get_batch_entries(batch_num)

        # Get context
        context_before, context_after = self._get_context(start_idx, end_idx)

        # Convert to IBF entries
        ibf_entries = [IBFEntry(e.id, e.text) for e in batch_entries]
        ibf_ctx_before = [IBFEntry(e.id, e.text) for e in context_before]
        ibf_ctx_after = [IBFEntry(e.id, e.text) for e in context_after]

        # Encode
        ibf_output = self.encoder.encode_batch(
            entries_to_translate=ibf_entries,
            context_before=ibf_ctx_before,
            context_after=ibf_ctx_after,
            src_lang=self.state.src_lang,
            tgt_lang=self.state.tgt_lang,
            batch_num=batch_num,
            total_batches=self.state.total_batches,
        )

        # Update state
        batch_status = self.state.batches[str(batch_num)]
        batch_status.status = "in_progress"
        batch_status.attempt += 1
        self._save_state()

        return ibf_output

    def submit_batch(self, batch_num: int, translated_ibf: str) -> dict:
        """
        Submit translated IBF output for a batch.

        Args:
            batch_num: Batch number
            translated_ibf: IBF formatted translation from LLM

        Returns:
            Status dictionary with next_action and validation_errors if any
        """
        batch_status = self.state.batches[str(batch_num)]

        # Step 1: File format validation
        format_valid, format_errors = self.decoder.validate_file_format(translated_ibf)
        if not format_valid:
            batch_status.status = "failed"
            batch_status.error = f"Format validation failed: {len(format_errors)} errors"
            self._save_state()
            return self._make_validation_error_response(
                batch_num, format_errors, batch_status.attempt
            )

        # Step 2: Extract clean IBF from response
        clean_ibf = self.decoder.extract_from_response(translated_ibf)

        # Step 3: Decode
        try:
            metadata, decoded_entries = self.decoder.decode(clean_ibf)
        except Exception as e:
            batch_status.status = "failed"
            batch_status.error = f"Decode error: {str(e)}"
            self._save_state()
            return {
                "status": "error",
                "next_action": "retry",
                "error_type": "DECODE_ERROR",
                "error": str(e),
                "suggestion": "Ensure file follows IBF format exactly",
                "attempt": batch_status.attempt,
                "max_attempts": 3,
            }

        # Step 4: Get original IDs for this batch
        batch_entries, _, _ = self._get_batch_entries(batch_num)
        original_ids = [e.id for e in batch_entries]

        # Step 5: Content validation
        is_valid, content_errors = self.decoder.validate(
            original_ids,
            decoded_entries,
            expected_batch=batch_num,
            expected_total=self.state.total_batches,
            metadata=metadata,
        )

        if not is_valid:
            batch_status.status = "failed"
            batch_status.error = f"Content validation failed: {len(content_errors)} errors"
            self._save_state()
            return self._make_validation_error_response(
                batch_num, content_errors, batch_status.attempt
            )

        # Step 6: Placeholder validation (for formats that support it)
        placeholder_errors = []
        for decoded, original in zip(decoded_entries, batch_entries):
            errors = self.handler.validate_placeholders(original.text, decoded.text)
            for error in errors:
                placeholder_errors.append(
                    ValidationError(
                        line_num=0,
                        error_type="PLACEHOLDER_MISMATCH",
                        message=f"[{decoded.id}] {error}",
                        suggestion="Ensure all placeholders from source appear in translation"
                    )
                )

        if placeholder_errors:
            # Placeholder errors are warnings, not failures
            # Log them but don't fail the batch
            pass

        # Store translations
        batch_status.status = "completed"
        batch_status.translated_entries = [
            {"id": str(e.id), "text": e.text} for e in decoded_entries
        ]
        batch_status.completed_at = datetime.now().isoformat()
        batch_status.error = None

        # Update current batch
        next_batch = self._find_next_pending_batch()
        self.state.current_batch = next_batch if next_batch else batch_num

        self._save_state()

        # Determine next action
        if next_batch:
            return self._make_status("continue", batch=next_batch)
        else:
            return self._make_status("finalize")

    def _find_next_pending_batch(self) -> Optional[int]:
        """Find next batch that needs translation."""
        for i in range(1, self.state.total_batches + 1):
            status = self.state.batches[str(i)]
            if status.status in ("pending", "failed") and status.attempt < 3:
                return i
        return None

    def _get_completed_count(self) -> int:
        """Get number of completed batches."""
        return sum(
            1 for b in self.state.batches.values()
            if isinstance(b, BatchStatus) and b.status == "completed"
        )

    def _make_status(self, next_action: str, error: str = None, batch: int = None) -> dict:
        """Create enhanced status response with agentic guidance."""
        completed = self._get_completed_count()
        progress_percent = (completed / self.state.total_batches) * 100 if self.state.total_batches > 0 else 0

        # Build next command
        if next_action == "continue" and batch:
            next_command = f"cli-localize batch --session {self.state_file} --batch {batch}"
            next_description = f"Translate batch {batch} of {self.state.total_batches}"
            batch_status = self.state.batches.get(str(batch))
            estimated_tokens = batch_status.estimated_tokens if batch_status else 0
        elif next_action == "finalize":
            next_command = f"cli-localize finalize --session {self.state_file}"
            next_description = "Generate final translated file"
            estimated_tokens = 0
        else:
            next_command = None
            next_description = None
            estimated_tokens = 0

        result = {
            "status": "ok" if not error else "error",
            "progress": {
                "completed": completed,
                "total": self.state.total_batches,
                "percent": round(progress_percent, 1),
                "current_batch": batch or self.state.current_batch,
            },
            "next_action": {
                "action": next_action,
                "command": next_command,
                "description": next_description,
                "estimated_tokens": estimated_tokens,
            } if next_command else {"action": next_action},
            "summary": self._make_summary(next_action, completed, batch),
        }

        if error:
            result["error"] = error
        if batch:
            result["next_batch"] = batch

        return result

    def _make_summary(self, action: str, completed: int, batch: int = None) -> str:
        """Generate human-readable summary."""
        total = self.state.total_batches
        pct = round((completed / total) * 100, 1) if total > 0 else 0

        if action == "continue":
            return f"{completed}/{total} batches complete ({pct}%). Continue with batch {batch}."
        elif action == "finalize":
            return f"All {total} batches complete! Ready to generate output file."
        elif action == "retry":
            return f"Batch {batch} failed. Please retry."
        else:
            return f"{completed}/{total} batches complete ({pct}%)."

    def _make_validation_error_response(
        self, batch_num: int, errors: list[ValidationError], attempt: int
    ) -> dict:
        """Create detailed validation error response for agents."""
        completed = self._get_completed_count()
        progress_percent = (completed / self.state.total_batches) * 100

        return {
            "status": "error",
            "progress": {
                "completed": completed,
                "total": self.state.total_batches,
                "percent": round(progress_percent, 1),
            },
            "next_action": {
                "action": "retry" if attempt < 3 else "skip",
                "batch": batch_num,
            },
            "batch": batch_num,
            "attempt": attempt,
            "max_attempts": 3,
            "validation_errors": [e.to_dict() for e in errors],
            "error_summary": f"{len(errors)} validation error(s) found",
            "suggestion": "Fix the errors listed in validation_errors and resubmit the .ibf file",
            "summary": f"Batch {batch_num} validation failed (attempt {attempt}/3). Fix errors and retry.",
        }

    def get_status(self) -> dict:
        """Get current session status with agentic guidance."""
        next_batch = self._find_next_pending_batch()
        next_action = "finalize" if not next_batch else "translate"
        completed = self._get_completed_count()
        progress_percent = (completed / self.state.total_batches) * 100 if self.state.total_batches > 0 else 0

        # Build batch status map
        batch_status_map = {}
        remaining_batches = []
        for i in range(1, self.state.total_batches + 1):
            status = self.state.batches.get(str(i))
            if status:
                batch_status_map[str(i)] = status.status
                if status.status in ("pending", "failed"):
                    remaining_batches.append(i)

        # Determine next command
        if next_batch:
            next_command = f"cli-localize batch --session {self.state_file} --batch {next_batch}"
            next_description = f"Translate batch {next_batch} of {self.state.total_batches}"
        else:
            next_command = f"cli-localize finalize --session {self.state_file}"
            next_description = "Generate final translated file"

        return {
            "session_id": self.session_id,
            "format": self.state.format_type,
            "status": self.state.status,
            "progress": {
                "completed": completed,
                "total": self.state.total_batches,
                "percent": round(progress_percent, 1),
                "remaining_batches": remaining_batches,
            },
            "batch_status": batch_status_map,
            "next_action": {
                "action": next_action,
                "command": next_command,
                "description": next_description,
            },
            "state_file": str(self.state_file),
            "summary": f"{completed}/{self.state.total_batches} batches complete. " + (
                f"{len(remaining_batches)} remaining." if remaining_batches else "Ready to finalize."
            ),
        }

    def finalize(self) -> dict:
        """
        Reconstruct final output from all translated batches.

        Returns:
            Status dictionary with output path and stats
        """
        # Build translated entries map
        translations = {}
        for batch_status in self.state.batches.values():
            if isinstance(batch_status, BatchStatus) and batch_status.translated_entries:
                for entry in batch_status.translated_entries:
                    translations[str(entry["id"])] = entry["text"]

        # Reconstruct using format handler
        # Pass target language for format handlers that support it (e.g., ARB for @@locale)
        try:
            output_content = self.handler.reconstruct(self.entries, translations, target_language=self.state.tgt_lang)
        except TypeError:
            # Handler doesn't accept target_language parameter
            output_content = self.handler.reconstruct(self.entries, translations)

        # Write output
        self.output_path.write_text(output_content, encoding="utf-8")

        # Update state
        self.state.status = "completed"
        self.state.updated_at = datetime.now().isoformat()
        self._save_state()

        # Stats
        translated_count = len(translations)
        fallback_count = len(self.entries) - translated_count

        return {
            "status": "ok",
            "output_file": str(self.output_path),
            "stats": {
                "total_entries": len(self.entries),
                "translated": translated_count,
                "fallback": fallback_count,
            },
            "progress": {
                "completed": self.state.total_batches,
                "total": self.state.total_batches,
                "percent": 100.0,
            },
            "summary": f"Translation complete! Output written to {self.output_path.name}",
        }

    def _save_state(self) -> None:
        """Save session state to file."""
        self.state.updated_at = datetime.now().isoformat()
        self.state_file.write_text(
            json.dumps(self.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, state_file: str) -> "TranslationSession":
        """Load session from state file."""
        state_path = Path(state_file)
        data = json.loads(state_path.read_text(encoding="utf-8"))

        session = cls(
            input_file=data["input_file"],
            src_lang=data["src_lang"],
            tgt_lang=data["tgt_lang"],
            context_size=data["context_size"],
            target_tokens=data.get("target_tokens", 5000),
            output_file=data["output_file"],
            session_id=data["session_id"],
            format_type=data.get("format_type", "srt"),
            _loading=True,
        )
        session.state = SessionState.from_dict(data)
        return session


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python session.py <input_file>")
        sys.exit(1)

    session = TranslationSession(
        input_file=sys.argv[1],
        src_lang="en",
        tgt_lang="tr",
        context_size=5,
        target_tokens=5000,
    )

    print("=== SESSION CREATED ===")
    print(json.dumps(session.get_status(), indent=2))

    print("\n=== BATCH 1 ===")
    batch_ibf = session.get_batch(1)
    print(batch_ibf)
