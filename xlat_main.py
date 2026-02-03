#!/usr/bin/env python3
"""
Entry point for xlat CLI binary.
This module is used by PyInstaller to create the standalone executable.
"""

import sys
from pathlib import Path

# Add the package directory to the path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled binary
    bundle_dir = Path(sys._MEIPASS)
else:
    # Running as script
    bundle_dir = Path(__file__).parent

sys.path.insert(0, str(bundle_dir))

from xlat.cli import main

if __name__ == "__main__":
    main()
