# Josaphat Tech Solution — Brand Assets

Personal freelance developer brand. See [brand spec](../../docs/superpowers/specs/2026-05-12-josaphat-tech-brand-design.md) for full design rationale.

## Quick Reference

**Logo style:** Terminal Cursor — `josaphat` lowercase mono + accent cursor block
**Tagline:** `From Concept to Code.` (rendered as `// from concept to code`)
**Two palettes:**

| | 04E (Magenta) | 04H (Navy/Green) |
|---|---|---|
| Background | `#0A0A0A` | `#0F172A` |
| Text (dark bg) | `#FFFFFF` | `#FFFFFF` |
| Text (light bg) | `#0A0A0A` | `#0F172A` |
| Accent (cursor) | `#EC4899` | `#10B981` |
| Use for | Promo, social, marketing | App, splash, README, formal |

## Files

### Static logos (SVG)

| File | Purpose |
|---|---|
| `lockup-04E-dark.svg` | Marketing dark variant (480×130) |
| `lockup-04E-light.svg` | Marketing on white (transparent bg) |
| `lockup-04H-dark.svg` | App / formal dark variant |
| `lockup-04H-light.svg` | App / formal on white |
| `icon-04E.svg` | App icon 256×256 (magenta) |
| `icon-04H.svg` | App icon 256×256 (navy/green) |

### Animations (animated SVG + HTML preview + GIF)

| Concept | SVG (SMIL) | HTML preview | GIF (Pillow output) |
|---|---|---|---|
| 02 — Typing Reveal | `animation-02-typing-04E.svg` | `.html` | `.gif` |
| 05 — Glow Pulse | `animation-05-glow-04H.svg` | `.html` | `.gif` |

## Common Tasks

### Use as Windows `.exe` icon

Convert `icon-04H.svg` to `.ico` (multi-size 16/32/48/256):

```powershell
# Option A: online — drop SVG into convertio.co or icoconvert.com
# Option B: ImageMagick if installed:
magick convert -density 384 -background none assets/brand/icon-04H.svg -define icon:auto-resize=16,32,48,256 assets/brand/icon-04H.ico
```

Then reference in `HR-Absensi.spec`:

```python
exe = EXE(
    ...,
    icon='assets/brand/icon-04H.ico',
)
```

### Use logo in app splash (Tkinter)

```python
from tkinter import PhotoImage
splash_img = PhotoImage(file="assets/brand/animation-05-glow-04H.gif", format="gif -index 0")
# For animated, iterate frames manually
```

### Embed in GitHub README

```markdown
![Josaphat Tech Solution](assets/brand/lockup-04H-dark.svg)
```

Animated SVG works on GitHub README natively.

### Regenerate the GIF files

```powershell
py -3 assets/brand/tools/render_gif.py
```

Requires:
- Pillow (`pip install Pillow`) — already in dev environment
- Consolas (Windows default) or JetBrains Mono installed in Fonts

### Convert GIF → MP4 / WebM (smaller, better quality)

```powershell
# Requires ffmpeg
ffmpeg -i animation-02-typing-04E.gif -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" animation-02-typing-04E.mp4
ffmpeg -i animation-05-glow-04H.gif -c:v libvpx-vp9 -b:v 500k animation-05-glow-04H.webm
```

## Font Notes

SVGs use this fallback chain: **JetBrains Mono → Fira Code → Consolas → Courier New → monospace**.
Best appearance: install [JetBrains Mono](https://www.jetbrains.com/lp/mono/). On Windows, Consolas is always present and looks acceptable.

For pixel-perfect fixed rendering (e.g., when sending an SVG to a non-tech recipient), convert text to paths in Inkscape: open SVG → select text → `Path → Object to Path` → save.
