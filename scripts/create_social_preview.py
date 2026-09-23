#!/usr/bin/env python3
"""Render the GitHub social preview image for dify-dsl-skill."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "social-preview.png"
WIDTH, HEIGHT = 1280, 640

BG = "#071217"
SURFACE = "#0D2028"
SURFACE_ALT = "#102A33"
LINE = "#21434C"
TEXT = "#F4F8F7"
MUTED = "#91AAAC"
TEAL = "#4ED1B3"
BLUE = "#86B7FF"
AMBER = "#F3C969"
CORAL = "#F18A8D"


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        candidates = [
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    elif bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, radius: int = 8) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 0)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # Brand mark.
    draw.ellipse((64, 58, 88, 82), fill=TEAL)
    draw.ellipse((82, 44, 106, 68), fill=BLUE)
    draw.line((84, 66, 94, 58), fill=TEXT, width=5)
    draw.text((126, 47), "Dify DSL Skill", font=font(30, bold=True), fill=TEXT)
    rounded(draw, (64, 112, 220, 146), SURFACE_ALT, LINE)
    draw.text((84, 119), "OPEN SOURCE", font=font(14, bold=True), fill=TEAL)

    draw.text((64, 184), "Natural language to", font=font(52, bold=True), fill=TEXT)
    draw.text((64, 244), "published Dify workflows", font=font(52, bold=True), fill=TEXT)
    draw.text((64, 324), "Generate  /  Source-sync  /  Auto-layout", font=font(22), fill=MUTED)
    draw.text((64, 358), "Validate  /  Import Draft  /  Publish", font=font(22), fill=MUTED)

    benefits = [
        (TEAL, "Canonical Python Code sources"),
        (BLUE, "Deterministic ELK canvas layout"),
        (AMBER, "Strict Draft and Published verification"),
    ]
    for index, (color, text) in enumerate(benefits):
        y = 430 + index * 44
        draw.ellipse((68, y + 5, 84, y + 21), fill=color)
        draw.text((100, y), text, font=font(20), fill=TEXT)

    # Workflow surface.
    rounded(draw, (704, 54, 1216, 586), SURFACE, LINE)
    draw.text((736, 82), "WORKFLOW CANDIDATE", font=font(14, bold=True), fill=MUTED)
    draw.text((736, 116), "Customer Feedback Triage", font=font(24, bold=True), fill=TEXT)

    nodes = [
        (736, 182, 834, 236, "INPUT", BLUE),
        (884, 182, 1018, 236, "ANALYZE", TEAL),
        (1068, 182, 1178, 236, "ROUTE", AMBER),
    ]
    for x1, y1, x2, y2, label, color in nodes:
        rounded(draw, (x1, y1, x2, y2), SURFACE_ALT, color)
        bounds = draw.textbbox((0, 0), label, font=font(14, bold=True))
        draw.text(((x1 + x2 - bounds[2]) / 2, y1 + 18), label, font=font(14, bold=True), fill=color)
    draw.line((836, 209, 880, 209), fill=TEAL, width=3)
    draw.polygon(((880, 209), (870, 203), (870, 215)), fill=TEAL)
    draw.line((1020, 209, 1064, 209), fill=TEAL, width=3)
    draw.polygon(((1064, 209), (1054, 203), (1054, 215)), fill=TEAL)

    branch_nodes = [
        (758, 294, 886, 350, "INVALID", CORAL),
        (908, 294, 1042, 350, "FOLLOW-UP", AMBER),
        (1064, 294, 1192, 350, "STANDARD", BLUE),
    ]
    for x1, y1, x2, y2, label, color in branch_nodes:
        rounded(draw, (x1, y1, x2, y2), SURFACE_ALT, color)
        bounds = draw.textbbox((0, 0), label, font=font(13, bold=True))
        draw.text(((x1 + x2 - bounds[2]) / 2, y1 + 19), label, font=font(13, bold=True), fill=color)
    for center in (822, 975, 1128):
        draw.line((1123, 238, center, 288), fill=LINE, width=3)

    rounded(draw, (846, 408, 1102, 466), "#173E3A", TEAL)
    draw.text((906, 426), "MERGE  ->  END", font=font(16, bold=True), fill=TEAL)
    for center in (822, 975, 1128):
        draw.line((center, 352, 974, 404), fill=LINE, width=3)

    draw.line((736, 512, 1184, 512), fill=LINE, width=2)
    draw.text((736, 532), "0 errors", font=font(17, bold=True), fill=TEAL)
    draw.text((862, 532), "0 overlaps", font=font(17, bold=True), fill=BLUE)
    draw.text((1018, 532), "publish-ready", font=font(17, bold=True), fill=AMBER)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, optimize=True)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
