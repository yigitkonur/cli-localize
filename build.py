#!/usr/bin/env python3
"""
Build script for xlat CLI binary.
Creates standalone executables for macOS and Linux.

Usage:
    python build.py          # Build for current platform
    python build.py --clean  # Clean build artifacts first
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_platform_name() -> str:
    """Get platform identifier for binary naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        if machine == "arm64":
            return "macos-arm64"
        return "macos-x64"
    elif system == "linux":
        if machine == "aarch64":
            return "linux-arm64"
        return "linux-x64"
    else:
        return f"{system}-{machine}"


def clean_build_artifacts(project_root: Path) -> None:
    """Remove build artifacts."""
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["*.pyc", "*.pyo"]
    
    for dir_name in dirs_to_remove:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"Removing {dir_path}")
            shutil.rmtree(dir_path)
    
    # Clean __pycache__ in subdirectories
    for pycache in project_root.rglob("__pycache__"):
        print(f"Removing {pycache}")
        shutil.rmtree(pycache)


def build_binary(project_root: Path) -> Path:
    """Build the binary using PyInstaller."""
    spec_file = project_root / "xlat.spec"
    
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        sys.exit(1)
    
    print(f"Building xlat for {get_platform_name()}...")
    print("-" * 50)
    
    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode != 0:
        print("Error: PyInstaller build failed")
        sys.exit(1)
    
    # Find the built binary
    dist_dir = project_root / "dist"
    binary_path = dist_dir / "xlat"
    
    if not binary_path.exists():
        print(f"Error: Binary not found at {binary_path}")
        sys.exit(1)
    
    # Rename with platform suffix
    platform_name = get_platform_name()
    final_name = f"xlat-{platform_name}"
    final_path = dist_dir / final_name
    
    if final_path.exists():
        final_path.unlink()
    
    binary_path.rename(final_path)
    
    # Make executable
    final_path.chmod(0o755)
    
    print("-" * 50)
    print(f"✓ Binary built successfully: {final_path}")
    print(f"  Size: {final_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    return final_path


def main():
    parser = argparse.ArgumentParser(description="Build xlat binary")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.absolute()
    
    if args.clean:
        clean_build_artifacts(project_root)
    
    binary_path = build_binary(project_root)
    
    print()
    print("To test the binary:")
    print(f"  {binary_path} --help")
    print()
    print("To install globally (optional):")
    print(f"  sudo cp {binary_path} /usr/local/bin/xlat")


if __name__ == "__main__":
    main()
