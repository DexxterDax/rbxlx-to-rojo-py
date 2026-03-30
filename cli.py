"""Command-line interface for rbxlx-to-rojo converter."""

import sys
import logging
from pathlib import Path
from typing import Optional
from filesystem import FileSystem
from lib import process_instructions
import rbx_dom


class Problem(Exception):
    """Base exception for rbxlx-to-rojo errors."""
    pass


class BinaryDecodeError(Problem):
    """Error decoding binary Roblox file."""
    def __init__(self, error):
        self.error = error
        super().__init__(
            f"While attempting to decode the place file, rbx_binary didn't know what to do: {error}"
        )


class XMLDecodeError(Problem):
    """Error decoding XML Roblox file."""
    def __init__(self, error):
        self.error = error
        super().__init__(
            f"While attempting to decode the place file, rbx_xml didn't know what to do: {error}"
        )


class InvalidFile(Problem):
    """Invalid file type."""
    def __init__(self):
        super().__init__("The file provided does not have a recognized file extension")


class IOError_(Problem):
    """IO error."""
    def __init__(self, doing_what: str, error: Exception):
        super().__init__(f"While attempting to {doing_what}, {error}")


class NFDCancel(Problem):
    """User cancelled file selection."""
    def __init__(self):
        super().__init__("Didn't choose a file.")


class NFDError(Problem):
    """Error in file dialog."""
    def __init__(self, error: str):
        super().__init__(f"Something went wrong when choosing a file: {error}")


class WrappedLogger:
    """Logger that writes to both console and file."""
    
    def __init__(self):
        self.log_file: Optional[Path] = None
        self.file_handle = None
    
    def set_log_file(self, path: Path):
        """Set the log file path."""
        self.log_file = path
        try:
            self.file_handle = open(path, 'w', encoding='utf-8')
        except Exception as e:
            logging.error(f"Could not create log file: {e}")
    
    def log(self, message: str):
        """Log a message to console and file."""
        logging.info(message)
        if self.file_handle:
            self.file_handle.write(f"{message}\n")
            self.file_handle.flush()
    
    def close(self):
        """Close the log file."""
        if self.file_handle:
            self.file_handle.close()


def get_file_path_from_dialog(prompt: str, filter_str: Optional[str] = None) -> Optional[Path]:
    """
    Get a file path from a file dialog.
    Falls back to command line input if dialog is not available.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        
        if filter_str:
            filetypes = []
            for ext in filter_str.split(','):
                filetypes.append((f"{ext.upper()} files", f"*.{ext}"))
            filetypes.append(("All files", "*.*"))
        else:
            filetypes = [("All files", "*.*")]
        
        file_path = filedialog.askopenfilename(
            title=prompt,
            filetypes=filetypes
        )
        
        root.destroy()
        
        if not file_path:
            return None
        
        return Path(file_path)
    
    except ImportError:
        print(prompt)
        file_path = input("Enter file path: ").strip()
        if not file_path:
            return None
        return Path(file_path)


def get_directory_from_dialog(prompt: str, initial_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Get a directory path from a dialog.
    Falls back to command line input if dialog is not available.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        
        dir_path = filedialog.askdirectory(
            title=prompt,
            initialdir=str(initial_dir) if initial_dir else None
        )
        
        root.destroy()
        
        if not dir_path:
            return None
        
        return Path(dir_path)
    
    except ImportError:
        print(prompt)
        if initial_dir:
            print(f"(Default: {initial_dir})")
        dir_path = input("Enter directory path: ").strip()
        if not dir_path:
            return None
        return Path(dir_path)


def routine() -> None:
    """Main conversion routine."""
    logger_wrapper = WrappedLogger()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    logger_wrapper.log("rbxlx-to-rojo-py v1.0.0")
    
    logger_wrapper.log("Select a place file.")
    
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        file_path = get_file_path_from_dialog(
            "Select a place file",
            "rbxl,rbxm,rbxlx,rbxmx"
        )
        
        if file_path is None:
            raise NFDCancel()
    
    if not file_path.exists():
        raise IOError_(f"read the place file", FileNotFoundError(f"File not found: {file_path}"))
    
    logger_wrapper.log("Opening place file")
    
    logger_wrapper.log("Decoding place file, this is the longest part...")
    
    extension = file_path.suffix.lower()
    tree = None
    
    try:
        if extension in ('.rbxmx', '.rbxlx'):
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = rbx_dom.from_reader_default(f)
        
        elif extension in ('.rbxm', '.rbxl'):
            tree = rbx_dom.from_path_default_binary(file_path)
        
        else:
            raise InvalidFile()
    
    except NotImplementedError as e:
        raise BinaryDecodeError(str(e))
    except ValueError as e:
        if extension in ('.rbxmx', '.rbxlx'):
            raise XMLDecodeError(str(e))
        else:
            raise BinaryDecodeError(str(e))
    except Exception as e:
        if isinstance(e, Problem):
            raise
        raise BinaryDecodeError(str(e))
    
    logger_wrapper.log("Select the path to put your Rojo project in.")
    
    if len(sys.argv) > 2:
        root = Path(sys.argv[2])
    else:
        root = get_directory_from_dialog(
            "Select output directory",
            file_path.parent
        )
        
        if root is None:
            raise NFDCancel()
    
    output_dir = root / file_path.stem
    filesystem = FileSystem.from_root(output_dir)
    
    logger_wrapper.set_log_file(root / "rbxlx-to-rojo.log")
    
    logger_wrapper.log("Starting processing, please wait a bit...")
    process_instructions(tree, filesystem)
    logger_wrapper.log("Done! Check rbxlx-to-rojo.log for a full log.")
    
    logger_wrapper.close()


def main():
    """Entry point."""
    try:
        routine()
    except Problem as e:
        print("An error occurred while using rbxlx-to-rojo.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("An unexpected error occurred:", file=sys.stderr)
        print(str(e), file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
