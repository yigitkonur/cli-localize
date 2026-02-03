# Contributing to xlat

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yigitkonur/xlat.git
cd xlat

# Install with dev dependencies using uv
uv sync --extra dev

# Or with pip
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_json_handler_array_notation.py

# Run tests matching pattern
uv run pytest -k "placeholder"
```

## Linting

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

## Project Structure

```
xlat/
├── xlat/
│   ├── cli.py              # CLI entry point
│   ├── session.py          # Session management
│   ├── ibf_format.py       # IBF encoder/decoder
│   ├── batcher.py          # Token-based batching
│   └── format_handlers/
│       ├── base.py         # Abstract FormatHandler
│       ├── srt.py          # SRT handler
│       ├── json_handler.py # JSON handler
│       ├── po.py           # PO/POT handler
│       ├── android_xml.py  # Android strings.xml
│       ├── ios_strings.py  # iOS .strings
│       ├── yaml_handler.py # YAML handler
│       └── arb.py          # Flutter ARB
├── tests/                  # Test files
├── examples/               # Format examples
└── pyproject.toml
```

## Adding a New Format Handler

1. **Create handler file** in `xlat/format_handlers/`:

```python
# format_handlers/myformat.py
from .base import FormatHandler, TranslationEntry, PlaceholderPattern

class MyFormatHandler(FormatHandler):
    @property
    def name(self) -> str:
        return "myformat"

    @property
    def file_extensions(self) -> list[str]:
        return ["myf", "myformat"]

    @property
    def supports_context(self) -> bool:
        # True if format benefits from context (like SRT)
        # False for key-value formats (like JSON)
        return False

    @property
    def placeholder_patterns(self) -> list[PlaceholderPattern]:
        return [
            PlaceholderPattern('myformat', r'\{(\w+)\}'),  # {name}
        ]

    def parse(self, content: str) -> list[TranslationEntry]:
        """Parse file content into TranslationEntry objects."""
        entries = []
        # ... parsing logic ...
        for key, value in parsed_items:
            entries.append(TranslationEntry(
                id=key,
                text=value,
                metadata={}  # Format-specific metadata
            ))
        return entries

    def reconstruct(
        self,
        original_entries: list[TranslationEntry],
        translations: dict[str, str],
        **kwargs
    ) -> str:
        """Reconstruct the file with translations."""
        # ... reconstruction logic ...
        return output_content
```

2. **Register the handler** in `format_handlers/__init__.py`:

```python
def _register_all_handlers():
    # ... existing handlers ...

    try:
        from .myformat import MyFormatHandler
        FormatRegistry.register(MyFormatHandler)
    except ImportError:
        pass
```

3. **Add tests** in `tests/test_myformat_handler.py`

4. **Add example files** in `examples/`

## IBF Format Specification

### Input Format (TRANSLATE)

```
#TRANSLATE:v1:{src}>{tgt}:batch={n}/{total}:entries={count}:ctx={context_size}
@context_before
[id] Previous context text (read-only)
@translate
[id] Entry to translate
[id] Another entry
@context_after
[id] Following context (read-only)
---
```

### Output Format (TRANSLATED)

```
#TRANSLATED:v1:batch={n}/{total}:count={count}:status=ok
[id] Translated text
[id] Another translated text
---
```

### Entry Format

- IDs can be integers (SRT: `[1]`, `[2]`) or strings (JSON: `[user.greeting]`)
- Newlines in text are escaped as `\n`
- IDs in brackets must match exactly

### Validation Rules

1. Entry count must match exactly
2. All IDs must be present
3. No extra/hallucinated IDs
4. Header format must be correct
5. Delimiter `---` required at end

## Pull Request Guidelines

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `uv run pytest`
4. Ensure linting passes: `uv run ruff check .`
5. Update documentation if needed
6. Submit PR with clear description

## Code Style

- Line length: 100 characters (configured in pyproject.toml)
- Use type hints for function parameters and returns
- Add docstrings to public classes and methods
- Follow existing patterns in the codebase
