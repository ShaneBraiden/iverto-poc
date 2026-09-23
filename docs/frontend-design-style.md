# Frontend Design Style

Design reference for `frontend/` (the hostel management web dashboard). Documents the
system that already exists in code — mainly `frontend/src/index.css` — so new pages and
components stay consistent instead of each one inventing its own button, card, or badge.

If you change a token or component class in code, update this doc in the same PR. If they
drift, the code wins; fix the doc to match.

**In this repo** the dashboard implements the same tokens, class names and values in plain
CSS (`frontend/src/styles.css`) rather than Tailwind — the POC has no Tailwind, Redux or
React Router. Everything below applies as written except where it names those libraries or
`src/index.css`; badge colours are `.badge-emerald` / `-blue` / `-orange` / `-rose` /
`-gray` classes carrying the same `50/700/200` hexes.

## Stack

- **React 19 + Vite + TypeScript**, React Router 7, Redux Toolkit for state.
- **Tailwind CSS v4** via `@tailwindcss/vite` — tokens defined with `@theme` in
  `src/index.css`, not a `tailwind.config.js`.
- **Poppins** (`@fontsource/poppins`, weights 300–700) is the only font.
- Icons are **lucide-react** (primary) — `react-icons` also exists for a few holdovers but
  new work should use lucide.

## Design tokens (`src/index.css`)

```css
@theme {
  --color-primary-start: #cd0447;
  --color-primary-end: #e91e63;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-surface: rgba(255, 255, 255, 0.85);
  --color-bg-start: #fafafa;
  --color-bg-end: #f5f5f5;
  --font-sans: 'Poppins', sans-serif;
}
:root {
  --brand: #cd0447;
  --brand-ring: rgba(205, 4, 71, 0.25);
  --radius-field: 0.75rem;
  --shadow-soft: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
}
```

- **Brand** is a pink/magenta gradient, `#cd0447 → #e91e63`, used on primary buttons and
  the login backdrop. `--brand` (`#cd0447`) is the flat fallback (focus rings, spinners,
  required-field asterisks).
- **Semantic colors** — `success` (`#10b981`), `warning` (`#f59e0b`), `danger` (`#ef4444`)
  — plus soft Tailwind palette shades (`emerald`, `blue`, `orange`, `rose`, etc. at
  `-50/-700/-200`) for badges. Don't invent new hexes for state colors; reuse these.
  Both live under `@theme` so they're also usable as Tailwind utilities
  (`bg-success`, `text-danger`, …).
- Page background is a soft diagonal gradient (`--color-bg-start` → `--color-bg-end`), not
  flat white — see `body` in `index.css`.
- Body text defaults to `#1f2937` (gray-800).

## Layout shell

- `DashboardLayout` (`src/layouts/DashboardLayout.tsx`): fixed left sidebar (collapsible,
  state persisted in `localStorage` under `iverto.sidebar.collapsed`) + top bar + content
  outlet. Nav items are grouped by intent (**Overview / Daily operations / Devices /
  Administration**), not a flat list — group new pages by what the user is trying to do,
  not by data model.
- Nav visibility is role-gated per item (`roles: string[]` on `NavItem`) — admin, warden,
  security, superadmin.
- Every page opens with `PageHeader` (`src/components/ui/PageHeader.tsx`): `title` (2xl/3xl
  bold), optional `subtitle` (gray-500), `actions` (top-right on desktop, wraps full-width
  on mobile), optional `filters` row underneath. Don't hand-roll page headers.

## Surfaces

- **Glassmorphism** is the default surface treatment, not flat cards:
  - `.glass` — translucent white (85%), `blur(20px)`, soft border, soft shadow. Use for
    prominent panels (login card, modals).
  - `.glass-panel` — lighter variant (60% opacity, `blur(16px)`) for secondary surfaces.
- `.card` — `border-radius: 20px`, lifts on hover (`translateY(-4px)` + deeper shadow),
  smooth `cubic-bezier(0.4,0,0.2,1)` transition. Use for dashboard widgets, clickable
  summary tiles.
- `.card-static` — same shape, hover lift disabled. Use for anything that holds a table or
  large content — a table shouldn't feel like it's floating away as you read a row.
- Radii: `20px` for cards, `0.75rem` (`--radius-field`) for inputs, fully rounded
  (`9999px`, pill) for buttons and badges.

## Buttons

Three variants, all pill-shaped (`border-radius: 9999px`), `padding: 0.5rem 1.25–1.5rem`,
`font-weight: 500`, `inline-flex` with `gap: 0.5rem` for icon + label:

| Class | Use | Look |
|---|---|---|
| `.btn-primary` | Main call-to-action, one per view | Brand gradient fill, white text, shadow that deepens + lifts 2px on hover |
| `.btn-secondary` | Default / cancel / secondary actions | White fill, gray border, text turns brand-colored on hover |
| `.btn-danger` | Destructive actions | White fill, red border/text, tints red on hover |
| `.icon-btn` | Icon-only, row actions / toolbars | Transparent, square padding, `0.75rem` radius, subtle gray tint on hover |

All variants share a disabled state (`opacity: 0.6`, no cursor, no lift, no shadow). Use
`confirmAction` (`src/components/ui/ConfirmDialog.tsx`) before anything a `.btn-danger`
triggers — don't fire destructive actions straight off the click.

## Forms

- `.field` — the one input class: `0.75rem` radius, gray-200 border, white background,
  `0.9375rem` text. Hover darkens the border; focus swaps to `--brand` border + a 3px
  brand-tinted ring (`--brand-ring`). Disabled/readonly get a gray-50 fill.
- On mobile (`≤640px`) `.field` font-size is forced to `16px` — below that, iOS Safari
  zooms the viewport on focus. Never drop below 16px on a mobile-visible input.
- `select.field` gets a custom chevron (inline SVG background), not the browser default.
- Labels/hints/errors: `.field-label` (bold, gray-700, `0.8125rem`), `.field-hint`
  (gray-500, `0.75rem`), `.field-error` (red-600, `0.75rem`, sits directly under the field
  it belongs to — not in a toast or a popup). `.field-required::after` appends a
  brand-colored `*`.
- Invalid state: `.field-invalid` (red border + faint red fill), with its own stronger
  focus ring in red when combined with `:focus`.

## Tables

`.data-table` — sticky, blurred header (`position: sticky; backdrop-filter: blur(8px)`) so
column meaning survives scrolling; uppercase gray-500 header text, `0.04em` tracking.
Rows highlight on hover; row-level actions (`.row-actions`) stay at `opacity: 0.4` until
the row is hovered/focused (always visible on touch — `@media (hover: none)`), so a
dense table doesn't look cluttered with icons by default.

Loading state: `TableSkeleton` (`src/components/ui/States.tsx`) — draws a fake header +
staggered-width shimmering rows sized to the real column count, not a spinner, so the
layout doesn't jump when data arrives.

Empty / no-results state: `EmptyState` / `NoResultsState` (same file) — icon in a rounded
gray tile, a title that names *why* it's empty, and (for search) a "Clear search" action.
Never ship a bare "No data" table.

## Badges

`.badge` — pill, `0.6875rem` bold text, `0.02em` tracking, `1px` border. Color is supplied
by pairing with soft Tailwind utilities, not a new class per status:

```
bg-emerald-50 text-emerald-700 border-emerald-200   /* active / success */
bg-blue-50    text-blue-700    border-blue-200      /* in / info */
bg-orange-50  text-orange-700  border-orange-200    /* out / warning */
```

Follow the `bg-{color}-50 text-{color}-700 border-{color}-200` pattern for any new status;
pick the Tailwind hue that best matches the semantic (red/rose for danger, gray for
neutral/inactive).

## Motion

- Standard easing: `cubic-bezier(0.4, 0, 0.2, 1)` for card/button interactions.
- Named keyframe utilities available: `.animate-fade-in-up`, `.animate-scale-in`,
  `.animate-slide-in-right` (panel/toast entrances), `.animate-overlay-in` (modal
  backdrops), `.pulse-green` / `.alert-pulse` (live status indicators — success/danger
  ring pulses).
- Everything respects `prefers-reduced-motion: reduce` globally (animations collapse to
  `0.01ms`, hover-lift transforms are disabled) — don't add an animation that bypasses
  this block.

## Accessibility

- One global focus style: any focusable element gets a 2px solid `--brand` outline with
  2px offset (`:focus-visible`), not per-component focus styling.
- Required fields are marked in text (`.field-required::after`), not color alone.
- Reduced motion is honored globally (see Motion above).

## Misc

- Custom thin scrollbar (8px, dark-on-transparent) is global; use `.scrollbar-none` to
  suppress it (e.g. horizontally-scrolling chip rows) without falling back to the browser
  default.
- The login page (`Login.tsx` + `.login-bg` / `.login-grid` / `.login-orb` / `.login-rule`)
  is the one place with bespoke decoration — a radial-gradient backdrop, a faint masked
  grid, and drifting blurred "orb" shapes, built in CSS so nothing is fetched over the
  network. Don't reuse Cloudinary-hosted background images for new decorative surfaces —
  follow this CSS-only pattern instead.
- Reusable primitives live in `src/components/ui/`: `Modal`, `ConfirmDialog`, `Toast`,
  `PageHeader`, `SearchInput`, `States` (`EmptyState`/`NoResultsState`/`TableSkeleton`/
  `CenteredSpinner`). Reach for these before writing a new one-off.
