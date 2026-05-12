# Brand Spec — Josaphat Tech Solution

**Date:** 2026-05-12
**Type:** Personal freelance developer brand
**Owner:** Josaphat (`josambrosia`)
**Status:** Approved (interactive brainstorm 2026-05-12)

## Positioning

Personal freelance developer brand. Single-person operation building practical
business software (HR Absensi being the first product). Target audience:
Indonesian SMB owners + tech-aware clients evaluating a solo dev for custom work.

## Logo System — Two-Palette

ONE logo structure (terminal-cursor monospace wordmark) in TWO palettes for
different contexts. Both palettes share **dark base** for brand cohesion.

### Palette 04E — Black + Magenta
- Background: `#0A0A0A`
- Text on dark: `#FFFFFF` · Text on light: `#0A0A0A`
- Accent (cursor): `#EC4899` (magenta)
- Use for: promo videos, social media, marketing site, anything punchy

### Palette 04H — Navy + Green
- Background: `#0F172A` (slate-900)
- Text on dark: `#FFFFFF` · Text on light: `#0F172A`
- Accent (cursor): `#10B981` (emerald)
- Use for: app splash, loading screens, README badges, "trustworthy" contexts

## Wordmark

`josaphat` lowercase in monospace bold (JetBrains Mono 700, fallback Fira Code →
Consolas → monospace), followed by a solid cursor block in the accent color.
The block represents an active terminal cursor — signals "this is a developer".

Tagline below in mono medium: `// from concept to code`

## App Icon (Mini Logo)

Square 64×64 master / 256×256 export, rounded corner radius 14:
- Solid dark background per palette
- Lowercase `j` in white, monospace bold
- Accent cursor block to the right of the `j`

Export to `.ico` at 16/32/48/256 for Windows distribution.

## Tagline

**Primary (final):** `From Concept to Code.`
*(English variant of brainstorm #08; alliterative C-C, dev culture, captures
freelance value proposition: "you describe what you want, I deliver code that
runs.")*

## Animation Set

### Animation 02 — Typing Reveal (palette 04E)
- "josaphat" types out letter by letter
- Magenta cursor follows, blinks at end
- ~4 second loop
- Use for: promo videos, video intros, dramatic reveals

### Animation 05 — Glow Pulse (palette 04H)
- Static "josaphat" wordmark
- Green cursor with pulsing glow (2-second breath)
- Cursor also blinks (1-second cycle)
- Loops infinitely, calm
- Use for: app splash screens, loading states, ambient

## Asset Inventory

```
assets/brand/
├── README.md
├── lockup-04E-dark.svg       # primary marketing piece (dark bg)
├── lockup-04E-light.svg      # transparent bg, dark text
├── lockup-04H-dark.svg
├── lockup-04H-light.svg
├── icon-04E.svg              # 64×64 app icon (dark bg)
├── icon-04H.svg
├── animation-02-typing-04E.svg    # animated SVG (SMIL)
├── animation-02-typing-04E.html   # standalone HTML preview
├── animation-05-glow-04H.svg
├── animation-05-glow-04H.html
├── animation-02-typing-04E.gif    # generated GIF (Pillow output)
├── animation-05-glow-04H.gif
└── tools/
    └── render_gif.py             # Pillow-based GIF generator
```

## Where Used

| Context | File |
|---------|------|
| App Tkinter splash | `lockup-04H-dark.svg` (or pre-render PNG) |
| App splash with motion | `animation-05-glow-04H.gif` (rendered to PNG frames) |
| Windows `.exe` icon | `icon-04H.svg` → export to `.ico` |
| README badge | `lockup-04H-dark.svg` raw URL on GitHub |
| Promo video / social | `animation-02-typing-04E.gif` or `.svg` |
| Invoice / formal doc | `lockup-04H-light.svg` (transparent on white) |
| Business card | Either palette; 04H more conservative |
| Email signature | `lockup-04H-light.svg` |

## Implementation Notes

- SVGs use system-safe font fallbacks. For guaranteed rendering, embed
  JetBrains Mono via `@font-face` in HTML wrappers, or convert text to paths
  with Inkscape (`File → Save As → Plain SVG` after `Path → Object to Path`).
- For Tkinter splash, the `.gif` output of `render_gif.py` can be loaded via
  `tkinter.PhotoImage` with frame iteration for animation.
- Animated SVGs work natively in modern browsers and on GitHub README files.
- Run `py -3 assets/brand/tools/render_gif.py` to regenerate `.gif` files
  (requires Pillow + Consolas/JetBrains Mono installed system-wide).

## Decisions Recorded

- **Style:** Terminal Cursor (#04 from brainstorm round 1)
- **Palettes:** 04E + 04H (both finalized; cohesion via dark base)
- **Tagline:** "From Concept to Code." (08-B; English alliterative)
- **Animations:** #02 Typing Reveal (promo) + #05 Glow Pulse (loading)

## Future Iterations

- Hand-tune the `josaphat` wordmark glyphs (custom letterforms) once brand is settled
- Generate matching favicon set (16/32/48/180/192/512) when website launches
- Consider Lottie (`.json`) export for richer in-app animation if Tkinter is replaced
- Tagline may evolve as brand grows — current works for solo freelance phase
