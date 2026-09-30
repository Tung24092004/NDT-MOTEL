# UI Foundation Implementation Plan - 2026-09-26

Scope: prepare the next phase only. Do not implement foundation components in Phase 1/P0.

## 1. Design Tokens

CURRENT IMPLEMENTATIONS: Brand colors, radius, spacing, typography and shadows are repeated in `core/base.html`, public templates, tenant CSS and admin inline CSS.

PROPOSED CONTRACT: Define semantic tokens for brand, accent, text, muted, line, surface, canvas, success, warning, danger, focus, spacing, radius and elevation.

FILES TO MIGRATE: `static/css/style.css`, `static/css/ui-system.css`, `static/css/tenant/components.css`, major admin templates with local CSS.

BLAST RADIUS: High, because tokens touch every screen.

MIGRATION STRATEGY: Add tokens first, migrate one page family at a time, keep visual parity screenshots.

TEST STRATEGY: `manage.py check`, no migrations, browser QA at 390/768/1024/1440, compare public/gallery pages.

## 2. Typography

CURRENT IMPLEMENTATIONS: 8-11px metadata/table text appears across admin lists; tenant/public pages are more readable.

PROPOSED CONTRACT: Metadata minimum 12px, table 13-14px, body/form 14-16px, headings from 20/24/32px, no viewport-scaled font sizes.

FILES TO MIGRATE: `quan_ly_*`, admin detail templates, auth/tenant CSS where small helper text appears.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Start with list/table pages, then forms, then detail pages.

TEST STRATEGY: Visual QA and CSS scan for `font-size: 8px`, `9px`, `10px`, `11px`.

## 3. PageHeader

CURRENT IMPLEMENTATIONS: Page title, kicker, back link and actions are page-local.

PROPOSED CONTRACT: Include/component with breadcrumb, title, description, metadata and actions slots.

FILES TO MIGRATE: Public room pages, tenant record pages, `quan_ly_*`, Smart Room pages.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Introduce include, migrate read-only pages first, then workflow pages.

TEST STRATEGY: Route smoke tests and screenshot QA.

## 4. Button

CURRENT IMPLEMENTATIONS: Many local button classes with inconsistent sizes and colors.

PROPOSED CONTRACT: Primary, secondary, danger, ghost and icon-only variants; compact/default/mobile sizes; loading and disabled states.

FILES TO MIGRATE: `style.css`, `ui-system.css`, tenant CSS, admin templates.

BLAST RADIUS: High for workflow pages.

MIGRATION STRATEGY: Add new classes beside old classes, migrate high-traffic pages, then retire duplicates.

TEST STRATEGY: Keyboard focus checks, mobile target checks, workflow smoke tests.

## 5. Badge

CURRENT IMPLEMENTATIONS: Status badges are mapped separately per page and some raw enum labels can leak.

PROPOSED CONTRACT: Central status label/tone registry and badge component.

FILES TO MIGRATE: Booking, contract, invoice, repair, Smart Room and policy templates.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Keep DB values unchanged; map presentation labels and tones centrally.

TEST STRATEGY: Template assertions for labels, no migrations, visual badge contrast checks.

## 6. Form Controls

CURRENT IMPLEMENTATIONS: Long forms use local field, helper, error and action styles.

PROPOSED CONTRACT: Field wrapper, label, required marker, helper, error, control and form action bar.

FILES TO MIGRATE: `tao_*`, `sua_*`, account forms, Smart Room forms.

BLAST RADIUS: High.

MIGRATION STRATEGY: Start with non-destructive create/edit forms, keep names/POST contracts unchanged.

TEST STRATEGY: Form validation tests, browser smoke tests, no workflow changes.

## 7. Table

CURRENT IMPLEMENTATIONS: Admin tables have separate wrappers, min-widths and action columns.

PROPOSED CONTRACT: Table shell, toolbar, overflow-x behavior, action column contract, empty/loading/error row.

FILES TO MIGRATE: `quan_ly_dat_phong`, `quan_ly_hop_dong`, `quan_ly_hoa_don`, `quan_ly_phong`, tenant tables.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Preserve tables and horizontal scroll in Phase 2; defer card conversion decisions.

TEST STRATEGY: 390/768/1024/1440 screenshots and keyboard scroll/action checks.

## 8. EmptyState

CURRENT IMPLEMENTATIONS: Empty states vary from raw rows to icon blocks.

PROPOSED CONTRACT: Title, body, optional icon and optional CTA.

FILES TO MIGRATE: Dashboards, room/booking/contract/invoice/repair/notice/Face ID templates.

BLAST RADIUS: Low to medium.

MIGRATION STRATEGY: Replace passive empty copy first, add CTA only where workflow already exists.

TEST STRATEGY: Template branch checks and visual QA.

## 9. Dialog

CURRENT IMPLEMENTATIONS: Browser `confirm()` and `alert()` plus local modal implementations.

PROPOSED CONTRACT: Accessible confirmation dialog with default/danger variants, focus trap, cancel default and contextual body.

FILES TO MIGRATE: Booking, contract, invoice, policy, Smart Room and sharing actions.

BLAST RADIUS: High because actions are destructive/financial.

MIGRATION STRATEGY: Build once, migrate high-risk actions gradually, keep server-side permissions unchanged.

TEST STRATEGY: Keyboard tests, action smoke tests, no data mutation except explicit workflow tests.

## 10. Card

CURRENT IMPLEMENTATIONS: Cards/panels use many radii, shadows and padding systems.

PROPOSED CONTRACT: Panel, item and metric cards with fixed radius/elevation roles.

FILES TO MIGRATE: Tenant records, admin KPIs, public room cards, Smart Room panels.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Tokenize card visuals before changing markup.

TEST STRATEGY: Visual regression screenshots.

## 11. Responsive Utilities

CURRENT IMPLEMENTATIONS: Each page owns its own breakpoints; admin tables rely on local overflow.

PROPOSED CONTRACT: Shared utilities for stack, grid, table-scroll, action-wrap, sr-only and stable touch targets.

FILES TO MIGRATE: `ui-system.css`, tenant CSS, admin local CSS.

BLAST RADIUS: Medium.

MIGRATION STRATEGY: Add utilities first, migrate page families when touching them for component work.

TEST STRATEGY: 390/768/1024/1440 QA and horizontal overflow checks.
