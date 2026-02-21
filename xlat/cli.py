#!/usr/bin/env python3
"""
cli-localize - LLM-Friendly Localization Translation CLI

Multi-format localization file translator optimized for AI agent workflows.

Supported Formats:
    - SRT (subtitles)
    - JSON (i18next, react-intl, vue-i18n)
    - PO/POT (gettext - WordPress, Django, Rails)
    - Android XML (strings.xml)
    - iOS .strings
    - YAML (Rails, Symfony)
    - ARB (Flutter)

Commands:
    init     - Initialize translation session
    batch    - Get IBF batch for translation
    submit   - Submit translated IBF patch file
    status   - Check session status
    finalize - Reconstruct final output
    formats  - List supported formats

Example Agent Workflow:
    1. cli-localize init --input messages.json --lang 'en>tr'
       → Returns: session state file path, batch count

    2. cli-localize batch --session .loc-xxx.json --batch 1
       → Returns: IBF format text for translation

    3. [Agent translates and saves to batch_1.ibf]

    4. cli-localize submit --session .loc-xxx.json --batch 1 --patch batch_1.ibf
       → Returns: validation result + next command

    5. Repeat 2-4 for all batches

    6. cli-localize finalize --session .loc-xxx.json
       → Returns: output file path + stats
"""

import argparse
import json
import sys
from pathlib import Path

from .session import TranslationSession
from .format_handlers import FormatRegistry
from .ibf_format import create_translation_prompt


def cmd_init(args) -> dict:
    """Initialize a new translation session."""
    # Parse language pair
    if ">" in args.lang:
        src_lang, tgt_lang = args.lang.split(">")
    else:
        src_lang, tgt_lang = "en", args.lang

    # Validate language pair - detect shell redirect issue
    if src_lang == tgt_lang:
        return {
            "status": "error",
            "error": "same_language",
            "message": f"Source and target language are the same: '{src_lang}'. "
                      f"This usually happens when --lang is not quoted. "
                      f"Use: --lang '{src_lang}>XX' (with quotes) to prevent shell interpretation of '>'.",
            "suggestion": f"Try: cli-localize init --input {args.input} --lang '{src_lang}>XX'",
        }

    session = TranslationSession(
        input_file=args.input,
        src_lang=src_lang,
        tgt_lang=tgt_lang,
        context_size=args.context,
        target_tokens=args.target_tokens,
        output_file=args.output,
        format_type=args.format if args.format != "auto" else None,
    )

    # Get batch stats
    batch_stats = session.batcher.get_stats(session.batch_infos)

    return {
        "status": "ok",
        "session_id": session.session_id,
        "session_file": str(session.state_file),
        "format": session.handler.name,
        "stats": {
            "total_entries": session.state.total_entries,
            "total_batches": session.state.total_batches,
            "estimated_tokens_per_batch": batch_stats["avg_tokens_per_batch"],
            "source_lang": src_lang,
            "target_lang": tgt_lang,
        },
        "next_action": {
            "command": f"cli-localize batch --session {session.state_file} --batch 1",
            "description": f"Get batch 1 of {session.state.total_batches} for translation",
        },
        "summary": f"Session created. {session.state.total_entries} entries split into {session.state.total_batches} batches. Run the next command to start.",
    }


def cmd_batch(args) -> str:
    """Get IBF batch for translation."""
    session = TranslationSession.load(args.session)
    ibf = session.get_batch(args.batch)

    # Get batch info for guidance
    batch_info = session.batch_infos[args.batch - 1] if args.batch <= len(session.batch_infos) else None
    estimated_tokens = batch_info.estimated_tokens if batch_info else 0

    if args.with_prompt:
        # Include full translation prompt
        return create_translation_prompt(ibf, target_language=session.state.tgt_lang)

    # Add guidance footer
    guidance = {
        "progress": {
            "percent": 0 if args.batch == 1 else round(((args.batch - 1) / session.state.total_batches) * 100, 1),
            "current_batch": args.batch,
            "total": session.state.total_batches,
        },
        "next_action": {
            "save_as": f"batch_{args.batch}.ibf",
            "then_run": f"cli-localize submit --session {args.session} --batch {args.batch} --patch batch_{args.batch}.ibf",
        },
    }

    return f"{ibf}\n\n#GUIDANCE:{json.dumps(guidance)}"


def cmd_submit(args) -> dict:
    """Submit translated IBF patch file."""
    # Validate patch file argument
    if not args.patch:
        return {
            "status": "error",
            "error_type": "MISSING_PATCH",
            "error": "No patch file provided",
            "suggestion": "Use --patch to specify the .ibf file containing the translation",
            "example": f"cli-localize submit --session {args.session} --batch {args.batch} --patch batch_{args.batch}.ibf",
        }

    patch_path = Path(args.patch)

    # Check file exists
    if not patch_path.exists():
        return {
            "status": "error",
            "error_type": "FILE_NOT_FOUND",
            "error": f"Patch file not found: {args.patch}",
            "suggestion": f"Create the file '{args.patch}' with the translated IBF content",
            "expected_format": "#TRANSLATED:v1:batch=N/M:count=X:status=ok\\n[id] translated text\\n---",
        }

    # Check file is readable
    try:
        translated = patch_path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "status": "error",
            "error_type": "FILE_READ_ERROR",
            "error": f"Cannot read patch file: {e}",
            "suggestion": "Ensure the file is readable and properly encoded (UTF-8)",
        }

    # Check file is not empty
    if not translated.strip():
        return {
            "status": "error",
            "error_type": "EMPTY_FILE",
            "error": f"Patch file is empty: {args.patch}",
            "suggestion": "File must contain #TRANSLATED header, entries, and --- delimiter",
        }

    # Load session and submit
    session = TranslationSession.load(args.session)
    return session.submit_batch(args.batch, translated)


def cmd_status(args) -> dict:
    """Get session status."""
    session = TranslationSession.load(args.session)
    return session.get_status()


def cmd_finalize(args) -> dict:
    """Finalize and create output file."""
    session = TranslationSession.load(args.session)
    return session.finalize()


def cmd_formats(args) -> dict:
    """List supported formats."""
    formats = FormatRegistry.list_formats()
    return {
        "status": "ok",
        "formats": formats,
        "summary": f"{len(formats)} formats supported: {', '.join(f['name'] for f in formats)}",
    }


def cmd_oneshot(args) -> str:
    """
    One-shot mode: Return batch + status in single output.
    Useful for simple agent loops.
    """
    # Parse language pair
    if ">" in args.lang:
        src_lang, tgt_lang = args.lang.split(">")
    else:
        src_lang, tgt_lang = "en", args.lang

    # Check for existing session
    existing_states = list(Path(args.input).parent.glob(".loc-*.json"))

    if existing_states and not args.new:
        # Load most recent session
        state_file = max(existing_states, key=lambda p: p.stat().st_mtime)
        session = TranslationSession.load(str(state_file))
    else:
        # Create new session
        session = TranslationSession(
            input_file=args.input,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            context_size=args.context,
            target_tokens=args.target_tokens,
            output_file=args.output,
            format_type=args.format if args.format != "auto" else None,
        )

    # Determine batch to process
    status = session.get_status()
    batch_num = args.batch if args.batch else status["progress"].get("remaining_batches", [None])[0]

    if batch_num is None or status["next_action"]["action"] == "finalize":
        # All batches complete
        return json.dumps({
            "type": "ready_to_finalize",
            "session_id": session.session_id,
            "state_file": str(session.state_file),
            "next_action": {
                "command": f"cli-localize finalize --session {session.state_file}",
                "description": "Generate final translated file",
            },
        })

    # Get batch
    ibf = session.get_batch(batch_num)

    # Combine with status
    status_data = {
        "session_id": session.session_id,
        "batch": batch_num,
        "total": session.state.total_batches,
        "state_file": str(session.state_file),
        "next_action": "translate",
    }

    return f"{ibf}\n#STATUS:{json.dumps(status_data)}"


def main():
    parser = argparse.ArgumentParser(
        prog="cli-localize",
        description="cli-localize - LLM-Friendly Localization Translation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Formats:
  srt      - SubRip subtitles
  json     - i18next/react-intl/vue-i18n nested JSON
  po       - GNU gettext .po/.pot files
  android  - Android strings.xml
  strings  - iOS/macOS .strings
  yaml     - Rails/Symfony YAML i18n
  arb      - Flutter Application Resource Bundle

Examples:
  # Initialize session (auto-detect format, QUOTE the --lang!)
  cli-localize init --input messages.json --lang 'en>tr'

  # Initialize with explicit format and token target
  cli-localize init --input strings.xml --format android --lang 'en>es' --target-tokens 3000

  # Get batch for translation
  cli-localize batch --session .loc-abc123.json --batch 1 > batch_1_input.ibf

  # Submit translation
  cli-localize submit --session .loc-abc123.json --batch 1 --patch batch_1.ibf

  # Check status
  cli-localize status --session .loc-abc123.json

  # Finalize
  cli-localize finalize --session .loc-abc123.json

  # List supported formats
  cli-localize formats

IBF Patch File Format (.ibf):
  #TRANSLATED:v1:batch=1/10:count=10:status=ok
  [key1] First translated text
  [key2] Second translated text
  ...
  ---
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize translation session")
    init_parser.add_argument("--input", "-i", required=True, help="Input file")
    init_parser.add_argument("--output", "-o", help="Output file (optional)")
    init_parser.add_argument("--lang", "-l", default="en>tr", help="Language pair (e.g., 'en>tr') - QUOTE to prevent shell redirect")
    init_parser.add_argument("--context", "-c", type=int, default=10, help="Context entries for SRT (default: 10)")
    init_parser.add_argument("--target-tokens", "-t", type=int, default=5000, help="Target tokens per batch (default: 5000)")
    init_parser.add_argument("--format", "-f", default="auto",
                            choices=["auto", "srt", "json", "po", "android", "strings", "yaml", "arb"],
                            help="Input format (default: auto-detect)")

    # batch command
    batch_parser = subparsers.add_parser("batch", help="Get IBF batch for translation")
    batch_parser.add_argument("--session", "-s", required=True, help="Session state file")
    batch_parser.add_argument("--batch", "-b", type=int, required=True, help="Batch number")
    batch_parser.add_argument("--with-prompt", "-p", action="store_true", help="Include full translation prompt")

    # submit command
    submit_parser = subparsers.add_parser("submit", help="Submit translated IBF patch file")
    submit_parser.add_argument("--session", "-s", required=True, help="Session state file")
    submit_parser.add_argument("--batch", "-b", type=int, required=True, help="Batch number")
    submit_parser.add_argument("--patch", "-p", required=True, help="Path to .ibf patch file with translations")

    # status command
    status_parser = subparsers.add_parser("status", help="Get session status")
    status_parser.add_argument("--session", "-s", required=True, help="Session state file")

    # finalize command
    finalize_parser = subparsers.add_parser("finalize", help="Reconstruct final output")
    finalize_parser.add_argument("--session", "-s", required=True, help="Session state file")

    # formats command
    formats_parser = subparsers.add_parser("formats", help="List supported formats")

    # oneshot command
    oneshot_parser = subparsers.add_parser("oneshot", help="One-shot mode: get batch + status")
    oneshot_parser.add_argument("--input", "-i", required=True, help="Input file")
    oneshot_parser.add_argument("--output", "-o", help="Output file (optional)")
    oneshot_parser.add_argument("--lang", "-l", default="en>tr", help="Language pair")
    oneshot_parser.add_argument("--context", "-c", type=int, default=10, help="Context entries")
    oneshot_parser.add_argument("--target-tokens", "-t", type=int, default=5000, help="Target tokens per batch")
    oneshot_parser.add_argument("--format", "-f", default="auto",
                               choices=["auto", "srt", "json", "po", "android", "strings", "yaml", "arb"],
                               help="Input format (default: auto-detect)")
    oneshot_parser.add_argument("--batch", type=int, help="Specific batch number")
    oneshot_parser.add_argument("--new", action="store_true", help="Force new session")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init":
            result = cmd_init(args)
            print(json.dumps(result, indent=2))
        elif args.command == "batch":
            result = cmd_batch(args)
            print(result)
        elif args.command == "submit":
            result = cmd_submit(args)
            print(json.dumps(result, indent=2))
        elif args.command == "status":
            result = cmd_status(args)
            print(json.dumps(result, indent=2))
        elif args.command == "finalize":
            result = cmd_finalize(args)
            print(json.dumps(result, indent=2))
        elif args.command == "formats":
            result = cmd_formats(args)
            print(json.dumps(result, indent=2))
        elif args.command == "oneshot":
            result = cmd_oneshot(args)
            print(result)
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
