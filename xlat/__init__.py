"""
cli-localize - LLM-optimized multi-format localization translator

A CLI tool designed for LLM agents to translate localization files efficiently.
Supports SRT, JSON, PO, Android XML, iOS strings, YAML, and ARB formats.
Uses IBF (Indexed Block Format) for ~24% token savings vs JSON.

Quick start:
    cli-localize init --input messages.json --lang en>tr
    cli-localize batch --session .loc-xxx.json --batch 1
    # create batch_1.ibf with translations
    cli-localize submit --session .loc-xxx.json --batch 1 --patch batch_1.ibf
    cli-localize finalize --session .loc-xxx.json
"""

__version__ = "2.0.0"
__author__ = "Yigit Konur"

from .ibf_format import IBFDecoder, IBFEncoder, IBFEntry, IBFMetadata, ValidationError
from .session import TranslationSession

__all__ = [
    "IBFEncoder",
    "IBFDecoder",
    "IBFEntry",
    "IBFMetadata",
    "ValidationError",
    "TranslationSession",
]
