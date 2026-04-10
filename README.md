# rbxlx-to-rojo-py

Python port of the rbxlx-to-rojo Rust tool for converting Roblox place files to Rojo projects.

## Overview

This is a Python conversion of the original Rust implementation. It converts Roblox place files (`.rbxl`, `.rbxlx`, `.rbxm`, `.rbxmx`) into Rojo project structures.

## Structure

- `cli.py` - Command-line interface and main entry point
- `lib.py` - Core processing logic for tree traversal and instruction generation
- `filesystem.py` - Filesystem operations and project file generation
- `structures.py` - Data structures and base classes
- `rbx_dom.py` - Roblox XML file parser and DOM representation
- `scripts/build_bootstrapper.py` - Build script for a standalone app bundle/executable

## Features

- Parse Roblox XML files (.rbxlx, .rbxmx)
- Generate Rojo project structure with proper folder hierarchy
- Handle Scripts, LocalScripts, and ModuleScripts
- Generate .meta.json files for special instances
- Respect Roblox services (Workspace, ReplicatedStorage, etc.)

## Dependencies

XML input uses only the Python standard library:
- `xml.etree.ElementTree` - For XML parsing
- `pathlib` - For path operations
- `json` - For JSON serialization
- `tkinter` - For file dialogs (optional, falls back to CLI input)

Standalone release builds additionally require:
- `PyInstaller` (installed automatically by `scripts/build_bootstrapper.py`, so the build machine needs internet access once)

## Usage

### Basic Usage

```bash
python cli.py [input_file] [output_directory]
```

### Examples

```bash
# With arguments
python cli.py MyPlace.rbxlx ./output

# Without arguments (will show file dialogs)
python cli.py
```

If arguments are not provided, the script will prompt you to select files using a file dialog (requires tkinter).

### Standalone Bootstrapper

To produce a version that end users can run without installing Python, the repo, or any packages:

```bash
python3 scripts/build_bootstrapper.py
```

That creates a standalone release in `dist/`:
- macOS: `dist/rbxlx-to-rojo.app` plus `dist/rbxlx-to-rojo.zip`
- Windows/Linux: `dist/rbxlx-to-rojo/` plus `dist/rbxlx-to-rojo.zip`

The builder also bundles `scripts/parse_binary_place.lua` and, when `rbxmk` is available locally, bundles `rbxmk` into the release. That means the person using the generated app/bundle does not need Python, this repository, or a separate `rbxmk` install.

### Publishable Builds

This repo includes a GitHub Actions workflow at `.github/workflows/release-builds.yml` that builds publishable archives for:
- macOS arm64
- Windows x64

How to use it:
- Run the `Release Builds` workflow manually from the Actions tab to test CI builds.
- Push a tag like `v1.0.0` to build both platforms and publish the generated zip files to a GitHub Release for that tag.

The workflow uses:
- `actions/setup-python` to provide Python
- `ok-nick/setup-aftman` plus `aftman.toml` to install `rbxmk`
- `scripts/build_bootstrapper.py` to build the standalone app
- `scripts/prepare_release_artifact.py` to normalize the uploaded zip names

Published release asset names will look like:
- `rbxlx-to-rojo-macos-arm64.zip`
- `rbxlx-to-rojo-windows-x64.zip`

## Current Status

**Working in the standalone build:** XML and binary file parsing with Rojo project generation for `.rbxl`, `.rbxlx`, `.rbxm`, and `.rbxmx`, as long as the build machine has `rbxmk` available for bundling.

## Differences from Rust Version

- Uses python lel

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd rbxlx-to-rojo-py

# Run from source
python cli.py

# Or build the standalone app
python3 scripts/build_bootstrapper.py
```

## Contributing

This is a port of the original Rust implementation. When adding features, try to maintain compatibility with the original design where possible.
