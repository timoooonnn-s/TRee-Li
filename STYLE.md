# TRee-Li Style Guide

One blue family in several shades, calm and modern, plus a few small, bright highlights.
The code side lives in `PALETTE` in `tree-li`. This page is the reference for both.

## Palette

| Name | Design hex | Terminal (xterm-256) | Used for |
|---|---|---|---|
| **Navy** | `#000078` | 18 `#000087` | input-field text |
| **TRee Blue** (primary) | `#003cb4` | 25 `#005faf` | active tab, selection bar, divider lines |
| **Signal Blue** | `#1964dc` | 26 `#005fd7` | cursor block |
| **Steel** | `#6487be` | 67 `#5f87af` | dialog window surface, secondary text, hints |
| **Sky** | `#9bbdf5` | 111 `#87afff` | brand name, column headers, keys, idle input fields |
| **Mist** | `#e6e9ff` | 189 `#d7d7ff` | active input field, frames, messages, sort arrow |
| White | `#ffffff` | 231 | text on TRee Blue / Steel |
| Fade | `#949494` | 246 | everything behind an open dialog |

**Highlights.** These are small and bright on purpose, and the only colours outside the blue family:

| Name | Terminal | Used for |
|---|---|---|
| **Highlight Orange** | 214 `#ffaf00` | favourite star `*` |
| Up | 78 `#5fd787` | `● up`, `● open` |
| Down | 203 `#ff5f5f` | `● down`, `● closed`, `● no-answer`, errors |
| Wait | 179 `#d7af5f` | `● wait`, "running" |

## Rules

- **Light on dark, strong as background.** Sky and Mist carry text; TRee Blue and Steel are surfaces.
  Body text uses the terminal's own foreground, so light terminal themes still work.
- **Highlights stay small:** one character or one word (a star, a dot, a status). Never colour whole rows with them.
- **Search matches:** the matched letters are Sky, bold and underlined (Mist on the selection bar).
- **Layout:** top bar → divider line → tabs → search → table → divider line → footer with key hints.
  Two columns of margin on the left; blocks are separated by space and thin lines, not boxes.
- **Dialogs:** the screen behind fades to Fade grey. The window is a Steel panel with a thin
  rounded Mist frame that holds the title (`╭─ Login · subtitle ─╮`). No shadows.
- **Full-screen views** (ping, traceroute, details, help) reuse the same top bar and footer.
- **Symbols:** Unicode only for characters in common Windows terminal fonts:
  `─ │ ╭ ╮ ╰ ╯ ▌ ● › ‹ ▲ ▼ · ← → ↑ ↓ • …`. Every one has an ASCII fallback (`--ascii`).
- **Text:** short, lower-case labels (`run`, `sort`, `favourite`). Column headers are UPPERCASE.
  Messages start with `●`.

## Fallbacks

| Terminal | Behaviour |
|---|---|
| 256 colours (Tabby, `TERM=xterm-256color`) | full palette as above |
| 8 colours (PuTTY default `TERM=xterm`) | blue / cyan / white; star yellow; status green / red |
| no colours | bold, reverse and underline only |
| no UTF-8 / `--ascii` | `- \| + > * ^ v` instead of lines and symbols |

## For docs and web pages

```css
:root {
  --treeli-navy:        #000078;
  --treeli-blue:        #003cb4;   /* primary */
  --treeli-signal:      #1964dc;
  --treeli-steel:       #6487be;
  --treeli-sky:         #9bbdf5;
  --treeli-mist:        #e6e9ff;
  --treeli-highlight:   #ffaf00;   /* small accents only */
  --treeli-up:          #5fd787;
  --treeli-down:        #ff5f5f;
  --treeli-wait:        #d7af5f;
}
```
