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

## Features

- Parse Roblox XML files (.rbxlx, .rbxmx)
- Parse Roblox binary files (.rbxl, .rbxm) through a small `rbxmk` bridge
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

Binary input additionally requires:
- `aftman`
- `rbxmk` installed through Aftman

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

### Converting Binary Files

Before using a binary Roblox file (`.rbxl` or `.rbxm`), install `rbxmk` once:

```bash
aftman trust Anaminus/rbxmk
aftman add --global Anaminus/rbxmk
```

## Current Status

 **Working:** XML and binary file parsing with Rojo project generation for `.rbxl`, `.rbxlx`, `.rbxm`, and `.rbxmx` files

## Differences from Rust Version

- Uses python lel

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd rbxlx-to-rojo-py

# Install the optional binary parser dependency
aftman trust Anaminus/rbxmk
aftman add --global Anaminus/rbxmk

# Then run the converter
python cli.py
```

## Contributing

This is a port of the original Rust implementation. When adding features, try to maintain compatibility with the original design where possible.
