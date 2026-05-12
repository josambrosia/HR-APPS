"""Render brand animation GIFs using Pillow.

Outputs (next to assets/brand/):
  - animation-02-typing-04E.gif  (typing reveal, magenta cursor on black)
  - animation-05-glow-04H.gif    (glow pulse, green cursor on navy)

Usage:
  py -3 assets/brand/tools/render_gif.py

Requires Pillow and a monospace TTF (Consolas on Windows by default).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent

FONT_CANDIDATES_BOLD = [
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono-Bold.ttf",
    Path("C:/Windows/Fonts/JetBrainsMono-Bold.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
]
FONT_CANDIDATES_REGULAR = [
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono-Medium.ttf",
    Path("C:/Windows/Fonts/JetBrainsMono-Medium.ttf"),
    Path("C:/Windows/Fonts/consola.ttf"),
]

WORD = "josaphat"
TAGLINE = "// from concept to code"

CANVAS = (480, 130)
TEXT_X = 36
WORD_BASELINE = 70
WORD_FONT_SIZE = 44
CURSOR_W = 20
CURSOR_H = 40
CURSOR_Y = 36
TAG_X = 36
TAG_BASELINE = 102
TAG_FONT_SIZE = 16

PALETTES = {
    "04E": {"bg": (10, 10, 10), "fg": (255, 255, 255), "accent": (236, 72, 153), "tag": (163, 163, 163)},
    "04H": {"bg": (15, 23, 42), "fg": (255, 255, 255), "accent": (16, 185, 129), "tag": (148, 163, 184)},
}


def find_font(candidates: list[Path], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    print(f"WARNING: No TTF found among {candidates}; using PIL default (will look ugly).", file=sys.stderr)
    return ImageFont.load_default()


def measure_word_end(font: ImageFont.FreeTypeFont, text: str) -> int:
    """Return the right edge x of `text` if drawn at TEXT_X."""
    if not text:
        return TEXT_X
    bbox = font.getbbox(text)
    return TEXT_X + (bbox[2] - bbox[0])


def draw_tagline(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, color: tuple[int, int, int]) -> None:
    draw.text((TAG_X, TAG_BASELINE - TAG_FONT_SIZE), TAGLINE, font=font, fill=color)


def render_typing_gif(palette: str, out_name: str, fps: int = 24, duration_s: float = 4.0) -> Path:
    p = PALETTES[palette]
    bold = find_font(FONT_CANDIDATES_BOLD, WORD_FONT_SIZE)
    medium = find_font(FONT_CANDIDATES_REGULAR, TAG_FONT_SIZE)

    n_frames = int(fps * duration_s)
    frames: list[Image.Image] = []

    for i in range(n_frames):
        t = i / fps  # seconds in [0, duration_s)
        progress = t / duration_s

        if progress < 0.45:
            chars = int(round((progress / 0.45) * len(WORD)))
        elif progress < 0.85:
            chars = len(WORD)
        elif progress < 0.95:
            held = (progress - 0.85) / 0.10
            chars = int(round(len(WORD) * (1 - held)))
        else:
            chars = 0
        chars = max(0, min(len(WORD), chars))

        text_partial = WORD[:chars]

        img = Image.new("RGB", CANVAS, p["bg"])
        draw = ImageDraw.Draw(img)

        if text_partial:
            draw.text((TEXT_X, WORD_BASELINE - WORD_FONT_SIZE), text_partial, font=bold, fill=p["fg"])

        cursor_x = measure_word_end(bold, text_partial) + 4

        if progress < 0.45 or (0.85 <= progress < 0.95):
            cursor_visible = True
        else:
            cycle = (t * 2) % 1.0
            cursor_visible = cycle < 0.5

        if cursor_visible:
            draw.rectangle(
                [cursor_x, CURSOR_Y, cursor_x + CURSOR_W, CURSOR_Y + CURSOR_H],
                fill=p["accent"],
            )

        draw_tagline(draw, medium, p["tag"])
        frames.append(img)

    out_path = OUT_DIR / out_name
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"  rendered {len(frames)} frames @ {fps}fps -> {out_path.name}")
    return out_path


def render_glow_gif(palette: str, out_name: str, fps: int = 30, duration_s: float = 2.0) -> Path:
    p = PALETTES[palette]
    bold = find_font(FONT_CANDIDATES_BOLD, WORD_FONT_SIZE)
    medium = find_font(FONT_CANDIDATES_REGULAR, TAG_FONT_SIZE)

    cursor_x = measure_word_end(bold, WORD) + 4
    n_frames = int(fps * duration_s)
    frames: list[Image.Image] = []

    accent_rgba = p["accent"] + (255,)

    for i in range(n_frames):
        t = i / fps
        cycle = t / duration_s

        pulse = (math.sin(cycle * 2 * math.pi - math.pi / 2) + 1) / 2
        glow_radius = 1 + pulse * 12

        blink_cycle = (t * 1.0) % 1.0
        cursor_alpha = 1.0 if blink_cycle < 0.5 else 0.25

        base = Image.new("RGB", CANVAS, p["bg"])
        base_draw = ImageDraw.Draw(base)
        base_draw.text((TEXT_X, WORD_BASELINE - WORD_FONT_SIZE), WORD, font=bold, fill=p["fg"])
        draw_tagline(base_draw, medium, p["tag"])

        glow_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.rectangle(
            [cursor_x, CURSOR_Y, cursor_x + CURSOR_W, CURSOR_Y + CURSOR_H],
            fill=accent_rgba,
        )
        if glow_radius > 0:
            blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
            glow_intensity = int(190 * pulse)
            r, g, b, _ = blurred.split()
            a = blurred.split()[3].point(lambda v, gi=glow_intensity: min(255, int(v * gi / 255)))
            blurred = Image.merge("RGBA", (r, g, b, a))
            base.paste(blurred, (0, 0), blurred)

        cursor_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(cursor_layer)
        cursor_color = p["accent"] + (int(255 * cursor_alpha),)
        c_draw.rectangle(
            [cursor_x, CURSOR_Y, cursor_x + CURSOR_W, CURSOR_Y + CURSOR_H],
            fill=cursor_color,
        )
        base.paste(cursor_layer, (0, 0), cursor_layer)

        frames.append(base)

    out_path = OUT_DIR / out_name
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"  rendered {len(frames)} frames @ {fps}fps -> {out_path.name}")
    return out_path


def main() -> None:
    print("Rendering Josaphat Tech Solution brand animations...")
    print()
    print("Animation 02 (Typing Reveal, palette 04E):")
    render_typing_gif("04E", "animation-02-typing-04E.gif")
    print()
    print("Animation 05 (Glow Pulse, palette 04H):")
    render_glow_gif("04H", "animation-05-glow-04H.gif")
    print()
    print(f"Done. Files written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
