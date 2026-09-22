from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SCRIPT_PATH = ROOT / "skills" / "dify-dsl" / "scripts" / "sync_code_nodes.py"
SPEC = importlib.util.spec_from_file_location("sync_code_nodes", SCRIPT_PATH)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SYNC
SPEC.loader.exec_module(SYNC)


SOURCE = """# Dify input variables:
# - text (String, required): Text to normalize.
#
# Dify output variables:
# - result (String): Normalized text.
def main(text: str) -> dict:
    return {"result": (text or "").strip()}
"""


def dsl(source_line: str | None, code: str = "def main(text):\n    return {'result': text}\n") -> dict:
    desc = "Normalize text."
    if source_line:
        desc += f"\n\nCode source: {source_line}"
    return {
        "kind": "app",
        "version": "0.7.0",
        "app": {"name": "Fixture", "mode": "workflow"},
        "workflow": {
            "graph": {
                "edges": [],
                "nodes": [
                    {
                        "id": "normalize",
                        "type": "custom",
                        "data": {
                            "type": "code",
                            "title": "Normalize",
                            "desc": desc,
                            "code_language": "python3",
                            "code": code,
                            "variables": [{"variable": "text", "value_selector": ["start", "text"]}],
                            "outputs": {"result": {"type": "string", "children": None}},
                        },
                    }
                ],
            }
        },
    }


class SyncCodeNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.source_root = self.repo / "docs" / "dify-code-nodes"
        self.source_root.mkdir(parents=True)
        self.source = self.source_root / "normalize.py"
        self.source.write_text(SOURCE, encoding="utf-8")
        self.dsl_path = self.repo / "dev-dsl" / "fixture.yml"
        self.dsl_path.parent.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_dsl(self, data: dict) -> None:
        self.dsl_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def sync(self, *, write: bool) -> tuple[bool, list[object]]:
        return SYNC.synchronize_file(
            self.dsl_path,
            repo_root=self.repo,
            source_root=self.source_root,
            write=write,
        )

    def test_write_embeds_exact_canonical_source_then_check_passes(self) -> None:
        self.write_dsl(dsl("docs/dify-code-nodes/normalize.py"))
        changed, issues = self.sync(write=True)
        self.assertTrue(changed)
        self.assertEqual([], issues)

        data = yaml.safe_load(self.dsl_path.read_text(encoding="utf-8"))
        embedded = data["workflow"]["graph"]["nodes"][0]["data"]["code"]
        self.assertEqual(SYNC.normalize_code(SOURCE), embedded)

        changed, issues = self.sync(write=False)
        self.assertFalse(changed)
        self.assertEqual([], issues)

    def test_missing_source_marker_is_an_error(self) -> None:
        self.write_dsl(dsl(None))
        _, issues = self.sync(write=False)
        self.assertTrue(any("missing `Code source" in str(issue) for issue in issues))

    def test_source_outside_registry_is_an_error(self) -> None:
        outside = self.repo / "outside.py"
        outside.write_text(SOURCE, encoding="utf-8")
        self.write_dsl(dsl("outside.py"))
        _, issues = self.sync(write=False)
        self.assertTrue(any("outside" in str(issue) for issue in issues))

    def test_contract_mismatch_is_an_error(self) -> None:
        data = dsl("docs/dify-code-nodes/normalize.py")
        data["workflow"]["graph"]["nodes"][0]["data"]["outputs"] = {}
        self.write_dsl(data)
        changed, issues = self.sync(write=True)
        self.assertFalse(changed)
        self.assertTrue(any("output contract differs" in str(issue) for issue in issues))


if __name__ == "__main__":
    unittest.main()
