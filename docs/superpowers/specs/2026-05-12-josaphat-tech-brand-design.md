# Brand Spec — Josaphat Tech Solution

**Date:** 2026-05-12
**Type:** Personal freelance developer brand
**Owner:** Josaphat (`josambrosia`)
**Status:** Final (locked 2026-05-12)

## Positioning

Personal freelance developer brand. Single-person operation building practical
business software (HR Absensi being the first product). Target audience:
Indonesian SMB owners + tech-aware clients evaluating a solo dev for custom work.

## Brand Identity

ONE logo structure (terminal-cursor monospace wordmark), ONE palette.

### Palette — Black + Magenta
- Background: `#0A0A0A`
- Text on dark: `#FFFFFF` · Text on light: `#0A0A0A`
- Accent (cursor): `#EC4899` (magenta / hot pink)
- Tagline color (dark bg): `#A3A3A3` · (light bg): `#525252`

Strong, punchy, dev-flavored. Works for both promo/marketing AND app/formal
contexts — the brand voice is consistent.

*Note: an alternate Navy+Green palette (04H) was explored during brainstorm
2026-05-12 but not adopted. See git history for assets if revisiting.*

## Wordmark

`josaphat` lowercase in monospace bold (JetBrains Mono 700, fallback Fira Code →
Consolas → monospace), followed by a solid magenta cursor block. The block
represents an active terminal cursor — signals "this is a developer".

Tagline below in mono medium: `// from concept to code`

## App Icon (Mini Logo)

Square 64×64 master / 256×256 export, rounded corner radius 14:
- Solid black background `#0A0A0A`
- Lowercase `j` in white, monospace bold
- Magenta cursor block to the right of the `j`

Export to `.ico` at 16/32/48/256 for Windows distribution.

## Tagline

**Final:** `From Concept to Code.`
*(English variant of brainstorm #08; alliterative C-C, dev culture, captures
freelance value proposition: "you describe what you want, I deliver code that
runs.")*

## Animation

### Typing Reveal (Animation #02)
- "josaphat" types out letter by letter from left to right
- Magenta cursor follows the type position, blinks at end
- ~4 second loop
- **Use for:** promo videos, video intros, dramatic reveals, GitHub README
  header animation, app splash with motion

## Asset Inventory

```
assets/brand/
├── README.md                              # how to use these assets
├── lockup-04E-dark.svg                    # primary marketing piece (dark bg)
├── lockup-04E-light.svg                   # transparent bg, dark text (invoice)
├── icon-04E.svg                           # 256×256 app icon
├── animation-02-typing-04E.svg            # animated SVG (SMIL)
├── animation-02-typing-04E.html           # standalone HTML preview
├── animation-02-typing-04E.gif            # rendered GIF binary (Pillow)
└── tools/
    └── render_gif.py                      # regenerator script
```

## Where Used

| Context | File |
|---|---|
| App Tkinter splash | `lockup-04E-dark.svg` (or pre-render to PNG) |
| App splash with motion | `animation-02-typing-04E.gif` |
| Windows `.exe` icon | `icon-04E.svg` → export to `.ico` |
| README badge | `lockup-04E-dark.svg` raw URL on GitHub |
| Promo video / social | `animation-02-typing-04E.gif` or `.svg` |
| Invoice / formal doc | `lockup-04E-light.svg` (transparent on white) |
| Business card | `lockup-04E-dark.svg` (back) + `lockup-04E-light.svg` (front) |
| Email signature | `lockup-04E-light.svg` |

## Implementation Notes

- SVGs use system-safe font fallbacks. For guaranteed rendering, embed
  JetBrains Mono via `@font-face` in HTML wrappers, or convert text to paths
  with Inkscape (`File → Save As → Plain SVG` after `Path → Object to Path`).
- For Tkinter splash, the `.gif` output of `render_gif.py` can be loaded via
  `tkinter.PhotoImage` with frame iteration for animation.
- Animated SVGs work natively in modern browsers and on GitHub README files.
- Run `py -3 assets/brand/tools/render_gif.py` to regenerate the GIF
  (requires Pillow + Consolas/JetBrains Mono installed system-wide).

## Decisions Recorded

- **Style:** Terminal Cursor (#04 from brainstorm round 1)
- **Palette:** 04E Black+Magenta (final, single)
- **Tagline:** "From Concept to Code." (08-B; English alliterative)
- **Animation:** #02 Typing Reveal

## Future Iterations

- Hand-tune the `josaphat` wordmark glyphs (custom letterforms) once brand settles
- Generate matching favicon set (16/32/48/180/192/512) when website launches
- Consider Lottie (`.json`) export for richer in-app animation if Tkinter is replaced
