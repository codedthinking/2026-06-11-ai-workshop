# AI Slides Template

A [reveal.js](https://revealjs.com/) presentation template for AI-related teaching content, styled with the [9x Academic](https://the9x.ac) design system from Coded Thinking.

## Quick start

1. Clone or use this template repository
2. Edit `index.html` — each `<section>` is one slide
3. Open `index.html` in a browser (no build step needed)

For local development with live reload:

```bash
npx serve .
```

## Slide types included

The template demonstrates these slide types:

| Slide type | Use case |
|---|---|
| Title slide | Opening/closing with 9x grid mark |
| Section divider | Chapter breaks with mono kicker |
| Text + bullets | Regular content slides |
| Code block | Syntax-highlighted code with line highlighting |
| Side-by-side code | Before/after comparisons |
| Terminal | CLI demos with prompt styling |
| Video embed | YouTube/Vimeo iframes (lazy-loaded) |
| Table | Data with mono headers |
| Math | KaTeX-rendered equations |
| Blockquote | Attributed quotations |
| Callout boxes | Warning, tip, and info panels |
| Two-column layout | Flexible side-by-side content |
| Fragment animation | Progressive reveal of list items |

## Design system

The theme implements the 9x Academic sub-brand of Coded Thinking:

- **Dark navy ground** (`#1D1D40`) — never black
- **Lavender-grey text** (`#D4D2E3`) on raised surfaces
- **Brand red** (`#E61E25`) for accents, markers, controls
- **Electric teal** (`#35E0D8`) for links, code highlights, AI cues
- **Inter** for body text, **DM Mono** for code and data labels
- Asymmetric border radii (`12px 2px 12px 12px`) on code and terminal blocks

## Features

- No build step — CDN-loaded reveal.js 5.1
- KaTeX math rendering
- Code syntax highlighting with line numbers
- Speaker notes (press `S`)
- Slide numbers
- PDF export (append `?print-pdf` to URL, then print)
- `transition: 'none'` for clean academic presentations

## Keyboard shortcuts

| Key | Action |
|---|---|
| `→` / `←` | Navigate slides |
| `S` | Speaker notes |
| `O` | Overview mode |
| `F` | Fullscreen |
| `Esc` | Exit overview/fullscreen |

## Customization

Edit `css/theme-9x.css` to adjust colors, typography, or component styles. All design tokens are CSS custom properties in `:root`.

To use Markdown instead of HTML slides, see the [reveal.js Markdown plugin](https://revealjs.com/markdown/).

## License

MIT
