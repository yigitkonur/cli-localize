#!/usr/bin/env python3
"""
Token-based batching for translation sessions.

Uses tiktoken to create batches based on estimated output token count,
allowing for optimal batch sizes that fit within LLM context limits.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from .format_handlers.base import TranslationEntry


@dataclass
class BatchInfo:
    """Information about a single batch."""
    batch_num: int
    entries: list[TranslationEntry]
    estimated_tokens: int
    start_idx: int
    end_idx: int


class TokenBatcher:
    """
    Creates batches based on estimated output token count.

    Instead of fixed entry counts, this batcher groups entries to approximate
    a target token count per batch, which is more efficient for LLM translation.
    """

    # Expansion factor: translations are typically longer than source
    EXPANSION_FACTOR = 1.2

    # Overhead per entry (brackets, newlines, etc.)
    ENTRY_OVERHEAD = 10

    def __init__(
        self,
        target_tokens: int = 5000,
        model: str = "cl100k_base",
        fallback_batch_size: int = 25,
    ):
        """
        Initialize token batcher.

        Args:
            target_tokens: Target output tokens per batch (default: 5000)
            model: Tiktoken encoding model (default: cl100k_base for GPT-4/Claude)
            fallback_batch_size: Batch size when tiktoken unavailable (default: 25)
        """
        self.target_tokens = target_tokens
        self.fallback_batch_size = fallback_batch_size

        if TIKTOKEN_AVAILABLE:
            try:
                self.encoder = tiktoken.get_encoding(model)
            except Exception:
                self.encoder = None
        else:
            self.encoder = None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if self.encoder:
            base_tokens = len(self.encoder.encode(text))
        else:
            # Fallback: ~4 chars per token (rough estimate)
            base_tokens = len(text) // 4

        # Apply expansion factor and add overhead
        return int(base_tokens * self.EXPANSION_FACTOR) + self.ENTRY_OVERHEAD

    def create_batches(
        self,
        entries: list[TranslationEntry],
    ) -> list[BatchInfo]:
        """
        Group entries into batches based on token count.

        Args:
            entries: List of translation entries

        Returns:
            List of BatchInfo objects
        """
        if not entries:
            return []

        batches = []
        current_entries = []
        current_tokens = 0
        start_idx = 0

        for i, entry in enumerate(entries):
            entry_tokens = self.estimate_tokens(entry.text)

            # Check if adding this entry would exceed target
            if current_tokens + entry_tokens > self.target_tokens and current_entries:
                # Save current batch
                batches.append(BatchInfo(
                    batch_num=len(batches) + 1,
                    entries=current_entries,
                    estimated_tokens=current_tokens,
                    start_idx=start_idx,
                    end_idx=start_idx + len(current_entries),
                ))

                # Start new batch
                current_entries = [entry]
                current_tokens = entry_tokens
                start_idx = i
            else:
                current_entries.append(entry)
                current_tokens += entry_tokens

        # Don't forget the last batch
        if current_entries:
            batches.append(BatchInfo(
                batch_num=len(batches) + 1,
                entries=current_entries,
                estimated_tokens=current_tokens,
                start_idx=start_idx,
                end_idx=start_idx + len(current_entries),
            ))

        return batches

    def create_batches_fixed(
        self,
        entries: list[TranslationEntry],
        batch_size: int,
    ) -> list[BatchInfo]:
        """
        Create batches with fixed entry count (legacy mode).

        Args:
            entries: List of translation entries
            batch_size: Number of entries per batch

        Returns:
            List of BatchInfo objects
        """
        if not entries:
            return []

        batches = []
        for i in range(0, len(entries), batch_size):
            batch_entries = entries[i:i + batch_size]
            estimated_tokens = sum(self.estimate_tokens(e.text) for e in batch_entries)

            batches.append(BatchInfo(
                batch_num=len(batches) + 1,
                entries=batch_entries,
                estimated_tokens=estimated_tokens,
                start_idx=i,
                end_idx=i + len(batch_entries),
            ))

        return batches

    def get_stats(self, batches: list[BatchInfo]) -> dict:
        """
        Get statistics about batches.

        Args:
            batches: List of BatchInfo objects

        Returns:
            Dictionary with batch statistics
        """
        if not batches:
            return {
                'total_batches': 0,
                'total_entries': 0,
                'total_estimated_tokens': 0,
                'avg_tokens_per_batch': 0,
                'min_tokens': 0,
                'max_tokens': 0,
            }

        total_entries = sum(len(b.entries) for b in batches)
        total_tokens = sum(b.estimated_tokens for b in batches)
        tokens_list = [b.estimated_tokens for b in batches]

        return {
            'total_batches': len(batches),
            'total_entries': total_entries,
            'total_estimated_tokens': total_tokens,
            'avg_tokens_per_batch': total_tokens // len(batches) if batches else 0,
            'min_tokens': min(tokens_list) if tokens_list else 0,
            'max_tokens': max(tokens_list) if tokens_list else 0,
        }


def create_batcher(
    target_tokens: Optional[int] = None,
    batch_size: Optional[int] = None,
) -> tuple[TokenBatcher, bool]:
    """
    Create appropriate batcher based on parameters.

    Args:
        target_tokens: Target tokens per batch (uses token-based batching)
        batch_size: Fixed batch size (uses fixed batching)

    Returns:
        Tuple of (TokenBatcher, use_token_mode)
    """
    if target_tokens is not None:
        return TokenBatcher(target_tokens=target_tokens), True
    elif batch_size is not None:
        batcher = TokenBatcher()
        return batcher, False
    else:
        # Default: token-based with 5000 tokens
        return TokenBatcher(target_tokens=5000), True
