# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cli-localize** is an LLM-optimized CLI for translating localization files using a custom token-efficient format called IBF (Indexed Block Format). It supports SRT, JSON, PO, Android XML, iOS .strings, YAML, and ARB formats.

## Commands

```bash
# Install dependencies
uv sync

# Install with optional dependencies
uv sync --extra api    # httpx for API calls
uv sync --extra cache  # redis for caching
uv sync --extra all    # all optional deps
uv sync --extra dev    # pytest, pyinstaller

# Run CLI
uv run cli-localize --help
uv run cli-localize formats  # List supported formats

# Run tests
uv run pytest                                    # All tests
uv run pytest tests/                             # All tests in tests/
uv run pytest tests/test_ibf_bugs.py -v          # Single test file
uv run pytest -k "placeholder"                   # Tests matching pattern

# Lint
uv run ruff check .
uv run ruff check --fix .

# Build standalone binary
uv run python build.py --clean
```

## Architecture

### Core Components

```
xlat/
├── cli.py              # Entry point (cli-localize command)
├── session.py          # TranslationSession: state management, validation
├── ibf_format.py       # IBF encoder/decoder, validation errors
├── batcher.py          # TokenBatcher: token-based batch splitting
└── format_handlers/
    ├── base.py         # FormatHandler ABC, TranslationEntry, PlaceholderPattern
    ├── srt.py          # SRT subtitle handler
    ├── json_handler.py # JSON (i18next/react-intl/vue-i18n)
    ├── po.py           # GNU gettext PO/POT
    ├── android_xml.py  # Android strings.xml
    ├── ios_strings.py  # iOS/macOS .strings
    ├── yaml_handler.py # Rails/Symfony YAML
    └── arb.py          # Flutter ARB
```

### Data Flow

1. **Init**: File → FormatHandler.parse() → TranslationEntry[] → TokenBatcher → BatchInfo[] → SessionState
2. **Batch**: BatchInfo → IBFEncoder → IBF text with @context_before/@translate/@context_after
3. **Submit**: IBF text → IBFDecoder → Validation → Store translations in SessionState
4. **Finalize**: SessionState + translations → FormatHandler.reconstruct() → Output file

### IBF Format

Token-efficient format (~24% fewer tokens than JSON):

```
#TRANSLATE:v1:en>tr:batch=1/10:entries=5:ctx=10
@context_before
[47] Previous text for context
[48] More context
@translate
[49] Text to translate
[50] Another entry
@context_after
[51] Following context
---
```

Translated output format:
```
#TRANSLATED:v1:batch=1/10:count=2:status=ok
[49] Translated text
[50] Another translation
---
```

### Key Classes

- **TranslationEntry**: Universal entry with `id`, `text`, `context`, `metadata`
- **FormatHandler**: ABC with `parse()`, `reconstruct()`, `validate_placeholders()`
- **FormatRegistry**: Registers handlers, auto-detects format from extension/content
- **TranslationSession**: Manages state file (`.loc-{id}.json`), batch tracking, validation
- **TokenBatcher**: Uses tiktoken (cl100k_base) to create batches targeting ~5000 tokens
- **IBFEncoder/IBFDecoder**: Encode entries to IBF, decode/validate translated output

### Adding a New Format Handler

1. Create `format_handlers/{format}.py` implementing `FormatHandler`
2. Implement required properties: `name`, `file_extensions`, `supports_context`
3. Implement methods: `parse()` → list[TranslationEntry], `reconstruct()` → str
4. Register in `format_handlers/__init__.py`

## CLI Workflow

```bash
# 1. Initialize session (IMPORTANT: Quote the language pair!)
cli-localize init --input messages.json --lang 'en>tr' --target-tokens 5000

# 2. Get batch for translation
cli-localize batch --session .loc-abc123.json --batch 1 > batch_1.ibf

# 3. LLM translates, output saved to file

# 4. Submit translation
cli-localize submit --session .loc-abc123.json --batch 1 --patch batch_1_tr.ibf

# 5. Check progress
cli-localize status --session .loc-abc123.json

# 6. Repeat 2-4 for remaining batches

# 7. Generate final output
cli-localize finalize --session .loc-abc123.json
```

> **⚠️ CRITICAL**: Always quote the `--lang` parameter: `--lang 'en>fr'`
> Without quotes, the shell interprets `>` as output redirection, causing silent failures.

## Validation

Submit validates:
- Entry count matches expected
- All IDs present, no extra/hallucinated IDs
- IBF header format correct
- Delimiter `---` present
- Placeholder preservation (format-specific)

Validation errors return structured JSON with line numbers and fix suggestions.

## State Files

Session state stored in `.loc-{session_id}.json` containing:
- Input/output file paths
- Source/target languages
- Batch statuses (pending/in_progress/completed/failed)
- Translated entries per batch
- Token estimates per batch

## Example Files

The `examples/` directory contains sample files for all 7 supported formats:

| Format | Source | Translated |
|--------|--------|------------|
| SRT | `sample.srt` | `sample_tr.srt` |
| JSON | `sample.json` | `sample_tr.json` |
| PO | `sample.po` | `sample_tr.po` |
| Android XML | `strings.xml` | `strings_tr.xml` |
| iOS Strings | `Localizable.strings` | `Localizable_tr.strings` |
| YAML | `sample.yml` | `sample_tr.yml` |
| ARB | `app_en.arb` | `app_tr.arb` |

Each example demonstrates placeholders specific to that format.

## Agent Usage Guide

This section provides optimized guidance for AI agents using cli-localize.

### Critical: Shell Quoting

**Always quote the `--lang` parameter**:
```bash
# ✅ CORRECT
cli-localize init --input file.json --lang 'en>fr'

# ❌ WRONG - Shell interprets > as redirect, causes silent failure
cli-localize init --input file.json --lang en>fr
```

### Session File Location

Session files are created **in the same directory as the input file**, not the current working directory:
```
Input: examples/sample.json
Session: examples/.loc-abc123-def456.json
```

### IBF Patch Format

When creating translated patches, use this exact format:

```
#TRANSLATED:v1:batch=N/M:count=X:status=ok
[id1] Translated text here
[id2] Another translation
[id3] Multi-line text uses \n for newlines
---
```

**Requirements:**
- Header must start with `#TRANSLATED:v1`
- Entry count must match exactly
- All IDs must be present (use exact IDs from batch output)
- Delimiter `---` required at end
- Newlines in text escaped as `\n`

### Placeholder Preservation by Format

| Format | Placeholder Style | Examples |
|--------|------------------|----------|
| SRT | N/A (timestamps only) | Preserve timing |
| JSON | Mustache `{{var}}` | `{{name}}`, `{{count}}` |
| PO | printf `%(var)s` | `%(name)s`, `%(count)d` |
| Android XML | Positional `%N$s` | `%1$s`, `%2$d` |
| iOS Strings | Apple `%@` / `%ld` | `%@`, `%ld`, `%1$@` |
| YAML | Ruby `%{var}` | `%{name}`, `%{count}` |
| ARB | ICU `{var}` | `{name}`, `{count}` |

**Placeholders must be preserved exactly** - copy them character-for-character into translations.

### Workflow Tips for Agents

1. **Parse init output** - Contains `session_file` path and `next_action` command
2. **Use absolute paths** - More reliable than relative paths
3. **Check next_action** - Every command response includes exact next command
4. **One batch at a time** - Process batch N, submit, then get batch N+1
5. **Validate before finalizing** - Use `status` command to verify all batches complete

### Example Agent Workflow

```python
# 1. Initialize (capture JSON output)
result = run("cli-localize init --input file.json --lang 'en>es'")
session_file = result["session_file"]

# 2. Get batch
batch_ibf = run(f"cli-localize batch --session {session_file} --batch 1")

# 3. Create translation (preserve IDs and placeholders)
translated_ibf = translate_content(batch_ibf)

# 4. Submit
run(f"cli-localize submit --session {session_file} --batch 1 --patch translated.ibf")

# 5. Finalize when all batches complete
run(f"cli-localize finalize --session {session_file}")
```

### Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| Session file not found | Wrong path or cleanup | Re-run init, use absolute path |
| Entry count mismatch | Missing/extra entries in patch | Count entries in batch output |
| Invalid header | Wrong TRANSLATED format | Copy header structure exactly |
| Missing delimiter | No `---` at end | Add `---` on final line |
| Silent init failure | Unquoted `--lang` | Quote: `--lang 'en>fr'`
