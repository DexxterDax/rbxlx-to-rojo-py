"""Core processing logic for rbxlx-to-rojo conversion."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from structures import (
    InstructionReader, CreateFileInstruction, CreateFolderInstruction,
    AddToTreeInstruction, TreePartition, MetaFile, create_partition,
    create_add_to_tree_instruction
)
import json

logger = logging.getLogger(__name__)

# Load non-tree services and respected services
# These would be loaded from files in the Rust version
NON_TREE_SERVICES: Set[str] = {
    # Add your non-tree services here
    # Example: "Workspace", "Players", etc.
}

RESPECTED_SERVICES: Set[str] = {
    "Workspace",
    "ReplicatedStorage", 
    "ServerScriptService",
    "ServerStorage",
    "StarterPlayer",
    "StarterGui",
    "StarterPack",
    "Chat",
    "LocalizationService",
    "SoundService",
    "Lighting",
    "ReplicatedFirst",
    "Teams",
}


class TreeIterator:
    """Iterates through the Roblox tree and generates instructions."""
    
    def __init__(self, instruction_reader: InstructionReader, path: Path, tree):
        self.instruction_reader = instruction_reader
        self.path = path
        self.tree = tree
    
    def visit_instructions(self, instance, has_scripts: Dict[int, bool]):
        """Visit an instance and generate instructions for it and its children."""
        for child_ref in instance.get_children():
            child = self.tree.get_by_ref(child_ref)
            if child is None:
                logger.error(f"Got fake child id: {child_ref}")
                continue
            
            if child.class_name == "StarterPlayer":
                folder_path = self.path / child.name
                instructions = []
                
                if has_scripts.get(child_ref, False):
                    instructions.append(CreateFolderInstruction(folder=folder_path))
                    
                    children_partitions = {}
                    for child_id in child.get_children():
                        if has_scripts.get(child_id, False):
                            child_instance = self.tree.get_by_ref(child_id)
                            if child_instance:
                                child_path = folder_path / child_instance.name
                                children_partitions[child_instance.name] = TreePartition(
                                    class_name="Folder",
                                    children={},
                                    ignore_unknown_instances=True,
                                    path=child_path
                                )
                    
                    instructions.append(AddToTreeInstruction(
                        name=child.name,
                        partition=TreePartition(
                            class_name=child.class_name,
                            children=children_partitions,
                            ignore_unknown_instances=True,
                            path=None
                        )
                    ))
                
                self.instruction_reader.read_instructions(instructions)
                
                new_iterator = TreeIterator(
                    self.instruction_reader,
                    folder_path,
                    self.tree
                )
                new_iterator.visit_instructions(child, has_scripts)
                continue
            
            result = repr_instance(self.path, child, has_scripts)
            if result is None:
                continue
            
            instructions_to_create_base, new_path = result
            self.instruction_reader.read_instructions(instructions_to_create_base)
            
            new_iterator = TreeIterator(
                self.instruction_reader,
                new_path,
                self.tree
            )
            new_iterator.visit_instructions(child, has_scripts)


def repr_instance(
    base: Path,
    child,
    has_scripts: Dict[int, bool]
) -> Optional[Tuple[List, Path]]:
    """
    Generate a representation of an instance.
    Returns (instructions, path) or None if the instance should be skipped.
    """
    child_ref = child.referent if hasattr(child, 'referent') else id(child)
    
    if not has_scripts.get(child_ref, False):
        return None
    
    class_name = child.class_name
    
    # Handle Folder
    if class_name == "Folder":
        folder_path = base / child.name
        meta_contents = json.dumps(
            MetaFile(ignore_unknown_instances=True).to_dict(),
            indent=2
        ).encode('utf-8')
        
        return (
            [
                CreateFolderInstruction(folder=folder_path),
                CreateFileInstruction(
                    filename=folder_path / "init.meta.json",
                    contents=meta_contents
                )
            ],
            folder_path
        )
    
    # Special handling for StarterCharacterScripts and StarterPlayerScripts
    # These should be treated as Folders to avoid Rojo className conflicts
    if class_name in ("StarterCharacterScripts", "StarterPlayerScripts"):
        folder_path = base / child.name
        meta_contents = json.dumps(
            MetaFile(ignore_unknown_instances=True).to_dict(),
            indent=2
        ).encode('utf-8')
        
        return (
            [
                CreateFolderInstruction(folder=folder_path),
                CreateFileInstruction(
                    filename=folder_path / "init.meta.json",
                    contents=meta_contents
                )
            ],
            folder_path
        )

    if class_name in ("Script", "LocalScript", "ModuleScript"):
        extension = {
            "Script": ".server",
            "LocalScript": ".client",
            "ModuleScript": ""
        }[class_name]
        
        source = child.get_property("Source")
        if source is None:
            logger.error(f"Script {child.name} has no Source property")
            return None
        
        source_bytes = source.encode('utf-8') if isinstance(source, str) else source
        
        if not child.get_children():
            return (
                [CreateFileInstruction(
                    filename=base / f"{child.name}{extension}.luau",
                    contents=source_bytes
                )],
                base
            )
        
        meta_contents = json.dumps(
            MetaFile(ignore_unknown_instances=True).to_dict(),
            indent=2
        ).encode('utf-8')
        
        script_children_count = sum(
            1 for child_id in child.get_children()
            if has_scripts.get(child_id, False)
        )
        total_children_count = len(child.get_children())
        folder_path = base / child.name
        
        if script_children_count == total_children_count:
            return (
                [
                    CreateFolderInstruction(folder=folder_path),
                    CreateFileInstruction(
                        filename=folder_path / f"init{extension}.luau",
                        contents=source_bytes
                    )
                ],
                folder_path
            )
        
        if script_children_count == 0:
            return (
                [
                    CreateFileInstruction(
                        filename=base / f"{child.name}{extension}.luau",
                        contents=source_bytes
                    ),
                    CreateFileInstruction(
                        filename=base / f"{child.name}.meta.json",
                        contents=meta_contents
                    )
                ],
                base
            )
        
        return (
            [
                CreateFolderInstruction(folder=folder_path),
                CreateFileInstruction(
                    filename=folder_path / f"init{extension}.luau",
                    contents=source_bytes
                ),
                CreateFileInstruction(
                    filename=folder_path / "init.meta.json",
                    contents=meta_contents
                )
            ],
            folder_path
        )
    
    treat_as_service = class_name in RESPECTED_SERVICES
    
    # TODO: Add reflection check for services
    # For now, we'll use a simple heuristic
    is_service = class_name.endswith("Service") or treat_as_service
    
    if is_service and not treat_as_service:
        return None
    
    if treat_as_service:
        # Don't represent empty services
        if not child.get_children():
            return None
        
        new_base = base / child.name
        instructions = []
        
        if class_name not in NON_TREE_SERVICES:
            instructions.append(create_add_to_tree_instruction(child, new_base))
        
        if child.get_children():
            instructions.append(CreateFolderInstruction(folder=new_base))
        
        return (instructions, new_base)
    
    folder_path = base / child.name
    meta = MetaFile(
        class_name=class_name,
        ignore_unknown_instances=True
    )
    
    return (
        [
            CreateFolderInstruction(folder=folder_path),
            CreateFileInstruction(
                filename=folder_path / "init.meta.json",
                contents=json.dumps(meta.to_dict(), indent=2).encode('utf-8')
            )
        ],
        folder_path
    )


def check_has_scripts(tree, instance, has_scripts: Dict[int, bool]) -> bool:
    """
    Recursively check if an instance or its descendants contain scripts.
    Updates the has_scripts dictionary.
    """
    children_have_scripts = False
    
    for child_ref in instance.get_children():
        child = tree.get_by_ref(child_ref)
        if child is None:
            logger.error(f"Got fake child id: {child_ref}")
            continue
        
        result = check_has_scripts(tree, child, has_scripts)
        children_have_scripts = children_have_scripts or result
    
    is_script = instance.class_name in ("Script", "LocalScript", "ModuleScript")
    result = is_script or children_have_scripts
    
    instance_ref = instance.referent if hasattr(instance, 'referent') else id(instance)
    has_scripts[instance_ref] = result
    
    return result


def process_instructions(tree, instruction_reader: InstructionReader):
    """
    Main entry point for processing a Roblox tree into filesystem instructions.
    """
    root_ref = tree.root_ref()
    root_instance = tree.get_by_ref(root_ref)
    
    if root_instance is None:
        logger.error("Could not get root instance")
        return
    
    path = Path()
    
    has_scripts = {}
    check_has_scripts(tree, root_instance, has_scripts)
    
    iterator = TreeIterator(instruction_reader, path, tree)
    iterator.visit_instructions(root_instance, has_scripts)
    
    instruction_reader.finish_instructions()
