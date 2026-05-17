import json
import unittest
from pathlib import Path

from lib import normalize_run_context, repr_instance
from rbx_dom import Instance, parse_property_value
from structures import CreateFileInstruction, CreateFolderInstruction, MetaFile


class TestRunContext(unittest.TestCase):
    def test_meta_file_can_include_properties(self):
        meta = MetaFile(properties={"RunContext": "Client"})

        self.assertEqual(
            meta.to_dict(),
            {
                "ignoreUnknownInstances": True,
                "properties": {
                    "RunContext": "Client",
                },
            },
        )

    def test_xml_token_properties_parse_as_ints(self):
        element = type("Element", (), {"tag": "token", "text": "2"})()

        self.assertEqual(parse_property_value(element), 2)

    def test_run_context_numeric_values_normalize_to_enum_names(self):
        self.assertEqual(normalize_run_context(0), "Legacy")
        self.assertEqual(normalize_run_context(1), "Server")
        self.assertEqual(normalize_run_context("2"), "Client")
        self.assertEqual(normalize_run_context("token: 2"), "Client")
        self.assertEqual(normalize_run_context("Plugin"), "Plugin")

    def test_script_file_gets_run_context_meta_file(self):
        script = Instance("Script", "ClientRunner", "script")
        script.properties["Source"] = "print('client')"
        script.properties["RunContext"] = 2

        instructions, new_path = repr_instance(Path("Workspace"), script, {"script": True})

        self.assertEqual(new_path, Path("Workspace"))
        self.assertEqual(len(instructions), 2)
        self.assertIsInstance(instructions[0], CreateFileInstruction)
        self.assertEqual(instructions[0].filename, Path("Workspace") / "ClientRunner.server.luau")
        self.assertEqual(instructions[1].filename, Path("Workspace") / "ClientRunner.meta.json")
        self.assertEqual(
            json.loads(instructions[1].contents.decode("utf-8")),
            {
                "ignoreUnknownInstances": True,
                "properties": {
                    "RunContext": "Client",
                },
            },
        )

    def test_legacy_script_file_does_not_get_run_context_meta_file(self):
        script = Instance("Script", "ServerRunner", "script")
        script.properties["Source"] = "print('server')"
        script.properties["RunContext"] = "Legacy"

        instructions, new_path = repr_instance(Path("Workspace"), script, {"script": True})

        self.assertEqual(new_path, Path("Workspace"))
        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0].filename, Path("Workspace") / "ServerRunner.server.luau")

    def test_local_script_does_not_get_run_context_meta_file(self):
        script = Instance("LocalScript", "ClientRunner", "script")
        script.properties["Source"] = "print('client')"
        script.properties["RunContext"] = 2

        instructions, new_path = repr_instance(Path("Workspace"), script, {"script": True})

        self.assertEqual(new_path, Path("Workspace"))
        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0].filename, Path("Workspace") / "ClientRunner.client.luau")

    def test_init_script_gets_run_context_meta_file_when_all_children_are_scripts(self):
        script = Instance("Script", "Container", "script")
        script.properties["Source"] = "print('server')"
        script.properties["RunContext"] = "Server"
        script.children_refs.append("child")

        instructions, new_path = repr_instance(
            Path("Workspace"),
            script,
            {"script": True, "child": True},
        )

        self.assertEqual(new_path, Path("Workspace") / "Container")
        self.assertIsInstance(instructions[0], CreateFolderInstruction)
        self.assertEqual(instructions[1].filename, Path("Workspace") / "Container" / "init.server.luau")
        self.assertEqual(instructions[2].filename, Path("Workspace") / "Container" / "init.meta.json")
        self.assertEqual(
            json.loads(instructions[2].contents.decode("utf-8")),
            {
                "ignoreUnknownInstances": True,
                "properties": {
                    "RunContext": "Server",
                },
            },
        )

    def test_legacy_script_still_gets_meta_file_when_children_require_it(self):
        script = Instance("Script", "Container", "script")
        script.properties["Source"] = "print('server')"
        script.properties["RunContext"] = "Legacy"
        script.children_refs.append("child")

        instructions, new_path = repr_instance(
            Path("Workspace"),
            script,
            {"script": True, "child": False},
        )

        self.assertEqual(new_path, Path("Workspace"))
        self.assertEqual(len(instructions), 2)
        self.assertEqual(instructions[0].filename, Path("Workspace") / "Container.server.luau")
        self.assertEqual(instructions[1].filename, Path("Workspace") / "Container.meta.json")
        self.assertEqual(
            json.loads(instructions[1].contents.decode("utf-8")),
            {
                "ignoreUnknownInstances": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
