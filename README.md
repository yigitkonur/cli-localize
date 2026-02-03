<h1 align="center">xlat</h1>
<h3 align="center">Token-efficient translation CLI built for AI agents</h3>

<p align="center">
  <a href="#installation"><img alt="uv" src="https://img.shields.io/badge/uv-package_manager-4D87E6.svg?style=flat-square"></a>
  <a href="#supported-formats"><img alt="formats" src="https://img.shields.io/badge/formats-7_supported-009688.svg?style=flat-square"></a>
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-F9A825.svg?style=flat-square"></a>
  <a href="#"><img alt="platform" src="https://img.shields.io/badge/platform-macOS_|_Linux_|_Windows-2ED573.svg?style=flat-square"></a>
</p>

<p align="center">
  <strong>Reduce translation API costs by ~24% using IBF (Indexed Block Format)</strong><br/>
  <sub>A compact intermediate format designed specifically for LLM consumption</sub>
</p>

---

## The Problem

Translating localization files with AI agents is expensive and error-prone:

| Challenge | What Happens |
|-----------|--------------|
| **Token waste** | JSON/XML syntax burns through your context window |
| **Context limits** | Large files exceed LLM limits, requiring manual splitting |
| **Broken placeholders** | Agents mangle `{{name}}` into `{name}` or worse |
| **Lost progress** | One failed batch means starting over |
| **Format fragmentation** | Different tools for JSON, PO, Android, iOS... |

## The Solution

xlat introduces **IBF (Indexed Block Format)** — a wire format that strips away syntax and gives agents exactly what they need:

```
#TRANSLATE:v1:en>fr:batch=1/3:entries=15:ctx=0
@translate
[welcome] Welcome to our app
[goodbye] Goodbye, see you soon
[items_count] You have %d items in your cart
---
```

The agent translates, returns IBF, and xlat reconstructs your original format with validated placeholders.

---

## Supported Formats

| Format | Extensions | Placeholder Syntax |
|--------|------------|-------------------|
| **JSON** | `.json` | `{{name}}` |
| **PO/POT** | `.po`, `.pot` | `%(name)s`, `%s`, `%d` |
| **Android XML** | `.xml` | `%1$s`, `%2$d` |
| **iOS Strings** | `.strings` | `%@`, `%ld` |
| **YAML** | `.yml`, `.yaml` | `%{name}` |
| **ARB** (Flutter) | `.arb` | `{name}`, `{n, plural, ...}` |
| **SRT** (Subtitles) | `.srt` | N/A |

---

## Installation

```bash
git clone https://github.com/yigitkonur/subtitle-llm-translator.git
cd subtitle-llm-translator
uv sync
uv tool install -e .
```

Verify installation:
```bash
xlat --help
```

---

## Quick Start

### Manual Usage

```bash
# 1. Initialize a translation session
xlat init --input messages.json --lang 'en>fr'
# Returns: {"session_file": ".loc-abc123.json", "total_batches": 5}

# 2. Get a batch to translate
xlat batch --session .loc-abc123.json --batch 1

# 3. Translate the IBF output, save to file, submit
xlat submit --session .loc-abc123.json --batch 1 --patch batch_1.ibf

# 4. Repeat for all batches, then finalize
xlat finalize --session .loc-abc123.json
# Creates: messages_fr.json
```

### With AI Agents

xlat is designed for autonomous translation by AI agents. See the [Agent Prompt](#agent-integration) section below for copy-paste instructions.

---

## Commands

| Command | Purpose |
|---------|---------|
| `xlat init` | Create session, analyze file, plan batches |
| `xlat batch` | Get IBF content for a specific batch |
| `xlat submit` | Submit translated IBF, validate placeholders |
| `xlat status` | Check session progress |
| `xlat finalize` | Generate output file from all translations |

### Command Options

```bash
xlat init --input <file> --lang '<src>><tgt>' [--tokens <n>] [--context <n>]
xlat batch --session <file> --batch <n>
xlat submit --session <file> --batch <n> --patch <file.ibf>
xlat status --session <file>
xlat finalize --session <file> [--output <file>]
```

---

## IBF Format Specification

### Input (from `xlat batch`)

```
#TRANSLATE:v1:en>fr:batch=1/5:entries=10:ctx=2
@context_before
[prev_entry] Previously translated text for context
@translate
[welcome] Welcome to our app
[goodbye] Goodbye, see you soon
@context_after
[next_entry] Following text for context
---
```

### Output (agent produces)

```
#TRANSLATED:v1:batch=1/5:count=2:status=ok
[welcome] Bienvenue dans notre application
[goodbye] Au revoir, à bientôt
---
```

### Rules

- **Header line**: Must start with `#TRANSLATED:v1:`
- **Entry format**: `[id] translated text` (space after bracket required)
- **Terminator**: `---` on final line (required)
- **Only translate** `@translate` section — context sections are read-only
- **Preserve placeholders** exactly as they appear
- **Preserve entry IDs** exactly as they appear

---

## Agent Integration

Copy the prompt from [`agent-prompt.md`](./agent-prompt.md) to instruct AI agents on using xlat.

### Critical Rules for Agents

1. **Always quote `--lang`** — The `>` is a shell redirect:
   ```bash
   # Correct
   xlat init --input file.json --lang 'en>fr'

   # Wrong — creates empty file "fr"
   xlat init --input file.json --lang en>fr
   ```

2. **Never translate placeholders**:
   - `{{variable}}` → `{{variable}}`
   - `%s`, `%d`, `%@` → unchanged
   - `{name}`, `%{name}` → unchanged

3. **Only translate `@translate` section** — `@context_before` and `@context_after` are read-only context.

### Minimal Agent Prompt

For context-limited agents:

```
Translate files using xlat CLI. ALWAYS quote --lang: --lang 'en>fr'

Commands:
1. xlat init --input FILE --lang 'SRC>TGT' → Get session_file, total_batches
2. xlat batch --session FILE --batch N → Get IBF to translate
3. xlat submit --session FILE --batch N --patch FILE.ibf → Submit translation
4. xlat finalize --session FILE → Generate output

IBF Output Format:
#TRANSLATED:v1:batch=N/M:count=X:status=ok
[id1] Translated text
[id2] Another translation
---

Rules: Preserve placeholders ({{x}}, %s, %d, %@). Keep [ids] exact. End with ---
```

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `ENTRY_COUNT_MISMATCH` | Wrong number of entries | Translate ALL entries from @translate |
| `MISSING_ENTRIES` | IDs missing from output | Add missing `[id]` lines |
| `EXTRA_ENTRIES` | IDs in output not in input | Remove extra entries |
| `PLACEHOLDER_WARNING` | Placeholders modified | Review and fix placeholders |
| `INVALID_HEADER` | Malformed `#TRANSLATED` line | Check header format |
| `MISSING_TERMINATOR` | No `---` at end | Add `---` on final line |

---

## Session Recovery

Sessions are stored as `.loc-*.json` files in the input file directory. To resume:

```bash
# Find session file
ls -la .loc-*.json

# Check progress
xlat status --session .loc-abc123.json

# Continue from next pending batch
xlat batch --session .loc-abc123.json --batch 3
```

---

## Why ~24% Token Savings?

Traditional approach sends full JSON:
```json
{
  "welcome": "Welcome to our app",
  "goodbye": "Goodbye, see you soon",
  "items_count": "You have %d items in your cart"
}
```

IBF strips syntax overhead:
```
[welcome] Welcome to our app
[goodbye] Goodbye, see you soon
[items_count] You have %d items in your cart
```

Fewer tokens = lower API costs = more translations per dollar.

---

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Build standalone binary
uv run python build.py
```

---

## License

MIT
