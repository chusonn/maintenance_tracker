---
name: design-system
description: UI conventions for the Maintenance Tracker — design tokens, components, styling rules. Use for ANY template/CSS/UI change - edit a page, add a button, style a table, adjust colors or spacing.
---

# Design system

> **STUB** — the clean-SaaS redesign has not landed yet. Until it does, the only binding rules are the ones below. This file gets completed (real token names, component macros) during the redesign phase.

Binding rules already in force:

- **No new inline `<style>` blocks in templates.** Shared styling belongs in a stylesheet (post-redesign: `app/static/css/app.css`).
- **Currency renders as £ (GBP), dates as UK `dd/mm/yyyy`** — everywhere, no exceptions.
- Status colors: Completed=green/success, In Progress=blue/primary, Scheduled=info, Pending=neutral, Cancelled=muted. Priority: Urgent=red, High=amber, Medium=blue, Low=gray.
- Every list view needs a designed empty state (icon + one-line explanation + primary action), not a bare empty table.
- Buttons/links that delete anything must be visually distinct (danger styling) and go through a confirmation step.
