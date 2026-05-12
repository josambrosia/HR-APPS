# Josaphat Tech Solution — Brand Assets

Personal freelance developer brand. See [brand spec](../../docs/superpowers/specs/2026-05-12-josaphat-tech-brand-design.md) for full design rationale.

## Quick Reference

- **Logo style:** Terminal Cursor — `josaphat` lowercase mono + magenta cursor block
- **Tagline:** `From Concept to Code.` (rendered as `// from concept to code`)
- **Palette:**

| | Value |
|---|---|
| Background | `#0A0A0A` |
| Text on dark bg | `#FFFFFF` |
| Text on light bg | `#0A0A0A` |
| Accent (cursor) | `#EC4899` (magenta) |
| Tagline (dark bg) | `#A3A3A3` |
| Tagline (light bg) | `#525252` |

## Files

### Static logos (SVG)

| File | Purpose |
|---|---|
| `lockup-04E-dark.svg` | Marketing on dark bg (480×130) |
| `lockup-04E-light.svg` | Marketing on white / transparent bg |
| `icon-04E.svg` | App icon 256×256 (rounded square) |

### Animation (animated SVG + HTML preview + GIF binary)

| File | Notes |
|---|---|
| `animation-02-typing-04E.svg` | Vector animation (SMIL), embed in browser/README |
| `animation-02-typing-04E.html` | Standalone HTML preview |
| `animation-02-typing-04E.gif` | Rendered binary GIF (96 frames @ 24fps, ~82 KB) |

## Common Tasks

### Use as Windows `.exe` icon

Convert `icon-04E.svg` to `.ico` (multi-size 16/32/48/256):

```powershell
# Option A: online — drop SVG into convertio.co or icoconvert.com
# Option B: ImageMagick if installed:
magick convert -density 384 -background none assets/brand/icon-04E.svg `
  -define icon:auto-resize=16,32,48,256 assets/brand/icon-04E.ico
```

Then reference in `HR-Absensi.spec`:

```python
exe = EXE(
    ...,
    icon='assets/brand/icon-04E.ico',
)
```

### Use logo in app splash (Tkinter)

```python
from tkinter import PhotoImage
splash_img = PhotoImage(file="assets/brand/animation-02-typing-04E.gif", format="gif -index 0")
# For animated splash, iterate frames manually with .after()
```

### Embed in GitHub README

```markdown
![Josaphat Tech Solution](assets/brand/lockup-04E-dark.svg)
```

Animated SVG also works on GitHub README natively.

### Regenerate the GIF

```powershell
py -3 assets/brand/tools/render_gif.py
```

Requires:
- Pillow (`pip install Pillow`) — already in dev environment
- Consolas (Windows default) or JetBrains Mono installed in system Fonts

### Convert GIF → MP4 / WebM (smaller, better quality for video)

```powershell
# Requires ffmpeg
ffmpeg -i assets/brand/animation-02-typing-04E.gif `
  -movflags faststart -pix_fmt yuv420p `
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" `
  assets/brand/animation-02-typing-04E.mp4
```

## Font Notes

SVGs use this fallback chain: **JetBrains Mono → Fira Code → Consolas → Courier New → monospace**.

Best appearance: install [JetBrains Mono](https://www.jetbrains.com/lp/mono/). On Windows, Consolas is always present and looks acceptable.

For pixel-perfect fixed rendering (e.g., when sending an SVG to a non-tech recipient), convert text to paths in Inkscape: open SVG → select text → `Path → Object to Path` → save.
