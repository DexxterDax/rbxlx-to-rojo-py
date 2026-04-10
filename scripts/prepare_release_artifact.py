#!/usr/bin/env python3
"""Copy the built archive to a release-friendly filename."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

APP_NAME = "rbxlx-to-rojo"
ROOT = Path(__file__).resolve().parent.parent
DIST_ARCHIVE = ROOT / "dist" / f"{APP_NAME}.zip"
RELEASE_DIR = ROOT / "release"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a platform-specific archive name for CI release publishing.",
    )
    parser.add_argument("--platform", required=True, help="Platform label, for example windows-x64 or macos-arm64")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not DIST_ARCHIVE.exists():
        raise SystemExit(f"Missing built archive: {DIST_ARCHIVE}")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = RELEASE_DIR / f"{APP_NAME}-{args.platform}.zip"
    shutil.copy2(DIST_ARCHIVE, artifact_path)
    print(artifact_path)


if __name__ == "__main__":
    main()
