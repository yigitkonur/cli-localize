#!/usr/bin/env python3
"""
Format handlers for localization file formats.

Supported formats:
- SRT: SubRip subtitle files
- JSON: i18next/react-intl style nested JSON
- PO: GNU gettext .po/.pot files
- Android XML: Android strings.xml
- iOS Strings: Apple .strings files
- YAML: Rails/Symfony i18n YAML
- ARB: Flutter Application Resource Bundle
"""

from .base import (
    FormatHandler,
    FormatRegistry,
    PlaceholderPattern,
    TranslationEntry,
    PLACEHOLDER_PATTERNS,
)

# Import handlers to register them
from .srt import SrtHandler

# Register handlers (order matters for extension conflicts)
FormatRegistry.register(SrtHandler)

# Lazy imports for other handlers (registered when imported)
def _register_all_handlers():
    """Import and register all available handlers."""
    try:
        from .json_handler import JsonHandler
        FormatRegistry.register(JsonHandler)
    except ImportError:
        pass

    try:
        from .po import PoHandler
        FormatRegistry.register(PoHandler)
    except ImportError:
        pass

    try:
        from .android_xml import AndroidXmlHandler
        FormatRegistry.register(AndroidXmlHandler)
    except ImportError:
        pass

    try:
        from .ios_strings import IosStringsHandler
        FormatRegistry.register(IosStringsHandler)
    except ImportError:
        pass

    try:
        from .yaml_handler import YamlHandler
        FormatRegistry.register(YamlHandler)
    except ImportError:
        pass

    try:
        from .arb import ArbHandler
        FormatRegistry.register(ArbHandler)
    except ImportError:
        pass


# Register all handlers on import
_register_all_handlers()

__all__ = [
    'FormatHandler',
    'FormatRegistry',
    'PlaceholderPattern',
    'TranslationEntry',
    'PLACEHOLDER_PATTERNS',
    'SrtHandler',
]
