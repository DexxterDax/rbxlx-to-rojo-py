"""Filesystem operations for rbxlx-to-rojo conversion."""

import json
import re
from pathlib import Path
from typing import Dict
from structures import (
    InstructionReader, Instruction, AddToTreeInstruction,
    CreateFileInstruction, CreateFolderInstruction, TreePartition
)

SRC = "src"
INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class Project:
    """Represents a Rojo project."""
    
    def __init__(self):
        self.name = "project"
        self.tree: Dict[str, TreePartition] = {}
    
    def to_dict(self) -> dict:
        """Convert project to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "tree": {
                "$className": "DataModel"
            }
        }
        
        for name, partition in self.tree.items():
            result["tree"][name] = partition.to_dict()
        
        return result


class FileSystem(InstructionReader):
    """Manages filesystem operations for the conversion process."""
    
    def __init__(self, root: Path):
        self.root = root
        self.source = root / SRC
        self.project = Project()
        
        self.source.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_root(cls, root: Path) -> 'FileSystem':
        """Create a FileSystem from a root path."""
        return cls(root)

    def sanitize_path_part(self, part: str) -> str:
        """Convert one path segment into a Windows-safe filename."""
        clean = INVALID_PATH_CHARS.sub("_", part.strip()).rstrip(".")

        if clean in {"", ".", ".."}:
            clean = "Unnamed"

        if clean.upper() in WINDOWS_RESERVED_NAMES:
            clean = f"{clean}_"

        return clean

    def sanitize_path(self, path: Path) -> Path:
        """Convert a relative path into a filesystem-safe relative path."""
        sanitized_parts = [self.sanitize_path_part(part) for part in path.parts if part not in {"", "."}]
        return Path(*sanitized_parts) if sanitized_parts else Path("Unnamed")

    def sanitize_partition_paths(self, partition: TreePartition):
        """Recursively sanitize tree partition paths for the generated project file."""
        if partition.path is not None:
            partition.path = Path(SRC) / self.sanitize_path(Path(partition.path))

        for child in partition.children.values():
            self.sanitize_partition_paths(child)
    
    def read_instruction(self, instruction: Instruction):
        """Process a single instruction."""
        if isinstance(instruction, AddToTreeInstruction):
            if instruction.name in self.project.tree:
                raise ValueError(
                    f"Duplicate item added to tree! Instances can't have the same name: {instruction.name}"
                )
            
            partition = instruction.partition
            self.sanitize_partition_paths(partition)
            
            self.project.tree[instruction.name] = partition
        
        elif isinstance(instruction, CreateFileInstruction):
            file_path = self.source / self.sanitize_path(Path(instruction.filename))
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                with open(file_path, 'wb') as f:
                    f.write(instruction.contents)
            except Exception as e:
                raise RuntimeError(f"Can't write to file {file_path}: {e}")
        
        elif isinstance(instruction, CreateFolderInstruction):
            folder_path = self.source / self.sanitize_path(Path(instruction.folder))
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise RuntimeError(f"Can't create folder {folder_path}: {e}")
    
    def finish_instructions(self):
        """Finalize the project by writing the default.project.json file."""
        project_file = self.root / "default.project.json"
        
        try:
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(self.project.to_dict(), f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Can't create default.project.json: {e}")
