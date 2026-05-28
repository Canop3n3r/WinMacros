#!/usr/bin/env python3
"""
Build script for WinMacros standalone executable.

Usage:
    python build.py

This will create a distributable folder in dist/WinMacros/
"""

import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

def clean():
    print("Cleaning previous builds...")
    for folder in (DIST_DIR, BUILD_DIR):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    print("Cleaned.")

def build():
    print("Building WinMacros executable with PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "WinMacros.spec"
    ]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print("Build failed!")
        sys.exit(result.returncode)
    print("Build completed successfully.")

def post_build():
    """Optional post-processing (copy docs, create zip, etc.)"""
    dist_app = DIST_DIR / "WinMacros"
    if dist_app.exists():
        # Copy useful files into the distribution
        for file in ["README.md", "LICENSE", "CHANGELOG.md", "requirements.txt"]:
            src = PROJECT_ROOT / file
            if src.exists():
                shutil.copy2(src, dist_app)

        print(f"\n✅ Build ready at: {dist_app}")
        print("You can zip this folder and distribute it.")
    else:
        print("Warning: Expected output folder not found.")

if __name__ == "__main__":
    clean()
    build()
    post_build()
    print("\nDone. Run the app from dist/WinMacros/WinMacros.exe")
