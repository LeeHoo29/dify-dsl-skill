from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
LAYOUT_SCRIPT = ROOT / "skills" / "dify-dsl" / "scripts" / "layout_dify_dsl.mjs"


def node(node_id: str, node_type: str, *, parent: str | None = None, outer_type: str = "custom") -> dict:
    value = {
        "id": node_id,
        "type": outer_type,
        "width": 244,
        "height": 90,
        "position": {"x": 0, "y": 0},
        "positionAbsolute": {"x": 0, "y": 0},
        "data": {"type": node_type, "title": node_id},
    }
    if parent:
        value["parentId"] = parent
    return value


def edge(edge_id: str, source: str, target: str, source_type: str, target_type: str, **data: object) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": "source",
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "data": {"sourceType": source_type, "targetType": target_type, **data},
    }


class LayoutTests(unittest.TestCase):
    def test_branch_and_iteration_layout_is_idempotent(self) -> None:
        iteration = node("iteration", "iteration")
        iteration["data"].update({"output_selector": ["child_code", "result"], "output_type": "array[string]"})
        child_start = node(
            "iteration_start",
            "iteration-start",
            parent="iteration",
            outer_type="custom-iteration-start",
        )
        child_code = node("child_code", "code", parent="iteration")
        graph_nodes = [
            node("start", "start"),
            node("branch", "if-else"),
            iteration,
            node("end", "end"),
            child_start,
            child_code,
        ]
        graph_edges = [
            edge("e1", "start", "branch", "start", "if-else"),
            edge("e2", "branch", "iteration", "if-else", "iteration"),
            edge("e3", "branch", "end", "if-else", "end"),
            edge("e4", "iteration", "end", "iteration", "end"),
            edge(
                "e5",
                "iteration_start",
                "child_code",
                "iteration-start",
                "code",
                isInIteration=True,
                iteration_id="iteration",
            ),
        ]
        data = {
            "kind": "app",
            "version": "0.7.0",
            "app": {"name": "Layout fixture", "mode": "workflow"},
            "workflow": {"graph": {"nodes": graph_nodes, "edges": graph_edges}},
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.yml"
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

            write = subprocess.run(
                ["node", str(LAYOUT_SCRIPT), str(path), "--write"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, write.returncode, write.stderr)

            check = subprocess.run(
                ["node", str(LAYOUT_SCRIPT), str(path), "--check"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, check.returncode, check.stderr)

            result = yaml.safe_load(path.read_text(encoding="utf-8"))
            nodes = {item["id"]: item for item in result["workflow"]["graph"]["nodes"]}
            container = nodes["iteration"]
            child = nodes["child_code"]
            self.assertGreater(container["width"], child["width"])
            self.assertGreater(container["height"], child["height"])
            self.assertEqual(
                container["position"]["x"] + child["position"]["x"],
                child["positionAbsolute"]["x"],
            )
            self.assertEqual(
                container["position"]["y"] + child["position"]["y"],
                child["positionAbsolute"]["y"],
            )


if __name__ == "__main__":
    unittest.main()
