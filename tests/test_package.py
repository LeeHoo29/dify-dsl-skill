from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml
from PIL import Image


ROOT = Path(__file__).parents[1]
SKILL_ROOTS = [
    ROOT / "skills" / "dify-dsl",
    ROOT / "skills" / "dify-python-code-node",
    ROOT / "skills" / "dify-local-sync",
]


class PackageTests(unittest.TestCase):
    def test_skill_frontmatter_and_name(self) -> None:
        for skill_root in SKILL_ROOTS:
            with self.subTest(skill=skill_root.name):
                content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
                match = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
                self.assertIsNotNone(match)
                metadata = yaml.safe_load(match.group(1))
                self.assertEqual(skill_root.name, metadata["name"])
                self.assertGreater(len(metadata["description"]), 50)

    def test_plugin_manifests_have_matching_identity(self) -> None:
        compatibility = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        portable = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("dify-dsl-skill", compatibility["name"])
        self.assertEqual(compatibility["name"], portable["name"])
        self.assertEqual(compatibility["version"], portable["version"])
        self.assertEqual(3, len(compatibility["interface"]["defaultPrompt"]))
        for field in ("composerIcon", "logo"):
            asset = ROOT / compatibility["interface"][field]
            self.assertTrue(asset.is_file(), f"missing plugin asset: {asset}")

    def test_skill_links_point_to_existing_local_resources(self) -> None:
        for skill_root in SKILL_ROOTS:
            content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            links = re.findall(r"\[[^]]+\]\(([^)]+)\)", content)
            local_links = [link for link in links if "://" not in link]
            self.assertTrue(local_links)
            for link in local_links:
                with self.subTest(skill=skill_root.name, link=link):
                    self.assertTrue((skill_root / link).is_file())

    def test_local_sync_artifacts_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "config/dify-env.local.yml",
            "dev-dsl/.dify-sync-map.json",
            "docker/docker-compose.override.yaml",
            ".dify-local-sync-backups/",
        ):
            self.assertIn(pattern, ignore)

    def test_demo_gif_is_a_30_second_readme_asset(self) -> None:
        demo = ROOT / "assets" / "demo.gif"
        self.assertTrue(demo.is_file())
        with Image.open(demo) as image:
            self.assertEqual((640, 400), image.size)
            self.assertGreaterEqual(image.n_frames, 100)
            duration_ms = 0
            for frame_index in range(image.n_frames):
                image.seek(frame_index)
                duration_ms += int(image.info.get("duration", 0))
            self.assertGreaterEqual(duration_ms, 29_000)
            self.assertLessEqual(duration_ms, 31_000)

    def test_live_canvas_reference_is_present(self) -> None:
        live_canvas = ROOT / "assets" / "live-dify-canvas.png"
        self.assertTrue(live_canvas.is_file())
        with Image.open(live_canvas) as image:
            self.assertGreaterEqual(image.width, 900)
            self.assertGreaterEqual(image.height, 500)

    def test_release_tree_has_no_private_project_markers(self) -> None:
        blocked = (
            "admin" + "@" + "admin.ai",
            "dify-" + "dsl-sync",
            "dify-" + "flyposter",
            "fly" + "fus",
            "local-" + "dify-" + "dsl-sync",
            "voc" + "scope",
        )
        unfinished_marker = "[" + "todo" + ":"
        text_suffixes = {".json", ".md", ".mjs", ".py", ".svg", ".txt", ".yaml", ".yml"}
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or "node_modules" in path.parts:
                continue
            if not path.is_file() or path.suffix not in text_suffixes:
                continue
            content = path.read_text(encoding="utf-8").lower()
            for marker in blocked:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker.lower(), content)
            self.assertNotIn(unfinished_marker, content)


if __name__ == "__main__":
    unittest.main()
