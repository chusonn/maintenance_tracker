---
name: design-system
description: UI conventions for the Maintenance Tracker — design tokens, components, styling rules. Use for ANY template/CSS/UI change - edit a page, add a button, style a table, adjust colors or spacing.
---

# Design system

Clean-SaaS design, token-based. Everything visual flows from CSS custom properties in `app/static/css/app.css`; Bootstrap 5.3 (CDN) supplies only grid + JS behaviors (modal/collapse). **Never add inline `<style>` blocks or hex colors in templates — extend app.css tokens/components instead.**

## Tokens (in `:root`, all prefixed `--mt-`)

- **Neutrals** `--mt-gray-25 … --mt-gray-900` (Untitled-UI-like scale); aliases `--mt-bg`, `--mt-surface`, `--mt-border`, `--mt-text`, `--mt-text-secondary`, `--mt-text-muted`.
- **Accent** (indigo) `--mt-accent-50/100/500/600/700` — buttons, active nav, focus rings.
- **Semantic** `--mt-{success,info,warning,danger,purple}-{50,600,700}`.
- **Type** `--mt-font` (Inter + system fallback), sizes `--mt-text-xs … --mt-text-2xl`.
- **Space/radius/shadow**: `--mt-space-1…6`, `--mt-radius-sm/md/lg`, `--mt-shadow-xs/sm/md`.
- Layout: `--mt-sidebar-width` (248px), `--mt-topbar-height` (60px).

## Components (classes in app.css, macros in templates)

- Shell: `.mt-shell` > `.mt-sidebar` (sticky, collapses <992px via `data-role="sidebar-toggle"`) + `.mt-main` (`.mt-topbar` + `.mt-content`, max-width 1280px).
- Macros in `_components.html`: `page_header(title, subtitle)` (use `{% call %}` to add action buttons), `stat_card(label, value, icon, tone)`, `status_badge(status)`, `priority_badge(priority)`, `followup_badge(job)`, `empty_state(icon, title, msg, action_url, action_label)`, `form_field/form_textarea/form_select`, `csrf()`, `pagination(page_obj, endpoint)`.
- Icons: `_icons.html` `icon(name, size)` — inline Lucide SVGs. Add new icons there; never add an icon font.
- Cards: `.mt-card` (+ `.mt-card-header`/`.mt-card-title`/`.mt-card-body`; add `.flush` + `.mt-table-wrap` for full-bleed tables).
- Tables: `.mt-table`; `td.primary` for the leading/name column; row buttons inside `.mt-row-actions`.
- Toasts: flash messages render in `.mt-toast-region` (base.html) with categories success/warning/danger/info; auto-dismiss 5 s via app.js.
- Deletes: use the shared `#mtDeleteModal` pattern (`data-delete-url` + `data-delete-label` on the trigger) or `form[data-confirm="…"]` for simple confirms. Danger buttons are `.btn-outline-danger`/`.btn-danger`.
- Shared form partials: `_flat_form.html`, `_contractor_form.html`.

## Dark mode

- Theme = `data-theme` + `data-bs-theme` on `<html>`, set **before first paint** by `static/js/theme.js` (priority: `?theme=` query param — handy for screenshots, not persisted — then localStorage `mt-theme`, then OS `prefers-color-scheme`). The topbar toggle (`data-role="theme-toggle"`, handled in app.js) flips both attributes, persists the choice, and dispatches `mt:themechange`; analytics.js listens and rebuilds its charts so they re-read tokens.
- All dark values live in **one `[data-theme="dark"]` block** in app.css, directly after `:root`. It remaps the gray scale (roles preserved: higher step = stronger ink), turns semantic `-50`s into deep tints, `-700`s into light badge text, keeps `accent-600/700` for buttons, and bridges `--bs-body-bg`/`--bs-border-color`/etc. so Bootstrap modals, forms and pagination sit on the same surfaces.
- **Role tokens** (`--mt-link`, `--mt-link-hover`, `--mt-nav-active-text`, `--mt-chart-accent`, `--mt-chart-neutral`, `--mt-chart-neutral-deep`, `--mt-chart-neutral-soft`) exist because one tint step can't serve both modes (a 700 is a dark hover bg in light mode but light badge text in dark). In `:root` they alias the scales; the dark block remaps them independently. `danger-700` is additionally special-cased on `.btn-danger`/`.btn-outline-danger` in dark.
- **Any new color must be defined in both `:root` and the dark block** (or be an alias of tokens that already are). Chart colors must also pass the dataviz skill's `validate_palette.js` against `--mt-surface` in **both** modes — the dark chart palette (cyan info `#00a0e4`, rose danger `#e31b63`, violet `#875bf7`, greens/ambers, two grays) was *selected* per-slot to pass CVD + contrast checks, never auto-inverted. Re-validate if you touch any of it.
- Verify UI changes in **both themes** (append `?theme=dark` / `?theme=light` to any URL) on seeded and empty databases.

## Rules

- Currency renders via the `| gbp` filter (£, thousands separators); dates via `| ukdate` (dd/mm/yyyy). Missing values show "—". Never hand-format either.
- Status colors: Completed=success, In Progress=info, Scheduled=purple, Pending=neutral, Cancelled=muted+strikethrough. Priority: Urgent=danger, High=warning, Medium=info, Low=neutral. (Chart colors must read these same tokens.)
- Every list view has an empty state; every destructive action confirms; every POST form includes `{{ csrf() }}`.
- Verify UI changes on BOTH seeded and empty databases, and at ~400px width.
