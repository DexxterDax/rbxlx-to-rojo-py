"""Roblox file format parsers for XML and binary files."""

import json
import logging
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    import compression.zstd as zstd
except ImportError:  # pragma: no cover
    zstd = None

logger = logging.getLogger(__name__)


class Instance:
    """Represents a Roblox instance."""
    
    def __init__(self, class_name: str, name: str = "", referent: Optional[str] = None):
        self.class_name = class_name
        self.name = name
        self.referent = referent or str(id(self))
        self.properties: Dict[str, Any] = {}
        self.children_refs: List[str] = []
        self.parent_ref: Optional[str] = None
    
    def get_property(self, name: str) -> Optional[Any]:
        """Get a property value."""
        return self.properties.get(name)
    
    def get_children(self) -> List[str]:
        """Get list of child referents."""
        return self.children_refs


class WeakDom:
    """Represents a weak DOM tree of Roblox instances."""
    
    def __init__(self, root_instance: Instance):
        self._root_ref = root_instance.referent
        self._instances: Dict[str, Instance] = {root_instance.referent: root_instance}
    
    def root_ref(self) -> str:
        """Get the root instance referent."""
        return self._root_ref
    
    def get_by_ref(self, ref: str) -> Optional[Instance]:
        """Get an instance by its referent."""
        return self._instances.get(ref)
    
    def insert(self, parent_ref: str, instance: Instance):
        """Insert an instance as a child of another."""
        parent = self.get_by_ref(parent_ref)
        if parent:
            parent.children_refs.append(instance.referent)
            instance.parent_ref = parent_ref
            self._instances[instance.referent] = instance
    
    def add_instance(self, instance: Instance):
        """Add an instance to the DOM."""
        self._instances[instance.referent] = instance


def parse_property_value(prop_elem) -> Any:
    """Parse a property value from an XML element."""
    prop_type = prop_elem.tag
    prop_text = prop_elem.text or ""
    
    # Handle different property types
    if prop_type == "string":
        return prop_text
    elif prop_type == "bool":
        return prop_text.lower() == "true"
    elif prop_type in ("int", "int64"):
        return int(prop_text) if prop_text else 0
    elif prop_type in ("float", "double"):
        return float(prop_text) if prop_text else 0.0
    elif prop_type == "ProtectedString":
        return prop_text
    elif prop_type == "Content":
        return prop_text
    elif prop_type == "BinaryString":
        # Binary strings are base64 encoded in XML
        import base64
        try:
            return base64.b64decode(prop_text).decode('utf-8', errors='ignore')
        except:
            return prop_text
    else:
        # For unknown types, just return the text
        return prop_text


def parse_instance(item_elem, parent_ref: str, dom: WeakDom):
    """Recursively parse an instance and its children from XML."""
    class_name = item_elem.get("class", "Unknown")
    referent = item_elem.get("referent", None)
    
    instance = Instance(class_name=class_name, referent=referent)
    
    properties_elem = item_elem.find("Properties")
    if properties_elem is not None:
        for prop_elem in properties_elem:
            prop_name = prop_elem.get("name", "Unknown")
            prop_value = parse_property_value(prop_elem)
            instance.properties[prop_name] = prop_value
            
            if prop_name == "Name":
                instance.name = prop_value
    
    if parent_ref:
        dom.insert(parent_ref, instance)
    else:
        dom.add_instance(instance)
    
    for child_elem in item_elem.findall("Item"):
        parse_instance(child_elem, instance.referent, dom)


def from_reader_default(file_reader) -> WeakDom:
    """
    Parse a Roblox XML file (rbxlx/rbxmx) from a file reader.
    Returns a WeakDom instance.
    """
    try:
        tree = ET.parse(file_reader)
        root_elem = tree.getroot()
        
        if root_elem.tag != "roblox":
            raise ValueError("Not a valid Roblox XML file")
        
        root_instance = Instance(class_name="DataModel", name="DataModel")
        dom = WeakDom(root_instance)
        
        for item_elem in root_elem.findall("Item"):
            parse_instance(item_elem, root_instance.referent, dom)
        
        return dom
    
    except ET.ParseError as e:
        raise ValueError(f"XML parsing error: {e}")


def from_str_default(xml_string: str) -> WeakDom:
    """
    Parse a Roblox XML string.
    Returns a WeakDom instance.
    """
    import io
    return from_reader_default(io.StringIO(xml_string))


def _binary_bridge_script() -> Path:
    """Return the path to the rbxmk-based binary parser bridge."""
    return Path(__file__).resolve().parent / "scripts" / "parse_binary_place.lua"


def _bundled_rbxmk_path() -> Optional[Path]:
    """Return a bundled rbxmk binary when present."""
    executable = "rbxmk.exe" if sys.platform == "win32" else "rbxmk"
    bundled = Path(__file__).resolve().parent / "bin" / executable
    if bundled.exists():
        return bundled

    return None


def _decompress_zstd(payload: bytes) -> bytes:
    """Decompress a Zstandard frame."""
    if zstd is not None:
        return zstd.decompress(payload)

    zstd_binary = shutil.which("zstd")
    if zstd_binary is None:
        raise RuntimeError(
            "This .rbxl file uses Zstandard-compressed chunks. "
            "Use Python 3.14+ or install the `zstd` CLI."
        )

    completed = subprocess.run(
        [zstd_binary, "-d", "-q", "-c"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.decode("utf-8", errors="replace").strip() or "zstd decompression failed")

    return completed.stdout


def _normalize_binary_for_rbxmk(file_path: Path) -> Path:
    """
    Rewrite Zstandard-compressed chunks into uncompressed chunks so older
    parsers like rbxmk can decode newer Roblox binary files.
    """
    temp_dir = Path(Path.home().anchor or "/") / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"rbxlx-to-rojo-normalized-{uuid4().hex}{file_path.suffix.lower() or '.rbxl'}"

    changed = False

    with file_path.open("rb") as source, temp_path.open("wb") as target:
        header = source.read(32)
        if len(header) < 32:
            temp_path.unlink(missing_ok=True)
            raise ValueError("Binary file is too short to be a valid Roblox binary file.")

        target.write(header)

        while True:
            chunk_header = source.read(16)
            if not chunk_header:
                break
            if len(chunk_header) < 16:
                temp_path.unlink(missing_ok=True)
                raise ValueError("Binary file ended in the middle of a chunk header.")

            chunk_name = chunk_header[:4]
            compressed_len, uncompressed_len, reserved = struct.unpack("<III", chunk_header[4:16])
            payload_len = compressed_len if compressed_len else uncompressed_len
            payload = source.read(payload_len)

            if len(payload) < payload_len:
                temp_path.unlink(missing_ok=True)
                raise ValueError("Binary file ended in the middle of a chunk payload.")

            if compressed_len and payload.startswith(b"\x28\xb5\x2f\xfd"):
                decompressed = _decompress_zstd(payload)
                if len(decompressed) != uncompressed_len:
                    temp_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"Zstandard chunk {chunk_name!r} decompressed to {len(decompressed)} bytes, "
                        f"expected {uncompressed_len}."
                    )

                target.write(chunk_name)
                target.write(struct.pack("<III", 0, len(decompressed), reserved))
                target.write(decompressed)
                changed = True
            else:
                target.write(chunk_header)
                target.write(payload)

            if chunk_name == b"END\x00":
                trailing = source.read()
                if trailing:
                    target.write(trailing)
                break

    if not changed:
        temp_path.unlink(missing_ok=True)
        return file_path

    return temp_path


def _from_binary_json(payload: Dict[str, Any]) -> WeakDom:
    """Convert a serialized binary parse result into a WeakDom."""
    root_instance = Instance(class_name="DataModel", name="DataModel")
    dom = WeakDom(root_instance)
    instances_by_id: Dict[int, Instance] = {}

    for raw_instance in payload.get("instances", []):
        instance = Instance(
            class_name=raw_instance.get("class_name", "Unknown"),
            referent=str(raw_instance["id"]),
        )

        for prop_name, prop_value in raw_instance.get("properties", {}).items():
            instance.properties[prop_name] = prop_value
            if prop_name == "Name" and isinstance(prop_value, str):
                instance.name = prop_value

        if not instance.name:
            instance.name = raw_instance.get("class_name", "Unknown")

        instances_by_id[raw_instance["id"]] = instance

    for raw_instance in payload.get("instances", []):
        instance = instances_by_id[raw_instance["id"]]
        parent_id = raw_instance.get("parent_id")

        if parent_id is None:
            dom.insert(root_instance.referent, instance)
            continue

        parent = instances_by_id.get(parent_id)
        if parent is None:
            logger.warning("Binary parser returned an unknown parent id: %s", parent_id)
            dom.insert(root_instance.referent, instance)
            continue

        dom.insert(parent.referent, instance)

    return dom


def from_path_default_binary(file_path: Path) -> WeakDom:
    """
    Parse a Roblox binary file (rbxl/rbxm) from a path.
    Requires the Lua bridge and an `rbxmk` runtime.
    """
    bundled_rbxmk = _bundled_rbxmk_path()
    rbxmk = str(bundled_rbxmk) if bundled_rbxmk is not None else shutil.which("rbxmk")
    if rbxmk is None:
        aftman_path = Path.home() / ".aftman" / "bin" / "rbxmk"
        if aftman_path.exists():
            rbxmk = str(aftman_path)

    if rbxmk is None:
        raise RuntimeError(
            "Binary Roblox file parsing requires `rbxmk`.\n"
            "Bundle it into the standalone app or install it with "
            "`aftman trust Anaminus/rbxmk && aftman add --global Anaminus/rbxmk`."
        )

    script_path = _binary_bridge_script()
    if not script_path.exists():
        raise RuntimeError(
            "Binary Roblox file parsing is not available in this build because "
            f"the bridge script is missing: {script_path}"
        )

    normalized_path = _normalize_binary_for_rbxmk(file_path)

    try:
        completed = subprocess.run(
            [rbxmk, "run", "--allow-insecure-paths", str(script_path), str(normalized_path)],
            cwd=script_path.parent.parent,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            error_message = completed.stderr.strip() or completed.stdout.strip()
            raise ValueError(error_message or "Binary parser bridge failed.")

        stdout = completed.stdout.strip()
        if not stdout:
            error_message = completed.stderr.strip() or "Binary parser bridge produced no output."
            raise ValueError(error_message)

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as error:
            detail = completed.stderr.strip()
            if detail:
                raise ValueError(detail) from error
            raise ValueError(f"Binary parser returned invalid JSON: {error}") from error

        return _from_binary_json(payload)
    finally:
        if normalized_path != file_path:
            normalized_path.unlink(missing_ok=True)


def from_reader_default_binary(file_reader) -> WeakDom:
    """
    Parse a Roblox binary file (rbxl/rbxm) from a binary file-like object.
    """
    temp_dir = Path(Path.home().anchor or "/") / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"rbxlx-to-rojo-{uuid4().hex}.rbxl"
    temp_path.write_bytes(file_reader.read())

    try:
        return from_path_default_binary(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
