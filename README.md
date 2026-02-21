translation CLI built for AI agents. breaks localization files into token-sized batches, hands them to an LLM in a compact format, validates the output, and reconstructs the translated file. stateful and resumable — pick up where you left off.

```bash
xlat init -i messages.json -l "en>tr"
xlat batch -s .loc-*.json -b 1
xlat submit -s .loc-*.json -b 1 -p batch1.ibf
xlat finalize -s .loc-*.json
```

or in one shot:

```bash
xlat oneshot -i messages.json -l "en>tr"
```

[![python](https://img.shields.io/badge/python-3.10+-93450a.svg?style=flat-square)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-grey.svg?style=flat-square)](https://opensource.org/licenses/MIT)

---

## what it does

- **7 localization formats** — SRT, JSON (i18next/react-intl/vue-i18n), PO/POT, Android XML, iOS .strings, YAML (Rails/Symfony), Flutter ARB
- **token-aware batching** — uses `tiktoken` (cl100k_base) to split files into batches that fit LLM context windows. estimates output length with 1.2x expansion factor
- **IBF (indexed block format)** — compact wire format for LLM translation. one entry per line, IDs in brackets, newlines escaped. minimal token waste
- **context windows for subtitles** — SRT batches include surrounding entries as read-only context so the LLM can maintain narrative coherence
- **5-layer validation** — structural check, extraction, decode, content verification (ID matching, no hallucinated IDs), placeholder preservation
- **retry with 3 attempts** — failed batches get re-queued automatically. after 3 failures, skip and move on
- **resumable sessions** — all state persists to a `.loc-*.json` file next to your input. crash, restart, continue
- **graceful fallback** — unfinished batches fall back to source text on finalize

## supported formats

| format | extensions | placeholder style |
|:---|:---|:---|
| SRT | `.srt` | none (timecodes preserved) |
| JSON | `.json` | `{{name}}` (i18next), `{name}` (ICU) |
| PO/POT | `.po`, `.pot` | `%s`, `%(name)s` (printf) |
| Android XML | `.xml` | `%1$s`, `%2$d` |
| iOS .strings | `.strings` | `%@`, `%d`, `%ld`, `%f` |
| YAML | `.yml`, `.yaml` | `%{name}` (Ruby), `{{name}}` |
| Flutter ARB | `.arb` | `{name}`, `{count, plural, ...}` (ICU) |

auto-detected by file extension. for `.xml`, content is sniffed for `<resources>` to confirm Android format.

## install

```bash
pip install .
```

or with uv:

```bash
uv sync
```

for a standalone binary (no Python needed):

```bash
uv sync --extra dev
uv run python build.py --clean
# produces: dist/xlat-{platform}
```

requires Python 3.10+. only two runtime dependencies: `tiktoken` and `pyyaml`.

## usage

### step by step

```bash
# 1. parse file, create session
xlat init -i strings.json -l "en>de" -t 5000

# 2. get batch in IBF format (pipe to your LLM)
xlat batch -s .loc-a1b2-c3d4e5f6.json -b 1

# 3. submit the LLM's translation
xlat submit -s .loc-a1b2-c3d4e5f6.json -b 1 -p translated.ibf

# 4. repeat for remaining batches, then finalize
xlat finalize -s .loc-a1b2-c3d4e5f6.json
```

### oneshot (for simple agent loops)

```bash
xlat oneshot -i strings.json -l "en>de"
```

auto-creates or resumes a session and returns the next pending batch. designed for single-turn agent workflows.

### check progress

```bash
xlat status -s .loc-a1b2-c3d4e5f6.json
```

### list supported formats

```bash
xlat formats
```

## IBF format

the wire format between xlat and the LLM. minimal, line-oriented, token-efficient.

**request (sent to LLM):**

```
#TRANSLATE:v1:en>tr:batch=1/10:entries=5:ctx=10
@context_before
[47] previous subtitle for context
[48] another context entry
@translate
[49] text to translate
[50] another entry
@context_after
[51] following context
---
```

**response (from LLM):**

```
#TRANSLATED:v1:batch=1/10:count=5:status=ok
[49] translated text
[50] another translation
---
```

newlines in content are escaped as `\n`. empty translations are `[id]` with no trailing text.

## CLI reference

### init

| flag | default | description |
|:---|:---|:---|
| `-i, --input` | required | input file path |
| `-o, --output` | `{lang}_{stem}{ext}` | output file path |
| `-l, --lang` | `en>tr` | language pair (quote it — `>` is shell redirection) |
| `-t, --target-tokens` | `5000` | target tokens per batch |
| `-c, --context` | `10` | context window size (SRT only) |
| `-f, --format` | `auto` | force format: `srt json po android strings yaml arb` |

### batch

| flag | description |
|:---|:---|
| `-s, --session` | session state file |
| `-b, --batch` | batch number (1-indexed) |
| `-p, --with-prompt` | prepend a full translation prompt before the IBF block |

### submit

| flag | description |
|:---|:---|
| `-s, --session` | session state file |
| `-b, --batch` | batch number |
| `-p, --patch` | path to `.ibf` file with the LLM's response |

### status / finalize

| flag | description |
|:---|:---|
| `-s, --session` | session state file |

## how batching works

`TokenBatcher` uses tiktoken's cl100k_base encoding. for each entry it estimates output tokens as `floor(source_tokens * 1.2) + 10` — 20% expansion for translated text, 10 tokens for IBF framing overhead. batches fill until the target token count would be exceeded. falls back to 25 entries per batch if tiktoken isn't available.

## validation pipeline

when you submit a translated batch, it goes through five checks:

1. **structural** — header regex, `---` delimiter, line format matches `[id] text`
2. **extraction** — strips LLM preamble/postamble, finds `#TRANSLATED:` and `---` markers
3. **decode** — parses metadata and entries, unescapes `\n`
4. **content** — count match, all expected IDs present, no hallucinated IDs, batch number matches
5. **placeholder** — checks source-format placeholders are preserved (warnings only, doesn't reject)

## project structure

```
xlat/
  cli.py              — argparse entry point, command routing
  session.py          — stateful translation session logic
  ibf_format.py       — IBF encoder/decoder/validator
  batcher.py          — token-aware batch splitting
  format_handlers/
    base.py           — FormatHandler ABC, registry, TranslationEntry
    srt.py            — SubRip subtitles
    json_handler.py   — JSON (i18next, react-intl, vue-i18n)
    po.py             — GNU gettext PO/POT
    android_xml.py    — Android strings.xml
    ios_strings.py    — iOS/macOS .strings
    yaml_handler.py   — YAML (Rails/Symfony)
    arb.py            — Flutter ARB
```

## license

MIT
