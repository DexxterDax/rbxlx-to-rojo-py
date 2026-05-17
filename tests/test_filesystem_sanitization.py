import json
import shutil
import tempfile
import unittest
from pathlib import Path

from filesystem import FileSystem
from structures import AddToTreeInstruction, CreateFileInstruction, TreePartition


class TestFileSystemSanitization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rbxlx-to-rojo-fs-"))
        self.filesystem = FileSystem.from_root(self.temp_dir / "output")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_file_sanitizes_whitespace_only_segments(self):
        self.filesystem.read_instruction(
            CreateFileInstruction(
                filename=Path("Workspace") / "Model" / " " / "init.meta.json",
                contents=b"{}",
            )
        )

        self.assertTrue(
            (self.temp_dir / "output" / "src" / "Workspace" / "Model" / "Unnamed" / "init.meta.json").exists()
        )

    def test_create_file_sanitizes_windows_invalid_characters(self):
        self.filesystem.read_instruction(
            CreateFileInstruction(
                filename=Path("Workspace") / 'bad:name*?' / "init.meta.json",
                contents=b"{}",
            )
        )

        self.assertTrue(
            (self.temp_dir / "output" / "src" / "Workspace" / "bad_name__" / "init.meta.json").exists()
        )

    def test_project_paths_are_sanitized_without_changing_tree_name(self):
        self.filesystem.read_instruction(
            AddToTreeInstruction(
                name=" ",
                partition=TreePartition(
                    class_name="Folder",
                    children={},
                    ignore_unknown_instances=True,
                    path=Path("Workspace") / " " / "Child.",
                ),
            )
        )
        self.filesystem.finish_instructions()

        project = json.loads((self.temp_dir / "output" / "default.project.json").read_text(encoding="utf-8"))
        self.assertNotIn("emitLegacyScripts", project)
        self.assertIn(" ", project["tree"])
        self.assertEqual(project["tree"][" "]["$path"], "src/Workspace/Unnamed/Child")

    def test_client_script_write_removes_stale_run_context_meta(self):
        stale_meta = self.temp_dir / "output" / "src" / "StarterGui" / "GuiScript.meta.json"
        stale_meta.parent.mkdir(parents=True, exist_ok=True)
        stale_meta.write_text(
            json.dumps(
                {
                    "ignoreUnknownInstances": True,
                    "properties": {
                        "RunContext": "Legacy",
                    },
                }
            ),
            encoding="utf-8",
        )

        self.filesystem.read_instruction(
            CreateFileInstruction(
                filename=Path("StarterGui") / "GuiScript.client.luau",
                contents=b"print('client')",
            )
        )

        self.assertFalse(stale_meta.exists())

    def test_script_write_removes_redundant_legacy_run_context_meta(self):
        stale_meta = self.temp_dir / "output" / "src" / "Workspace" / "ServerScript.meta.json"
        stale_meta.parent.mkdir(parents=True, exist_ok=True)
        stale_meta.write_text(
            json.dumps(
                {
                    "ignoreUnknownInstances": True,
                    "properties": {
                        "RunContext": "Legacy",
                    },
                }
            ),
            encoding="utf-8",
        )

        self.filesystem.read_instruction(
            CreateFileInstruction(
                filename=Path("Workspace") / "ServerScript.server.luau",
                contents=b"print('server')",
            )
        )

        self.assertFalse(stale_meta.exists())

    def test_script_write_keeps_legacy_run_context_meta_when_it_has_other_content(self):
        stale_meta = self.temp_dir / "output" / "src" / "Workspace" / "ServerScript.meta.json"
        stale_meta.parent.mkdir(parents=True, exist_ok=True)
        stale_meta.write_text(
            json.dumps(
                {
                    "ignoreUnknownInstances": True,
                    "className": "Script",
                    "properties": {
                        "RunContext": "Legacy",
                    },
                }
            ),
            encoding="utf-8",
        )

        self.filesystem.read_instruction(
            CreateFileInstruction(
                filename=Path("Workspace") / "ServerScript.server.luau",
                contents=b"print('server')",
            )
        )

        self.assertTrue(stale_meta.exists())


if __name__ == "__main__":
    unittest.main()
