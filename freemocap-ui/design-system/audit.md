# As-built audit

What the CSS on disk actually does, measured. This is the **Classic** theme; the Skull themes answer sections 1, 2 and 4.

## 1. Why it reads "gunmetal"

- **The whole neutral range used for surfaces spans #111 → #3a3a3a.** Ground (`color-bg-secondary` #212121), wells (#141414), cards (#191919), controls (#202020), hover (#3a3a3a). Five of the six sit within 1.17:1 of each other (#111 → #212121); even hover (#3a3a3a) is only 1.4:1 above the ground. The eye gets almost no depth cue, so everything collapses into one flat dark plane.
- **The greys are perfectly neutral (R=G=B).** No warm or cool cast at all — that is what makes it feel metallic/industrial rather than inviting.
- **Selection goes darker, not brighter.** Segmented control, selected buttons and the tooltip all sink to #141414. Active things recede.
- **Status hues are fully saturated, the neutrals are fully desaturated.** `green-100` #16dd12 and `blue-600` #0898ff against flat grey read as terminal/dev-tool, not as a brand.
- **Depth exists on only one surface** (settings cards). Everything else is flat fills with 1.5px mid-grey borders.

## 2. Brand vs UI palette

| | Logo / splash | UI tokens |
|---|---|---|
| primary hue | teal #94c4c7 | blue #0898ff / #2ba4ff |
| accent | coral #d95157 | pink-red #d7184b (danger only) |
| keyline | pure black | none |
| mood | illustrative, playful, sticker-like | neutral tool chrome |

The UI has no token for either brand colour. The closest UI accent to the logo's coral is `color-danger` — which the UI reserves for errors and record.

## 3. Two surface systems in parallel

- **Legacy:** `color-bg-primary/secondary/tertiary/elevated/idle` from the gray ramp. Used by nearly every component.
- **Ladder:** `color-surface-ground/raised/control` — hard-coded hexes deliberately *off* the ramp, used only by settings-layout. The source comment explains why ("the ramp is a palette, this is a ladder").
- `color-bg-secondary` (#212121, the app ground) is *lighter* than `color-surface-control` (#202020, the top ladder rung). A settings card dropped onto the app ground sinks rather than rises.

## 4. Contrast (WCAG 2, measured)

| token | on bg-secondary #212121 | on surface-raised #191919 | on bg-elevated #3a3a3a |
|---|---|---|---|
| text-primary #e4e4e4 | 12.7 | 13.8 | 9.0 |
| text-secondary #cdcdcd | 10.1 | 11.1 | 7.2 |
| text-muted #aaaaaa | 6.9 | 7.6 | 4.9 |
| text-help #949494 | 5.3 | 5.8 | **3.8** |
| text-inactive #8a8a8a | 4.7 | 5.1 | **3.3** |
| text-disabled #606060 | **2.6** | **2.8** | **1.8** |
| border-primary #606060 | **2.6** (control boundary) | **2.8** | — |
| border-control #6e6e6e | 3.2 | 3.45 | 2.2 |
| warning #e64900 (as text) | **4.1** | 4.45 | 2.9 |
| danger #d7184b (as text) | **3.2** | 3.45 | 2.2 |

- `SubactionHeader` sets real copy in `text-disabled` (2.6:1).
- Toggle-off ring and most input borders use `border-primary` (2.6:1); only settings-layout upgrades to `border-control`.
- Toasts, update banners and the toggle are colour-only status (no icon/word) — and green vs red at similar lightness.

## 5. Referenced but undefined (22 tokens)

Rules using these silently render nothing:

- `camera.css` uses 16 tokens it lists in a *commented-out* "REQUIRED MISSING TOKENS" block: `color-white-alpha-40/45/60`, `overlay-50/65/75`, `red-500-alpha-15/40`, `color-success-alpha-08/10/20`, `color-warning-alpha-06/08/15/20`, `color-warning-soft`.
- `components.css`: `color-text-secondary-alpha-10` (input focus ring), `color-text-secondary-alpha-20` (update progress track — invisible), `color-accent` (connection-idle outline).
- `calibration-module.css`: `color-bg-darker`. `log-terminal.css`: `color-text-tertiary`. `tutorial.css`: `color-border` (has fallback). `pipelineProgress.css`, `transform-editor.css`: `color-error` (fallback #ed5362 — a red not in the ramp).

## 6. Hard-coded values outside color.css (≈30 live)

- `playback.css`: timeline gradient in Tailwind blue `#3b82f6` (not the FreeMoCap blue) and `#212121`; focus glow `rgba(59,130,246,.3)`.
- `pipelineProgress.css`: `border-color: #FF00FF` (debug magenta left in).
- `components.css`: `.unit-text { color: #007acc }` (VS Code blue); drag-state `rgba(255,255,255,.08)`; resize grip `background: white`.
- `animation.css`: skeleton shimmer `#1b1b1b / #2a2a2a`.
- `tutorial.css`: spotlight `#4aa3ff` fallback + pulse `rgba(74,163,255,…)` — a third blue.
- `float-input.css`, `transform-editor.css`: `color-mix()` with `#aaa` fallbacks.
- `settings-layout.css`: header hover `rgba(255,255,255,.022)`.
- Icon SVGs: ink `#9b9b9b` (off-ramp), `stream_icon.svg` uses #060606/#1b1b1b/#4f4f4f, `streaming_icon.svg` uses iOS green `#34c759` (not `green-*`).

## 7. Structural quirks

- **Dark only.** A Redux `theme` slice toggles `light`/`dark` and the copy has "Switch to light mode", but no CSS reacts to it — there is no `[data-theme]` selector anywhere.
- `reset.css` paints body `background: var(--color-text-primary)` (light grey); `App.css` later overrides it to `color-bg-secondary`. A text token used as a fill.
- `.primary` buttons fill with `color-text-primary` and set their label to `color-text-primary` too — white on white if ever used.
- `.bg-pink` maps to `color-success` (green). `.border-pink` and `.border-red` are both `color-danger`.
- `.mt-1…mt-4` and `.overflow-hidden` are declared twice; `.icon-size-25` twice; `.splash-overlay` twice with different z-index (100 vs 50).
- Five monospace stacks: `monospace`, `"Courier New"`, `"JetBrains Mono", "Fira Code"`, `ui-monospace, Menlo, Consolas`, plain `system-ui` on `.form-control`.
- `@media screen (min-width : 1920px)` in components.css is invalid syntax (missing `and`), and the rule inside targets `ds\:video-tile`, which matches nothing.
- `.font-mono` uses bare `monospace`; settings chips use `ui-monospace`.
- App.css carries a "MISSING SEMANTIC TOKENS YOU SHOULD ADD" comment (`color-link`, `color-scrollbar-thumb`) — still not added.
- Icon docs (16px / 1.33px stroke) contradict the files (20px viewBox).

## 8. What already works and should survive

- The three-layer token architecture and the single ordered import chain.
- Semantic naming for status (`info/success/warning/danger` × `strong/muted/idle/surface`).
- The settings-layout grammar: ladder, hairlines vs control borders, required `info` on every row, summaries on collapsed sections, inactive-but-readable rows, contrast-annotated tokens.
- Domain token layers (`log-*`, `metric-*`, `chart-*`) that let feature UIs re-skin without touching components.
- Reduced-motion support and a small, named speed scale.
