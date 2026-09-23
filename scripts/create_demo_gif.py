#!/usr/bin/env python3
"""Render the README's deterministic 30-second Dify DSL workflow demo GIF."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "demo.gif"
WIDTH, HEIGHT = 960, 600
PREVIEW_SIZE = (640, 400)
FPS = 4
DURATION_SECONDS = 30

BG = "#071217"
PANEL = "#0D2028"
PANEL_ALT = "#102A33"
LINE = "#21434C"
TEXT = "#F3F8F7"
MUTED = "#8BA9AA"
TEAL = "#4ED1B3"
TEAL_DARK = "#1E665A"
BLUE = "#86B7FF"
AMBER = "#F3C969"
RED = "#F07F83"


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/System/Library/Fonts/Menlo.ttc",
            "/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
        if mono
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONTS = {
    "title": font(28),
    "heading": font(18),
    "body": font(15),
    "small": font(12),
    "mono": font(13, mono=True),
    "mono_small": font(11, mono=True),
}


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, amount))


def ease(amount: float) -> float:
    amount = max(0.0, min(1.0, amount))
    return amount * amount * (3 - 2 * amount)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], fill: str, radius: int = 12, outline: str | None = None) -> None:
    draw.rounded_rectangle(tuple(round(v) for v in box), radius=radius, fill=fill, outline=outline, width=1 if outline else 0)


def label(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, key: str = "body", fill: str = TEXT) -> None:
    draw.text((round(xy[0]), round(xy[1])), text, font=FONTS[key], fill=fill)


def center_label(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], text: str, key: str = "small", fill: str = TEXT) -> None:
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=FONTS[key])
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(((left + right - width) / 2, (top + bottom - height) / 2 - bounds[1]), text, font=FONTS[key], fill=fill)


def progress(draw: ImageDraw.ImageDraw, active: int) -> None:
    stages = ["Describe", "Compose", "Source", "Layout", "Validate", "Sync"]
    x0, y = 40, 77
    gap = 145
    for index, stage in enumerate(stages):
        x = x0 + index * gap
        color = TEAL if index <= active else LINE
        draw.ellipse((x, y - 4, x + 8, y + 4), fill=color)
        if index < len(stages) - 1:
            draw.line((x + 8, y, x + gap, y), fill=TEAL if index < active else LINE, width=2)
        label(draw, (x - 2, y + 12), stage, "small", TEAL if index <= active else MUTED)


def shell() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 56), fill="#0A1B22")
    draw.ellipse((30, 20, 42, 32), fill=TEAL)
    draw.ellipse((39, 14, 51, 26), fill=BLUE)
    label(draw, (66, 15), "Dify DSL Skill", "heading")
    label(draw, (790, 19), "30-second workflow", "small", MUTED)
    return image, draw


def left_panel(draw: ImageDraw.ImageDraw, t: float) -> None:
    rounded(draw, (30, 112, 294, 532), PANEL, 14, LINE)
    label(draw, (52, 132), "Natural language", "heading")
    label(draw, (52, 161), "Tell the Agent what to build.", "small", MUTED)
    rounded(draw, (50, 204, 274, 314), PANEL_ALT, 12)
    prompt = "Create a Workflow that validates\nan order, normalizes its payload,\nand publishes a clear result."
    lines = prompt.splitlines()
    visible = max(0, min(len(prompt), int((t - 0.2) * 25)))
    shown = prompt[:visible]
    lines = shown.splitlines() or [""]
    for index, line in enumerate(lines):
        label(draw, (68, 226 + index * 24), line, "body", TEXT)
    if visible < len(prompt):
        cursor_x = 68 + draw.textlength(lines[-1], font=FONTS["body"])
        draw.rectangle((cursor_x + 2, 227 + (len(lines) - 1) * 24, cursor_x + 4, 245 + (len(lines) - 1) * 24), fill=TEAL)
    rounded(draw, (50, 338, 274, 382), TEAL_DARK if t > 3.2 else PANEL_ALT, 10)
    label(draw, (68, 350), "Generate usable DSL", "small", TEXT if t > 3.2 else MUTED)
    checks = [("Graph contract", t > 4.0), ("Code source", t > 10.5), ("Canvas layout", t > 16.5), ("Import checks", t > 22.0)]
    for index, (text, done) in enumerate(checks):
        y = 424 + index * 25
        draw.ellipse((54, y + 2, 66, y + 14), fill=TEAL if done else LINE)
        if done:
            draw.line((57, y + 8, 60, y + 11), fill=BG, width=2)
            draw.line((60, y + 11, 64, y + 5), fill=BG, width=2)
        label(draw, (78, y), text, "small", TEXT if done else MUTED)


def code_panel(draw: ImageDraw.ImageDraw, t: float) -> None:
    rounded(draw, (318, 112, 650, 322), PANEL, 14, LINE)
    label(draw, (340, 132), "Canonical Code source", "heading")
    label(draw, (340, 161), "docs/dify-code-nodes/normalize_order.py", "mono_small", BLUE)
    code = [
        ("def main(raw_order):", BLUE),
        ("    order = parse_order(raw_order)", TEXT),
        ("    valid = order[\"total\"] > 0", TEXT),
        ("    return {", TEXT),
        ("        \"can_continue\": valid,", TEAL),
        ("        \"order\": order,", TEAL),
        ("    }", TEXT),
    ]
    reveal = max(0.0, min(1.0, (t - 9.5) / 5.5))
    count = int(len(code) * reveal + 0.5)
    for index, (line, color) in enumerate(code[:count]):
        label(draw, (342, 198 + index * 19), line, "mono_small", color)
    rounded(draw, (318, 344, 650, 532), PANEL, 14, LINE)
    label(draw, (340, 364), "DSL candidate", "heading")
    yaml_lines = [
        "kind: app",
        "version: 0.7.0",
        "app: { mode: workflow }",
        "graph:",
        "  start -> normalize_order",
        "  normalize_order -> end",
    ]
    for index, line in enumerate(yaml_lines):
        visible = t > 5.5 + index * 0.35
        label(draw, (342, 399 + index * 19), line, "mono_small", TEXT if visible else LINE)


def graph_panel(draw: ImageDraw.ImageDraw, t: float) -> None:
    rounded(draw, (670, 112, 930, 322), PANEL, 14, LINE)
    label(draw, (692, 132), "ELK auto-layout", "heading")
    label(draw, (692, 161), "Readable graph, no canvas cleanup.", "small", MUTED)
    nodes = [
        ("Start", 692, 202, 72, 34, BLUE),
        ("Normalize", 790, 202, 92, 34, TEAL),
        ("Result", 896, 202, 58, 34, AMBER),
    ]
    progress_amount = ease((t - 16.0) / 4.0)
    for index, (name, x, y, width, height, color) in enumerate(nodes):
        node_x = lerp(692, x, progress_amount)
        rounded(draw, (node_x, y, node_x + width, y + height), "#132F36", 8, color if t > 16 else LINE)
        center_label(draw, (node_x, y, node_x + width, y + height), name, "small", color if t > 16 else MUTED)
        if index < 2 and progress_amount > 0.3:
            start_x = node_x + width
            next_x = lerp(692, nodes[index + 1][1], progress_amount)
            draw.line((start_x + 4, y + height / 2, next_x - 5, y + height / 2), fill=TEAL, width=2)
            draw.polygon(((next_x - 5, y + height / 2), (next_x - 12, y + height / 2 - 4), (next_x - 12, y + height / 2 + 4)), fill=TEAL)
    center_label(draw, (690, 272, 910, 302), "positions + viewport updated", "small", TEAL if t > 19 else MUTED)


def validation_panel(draw: ImageDraw.ImageDraw, t: float) -> None:
    rounded(draw, (670, 344, 930, 532), PANEL, 14, LINE)
    label(draw, (692, 364), "Pre-import checks", "heading")
    checks = [
        ("selectors", t > 22.2),
        ("Code contract", t > 22.9),
        ("layout overlap", t > 23.6),
        ("portable secrets", t > 24.3),
    ]
    for index, (name, done) in enumerate(checks):
        y = 405 + index * 27
        draw.ellipse((694, y + 1, 708, y + 15), fill=TEAL if done else LINE)
        if done:
            draw.line((697, y + 8, 701, y + 12), fill=BG, width=2)
            draw.line((701, y + 12, 706, y + 4), fill=BG, width=2)
        label(draw, (720, y), name, "small", TEXT if done else MUTED)
        label(draw, (854, y), "PASS" if done else "...", "small", TEAL if done else MUTED)
    if t >= 25.0:
        rounded(draw, (692, 490, 908, 516), TEAL_DARK, 8)
        center_label(draw, (692, 490, 908, 516), "0 errors  /  0 overlaps", "small", TEXT)


def sync_banner(draw: ImageDraw.ImageDraw, t: float) -> None:
    if t < 25.5:
        return
    amount = ease((t - 25.5) / 2.0)
    alpha_color = TEAL if amount > 0.7 else BLUE
    rounded(draw, (318, 112, 650, 156), PANEL_ALT, 10, alpha_color)
    label(draw, (338, 125), "Local Dify", "small", alpha_color)
    label(draw, (425, 125), "Draft imported", "small", TEXT)
    label(draw, (546, 125), "Published", "small", TEAL if t > 28.0 else MUTED)
    if t > 28.0:
        rounded(draw, (318, 344, 650, 390), TEAL_DARK, 10)
        label(draw, (340, 357), "Workflow v20260923", "mono_small", TEXT)
        label(draw, (530, 357), "verified", "small", TEAL)


def make_frame(index: int) -> Image.Image:
    t = index / FPS
    image, draw = shell()
    active = 0 if t < 5 else 1 if t < 10 else 2 if t < 16 else 3 if t < 22 else 4 if t < 26 else 5
    progress(draw, active)
    left_panel(draw, t)
    code_panel(draw, t)
    graph_panel(draw, t)
    validation_panel(draw, t)
    sync_banner(draw, t)
    draw.rectangle((0, HEIGHT - 24, WIDTH, HEIGHT), fill="#0A1B22")
    status = "Generating graph..." if t < 10 else "Synchronizing canonical source..." if t < 16 else "Laying out graph..." if t < 22 else "Validating import candidate..." if t < 26 else "Draft and Published state verified"
    label(draw, (30, HEIGHT - 18), status, "small", TEAL if t >= 26 else MUTED)
    label(draw, (795, HEIGHT - 18), f"{min(t, 30):04.1f}s / 30.0s", "small", MUTED)
    return image


def main() -> None:
    frames = [
        make_frame(index).resize(PREVIEW_SIZE, Image.Resampling.LANCZOS).convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64
        )
        for index in range(FPS * DURATION_SECONDS)
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KiB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
