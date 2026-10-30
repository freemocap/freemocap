The FreeMoCap UI is a dense, dark, desktop tool for running a motion-capture pipeline: cameras, calibration, live 2D/3D tracking, recording, playback. Its style system is plain CSS — custom properties for colour, utility classes for layout, BEM-ish component classes — loaded once through `src/index.css → styles/App.css`.

This system keeps that architecture and changes only colour values. **Skull** is the default theme: the logo's teal as the accent and its coral for record and danger, on lightly teal-tinted greys. Four more tints — **Neutral**, **Cool slate**, **Warm graphite**, **Night ink** — re-tint only the greys. **Classic** is `color.css` exactly as it is on disk today, kept for comparison. The *As-built audit* section describes Classic.

## Architecture (keep this)

- **One entry, ordered imports.** `styles/App.css` `@import`s `reset → font → icons → color → animation → …feature sheets → toggle → button-sm → pipelineProgress`. Component-local sheets (`settings-layout.css`, `float-input.css`, `modal-window.css`, `transform-editor.css`) are imported by their TSX.
- **Three colour layers in `color.css`.** (1) Raw ramps `gray-*`, `green-*`, `red-*`, `warning-*`, `blue-*` (100 = lightest, 900 = darkest) plus `*-alpha-NN` tints. (2) Semantic aliases `color-bg-*`, `color-surface-*`, `color-text-*`, `color-border-*`, `color-info|success|warning|danger-*`. (3) Domain aliases `chart-*`, `metric-*`, `log-*`. Components consume layer 2 or 3; never a ramp directly.
- **Utility classes are the API.** Components compose classes like `flex items-center gap-1 p-1 br-1 bg-dark text-white` rather than writing bespoke CSS. Utility names are positional (`p-1` = 4px, `br-2` = 8px), colour utilities are semantic (`text-muted`, `bg-elevated`) with legacy aliases (`text-gray`, `bg-dark`, `bg-middark`, `border-mid-black`).
- **Icons are CSS backgrounds.** `icons.css` declares `--<name>-icon: url(...)` and a `.<name>-icon` class; markup is `span.icon.<name>-icon.icon-size-20`.
- **The settings-layout grammar** (`settings-layout.css`) is the most considered layer: an elevation ladder, hairlines, a fixed control column, contrast-checked text tokens. See the `SettingsSection` component.

## Themes & tints

- **One brand, several tints.** Accent (`blue-*` ramp, teal), danger (`red-*`, coral), live/OK (`green-*`) and caution (`warning-*`) are fixed brand colours, identical in Skull, Neutral, Cool slate, Warm graphite and Night ink. A tint changes only the neutral ramp `gray-*`, the ladder `color-surface-*`, `color-text-help`, `color-text-inactive` and `color-border-control`.
- **Only layer 1 changes.** Every semantic and domain token (`color-bg-*`, `color-text-*`, `log-*`, `metric-*` …) is the same alias in every theme. Components never know which tint is on.
- **How a tint is made.** Each grey is `oklch(L, c, h)`: the tint sets hue `h` and chroma `c` (≤ 0.02). The Skull family lifts the dark rungs by 0.026 L and spreads the surfaces 1.3× so cards and hovers read as separate planes (ground→hover 1.65:1 vs Classic 1.42:1).
- **Contrast is held, not hoped for.** After lifting, muted/help/inactive text is pushed to ≥ 4.5:1 and `color-border-control` to ≥ 3:1 on every surface it sits on, in every tint, and `red-500` is deepened until the Record label reads at ≥ 4.5:1. Check a new tint by reading the contrast figures in the token notes.
- **In code (not built yet).** Write the gray ramp and ladder in `color.css` as `oklch(L calc(var(--tint-c) * k) var(--tint-h))` and set `--tint-h`/`--tint-c` from `[data-tint="…"]` on `<html>`, driven by the existing redux `theme` slice. Accent and status ramps stay static hex. Icons must switch to `mask-image` + `background-color: currentColor` first, or their baked grey ignores the tint.
- **Use the theme names** `skull` (default), `neutral`, `cool`, `warm`, `night`. `classic` is a reference, not a user option.
- **Proposed, not in code:** `color-danger-text` (→ `red-300`) and `color-warning-text` (→ `warning-300`). `color-danger` and `color-warning` are fills; as small text they fail AA in every theme, including Classic.

## Content fundamentals

- Voice is plain, technical and second person where it addresses the user: "Calibrate your cameras", "You are up to date", "Can't highlight this right now — it may be in a collapsed panel. Click Next to continue."
- Section and panel titles use Title Case ("Recording Directory", "Camera Performance Metrics", "Stack Trace"); actions and descriptions use sentence case ("Detect available cameras", "Copy logs to clipboard", "Select camera image rotation").
- Ellipses for in-progress states and opening dialogs: "Waiting for data…", "Report an Issue…", "Filter…". (Some strings use three dots: "Starting in {{countdown}}...".)
- Keyboard hints in parentheses: "Next frame (→ / Shift+→ for 10)".
- Counts are terse: "{{count}} cam", "Cameras ({{count}})".
- No emoji. Copy is translated into 40 locales via `i18n/locales/*.json`; never hard-code English in components. AI-translated locales are flagged with a `translation-badge.ai`.

## Visual foundations

### Colour
- Ground the app in `color-bg-secondary` (Skull #242e2e; Classic #212121) — html, body, header, footer. Go darker (`color-bg-primary`) for tooltips, selected states and wells; go lighter (`color-bg-elevated`) for hover and "on" fills.
- Inside settings surfaces use the ladder instead: `color-surface-ground` → `color-surface-raised` (cards) → `color-surface-control` (inputs). Separate rungs with `shadow-raised-lip` + `shadow-raised-low`, not lighter greys.
- Body text defaults to `color-text-muted` (reset.css); emphasise with `color-text-primary` (`.text-white`); help prose `color-text-help`; inactive-but-real `color-text-inactive`. Reserve `color-text-disabled` for disabled things — it is about 3:1.
- Hue is status: `color-info` (teal; blue in Classic) = brand/selected/info/focus, `color-success` (green) = live/streaming/OK, `color-warning` (orange) = caution, `color-danger` (coral; pink-red in Classic) = error/destructive/record. Exception: SidebarNav uses green for Cameras mode and teal for Playback mode.
- Words in a status colour use `color-danger-text` / `color-warning-text` (proposed); the base tokens are for fills, borders and icons.
- Decorative rules use `color-border-hairline`; anything bounding an interactive control uses `color-border-control` (≥ 3:1).
- Status backgrounds use the `color-*-surface` (10–20% alpha) washes.

### Type
- One family: **Inter** (Google Fonts, opsz 14–32, wght 100–900), fallback system-ui. Monospace for paths, versions, logs and metrics (five different mono stacks exist — see audit).
- The scale is tiny and tight: `title` 13/14/600, `text-bg` 12/17/600 (−0.43px tracking), `text-md` 12/14/500, `text-sm` 11/14/500. Markup pairs a size class with `.text`: `p.text.bg`, `p.text.md`.
- Hierarchy comes from weight and colour (muted → primary), not size. Uppercase + 0.09em tracking only for `settings-group-heading`.
- Numbers that update use `font-variant-numeric: tabular-nums`.

### Spacing, radius, borders
- 4px step: `space-1` 4, `space-2` 8, `space-3` 12, `space-4` 16 via `p-* m-* gap-*` utilities. Settings layout breaks the grid on purpose (14px side padding, 18px indent, 224px control column).
- Radius: `br-1` 4px for buttons and inputs, `br-1-1` 6px for tracks/selects/toasts, `br-2` 8px for cards. `br-pill` for switches and grips.
- Default border width is **1.5px** (`border-1`), not 1px; settings-layout uses 1px hairlines.
- Controls are 25px tall (`h-25`, `icon-size-25`); settings rows 30px; section headers 36px.

### Elevation & depth
- Flat by default. Depth exists only in: tooltips (`shadow-elevated-sharp`), settings cards (`shadow-raised-*`), and `shadow-lg` flyouts. No gradients except the welcome modal image column and the skeleton loader shimmer.

### Motion
- Three speeds in `animation.css`: `--speed-0` 50ms (press), `--speed-1` 120ms (hover colour), `--speed-2` 220ms (reveals, toggles). Keyframes: `slide-up`, `slide-down`, `fadeIn`, `scaleIn`, `spin-ramp` (loader), `skeleton-loader`, `fmcPulse` (live dot). `prefers-reduced-motion` disables `.reveal`.
- Press = `translateY(1px)`. Rotate-buttons spin 45° on hover, 90° on press.

### States
- Hover: background to `color-bg-elevated` (or `color-surface-hover`), text muted → primary.
- Selected: background DARKER (`color-bg-primary`) + primary text.
- On: accent (`color-info-strong`) toggle track; green label for `.activated`.
- Disabled: opacity .5–.6 (`.disabled`), no colour token.
- Focus: 2px `color-info-strong` outline (checkbox); `.focus:ring-*` 3px ring utilities; many controls have no visible focus style.

## Iconography

- Custom single-ink SVGs in `src/assets/icons/` (≈110 files), drawn on a **20px viewBox** (icons.css says 16px with a 1.33px stroke — the files disagree), strokes outlined to fills.
- Ink is baked into each file with Classic values: idle `icon-ink-idle` #9b9b9b, primary #e4e4e4, active #0898ff (Classic `blue-600`), OK #16dd12, warning #e64900. Active states are separate files (`*_active_icon.svg`). Under any other theme these inks are wrong until icons render through `currentColor`.
- Use via `span.icon.<name>-icon.icon-size-20`; 25px hit box for IconButton, 42px in ButtonCard.
- No icon font, no emoji. The Icons asset group holds a representative 28 of the set.

## Imagery & brand marks

- `assets/Logos/freemocap-logo.png`: the FreeMoCap skull — teal (#94c4c7) skull, black keyline, coral-red (#d95157) four-point sparkles. In the Skull themes the teal is closest to `blue-300` (#86c2c5) and the coral to `red-400` (#f56e6f); Classic has neither.
- `assets/Images/splashmodal_art.webp`: 3D-rendered skeleton pointing out of a cold blue/cyan glow, red sparkle in the eye socket — used on the splash modal at 50% logo opacity.
- `logo_name.svg` (splash wordmark) and `inv-edge.svg` are referenced by CSS but absent from the repo.
