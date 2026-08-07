# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-08-05
- Primary product surfaces: Overview, sensor detail, Alerts, EDA, Model Evaluation, Simulation, and System Health.
- Evidence reviewed: `README.md`; `frontend/src/app/AppShell.tsx`; `frontend/src/app/navigation.ts`; `frontend/src/app/router.tsx`; `frontend/src/pages/ModelEvaluationPage.tsx`; `frontend/src/pages/SystemHealthPage.tsx`; `frontend/src/features/systemHealth/StatusSnapshot.tsx`; model-evaluation and system-health contracts, fixtures, queries, and API handlers; `backend/anomaly_backend/routes/system.py`; `frontend/src/theme/tokens.ts`; `frontend/src/theme/theme.ts`; chart and EDA components under `frontend/src/components/charts` and `frontend/src/features`; Playwright specifications and baselines under `frontend/tests/e2e`.
- This file is the design contract for the switchable light/dark theme, the Model Evaluation and System Health dashboards, and the adaptive shared Live Telemetry Health card used by Overview, Sensor Detail, and System Health. The Model Evaluation offline payload is intentionally migrated to the executed Step 7 notebook schema; public routes, query keys, and dependencies remain unchanged.

## Brand

- Personality: Technical, operational, calm, precise, and trustworthy.
- Trust signals: Dense but readable telemetry, explicit provenance, stable semantic status colors, visible focus, and predictable controls.
- Avoid: Decorative gradients, novelty motion, low-contrast chrome, a dark-sidebar/light-canvas hybrid, or theme-specific layout changes.

## Product goals

- Goals: Preserve the complete light/dark theme behavior; turn Model Evaluation into an evidence-separated visual comparison with progressive technical disclosure; turn System Health into an operational status board with legible KPIs and service cards; replace the shared text-heavy Live Telemetry Health block with compact Overview/Sensor and detailed System Health presentations of the same evidence.
- Non-goals: No public route, query-key, dependency, live-threshold, model-weight, database, or inference changes; no synthetic winner, leaderboard, readiness score, or platform-wide status; no explicit System menu option or decorative theme transition.
- Success signals: Both dashboards and every Live Telemetry Health consumer remain truthful to their evidence sources, expose exact/technical data accessibly, retain useful data through independent or polling failures, fit at 390px without horizontal overflow, and pass reviewed dark/light visual baselines. The sidebar and unrelated routes retain their established behavior.

## Personas and jobs

- Primary personas: IoT operators, anomaly analysts, and maintainers reviewing telemetry health and model behavior.
- User jobs: Spot anomalous sensors, inspect historical and live evidence, review alerts, understand EDA/model outputs, run simulations, and diagnose system health.
- Key contexts of use: Desktop operational monitoring, direct-linked analytical views, and compact/mobile-width inspection with either device color preference.

## Information architecture

- Primary navigation: Permanent left sidebar with six visible route destinations; EDA remains available by direct URL and is intentionally hidden from the sidebar. On desktop, a control outside the navigation landmark collapses the sidebar from 264px to the existing 72px icon rail and persists the choice locally. Theme control is a footer action outside the `Primary navigation` landmark.
- Core routes/screens: `/`, `/sensors/:sensorId`, `/alerts`, `/eda`, `/model-evaluation`, `/simulation`, and `/system-health`.
- Authentication boundary: `/login` renders outside the shell and is the only route reachable without a session; every other route is wrapped by a guard that redirects there, carrying the requested path so signing in lands on it. The sidebar footer holds a sign-out action below the theme control, outside the `Primary navigation` landmark. A session that lapses mid-visit returns the visitor to `/login` rather than leaving failed panels behind.
- Content hierarchy: Product identity, route navigation, route title/context, summary/status information, visual comparison or operational KPI layer, responsive detail cards, and progressively disclosed technical evidence.
- Model Evaluation hierarchy: Reported training registry first; separately labeled Step 7 `val_injected` evaluation second; the primary non-overlapping-bin comparison chart appears before selected-model KPIs, the three-scope table, and technical evidence.
- System Health hierarchy: Live telemetry classification and operational observation first; KPI row and timestamp evidence second; service grid third; bounded technical diagnostics last.
- Overview/Sensor hierarchy: Compact Live Telemetry Health status and four scannable indicators replace repeated freshness paragraphs; exact timestamps and technical evidence remain collapsed by default.

## Design principles

- Preserve meaning across schemes: semantic roles, not raw dark constants, own status, surface, divider, sidebar, and chart colors.
- Respect the user and device: system preference controls the UI until the user makes an explicit binary choice; that choice then persists and synchronizes.
- Keep operations stable: switching schemes changes color only, never layout, data, route state, or backend behavior.
- Separate evidence before summarizing it: training registry and Step 7 validation-injected evaluation remain independently queried, independently failed, and independently attributed. Executed notebook output is authoritative; the final test set remains unconsumed.
- Prefer neutral observability over synthetic judgment: charts compare measured values, while status views report API states and retained-snapshot limits without declaring a best model or inventing a global health/readiness score.
- Tradeoffs: Route-local card/grid layouts remain the summary layer, while horizontally contained tables preserve exact confusion counts and the three distinct evaluation scopes. Shared `StatusSnapshot` gains explicit compact/detailed densities so Overview and Sensor remain concise while System Health exposes the full evidence strip. Immediate scheme changes intentionally disable CSS transitions to avoid distracting flashes; chart consumers force a React theme rerender because they require concrete JavaScript color values.

## Visual language

- Color — dark (unchanged): canvas `#090D12`; paper `#111820`; primary text `#F3F6F8`; secondary text `#9BA8B4`; divider `#26323D`; strong/sidebar boundary `#3C4A57`; primary `#4C8DFF`; success `#4EC7A5`; warning `#F2B84B`; error `#FF6B6B`; info `#9AA7B2`; signal soft `#172A47`; success soft `#123A32`; success text `#A7E8D5`; warning soft `#332716`; offline soft `#202A33`; retained legacy sidebar-rule token `#24303A`; sidebar text `#CBD4DC`; sidebar muted `#81909D`; sidebar hover `#151F29`; sidebar active `#192A3F`; reconstruction error uses the existing MUI pink-300 value `#F06292`.
- Color — light: canvas `#F6F8FA`; paper `#FFFFFF`; primary text `#17202A`; secondary text `#52606D`; divider `#D8E0E7`; strong/sidebar divider `#B8C4CE`; primary `#2563EB`; success `#147D64`; warning `#9A6700`; error `#C9374C`; info `#52606D`; signal soft `#E7EFFF`; success soft `#E2F4ED`; success-chip text reuses primary text `#17202A` for AA contrast; warning soft `#FFF1CC`; offline soft `#E9EEF2`; sidebar text `#334155`; sidebar muted `#64748B`; sidebar hover `#EDF2F7`; sidebar active `#E7EFFF`; reconstruction error `#AD1457`.
- Typography: Preserve Inter for UI, IBM Plex Mono for data, and all existing type sizes, weights, and line heights.
- Spacing/layout rhythm: Preserve the 4px base unit, existing route padding, 1600px maximum content width, and 264px/72px sidebar widths. Model registry and service status use equal-height responsive cards with restrained internal spacing; KPI/evidence groups wrap rather than forcing page overflow.
- Shape/radius/elevation: Preserve 4px default radius, outlined panels, restrained elevation, and existing border widths.
- Motion: No theme transition; honor reduced-motion expectations and existing chart behavior.
- Imagery/iconography: Reuse current route icons. The theme action uses a familiar sun/moon icon paired with text on the full sidebar.

## Components

- Existing components to reuse: MUI `ThemeProvider`, `CssBaseline`, `Drawer`, `ListItemButton`, `Tooltip`, `SvgIcon`, `BarChart`, `Dialog`, `Accordion`, `Chip`, `EmptyState`, current application shell, semantic chart helpers, and existing cards/papers.
- New/changed components: A login form on an outlined paper, centered and capped at 420px, with username, password, a submit button disabled until both are filled, and an error alert carrying the server's own wording for a rejected credential or a locked account; a sidebar sign-out action mirroring the theme toggle's compact/full behavior; a route guard that shows a labeled progress indicator while the session resolves. A self-contained sidebar theme toggle footer; dual `colorSchemes` theme configuration; typed `palette.app` roles; scheme-aware chart and canvas color inputs; paired temperature and RH reconstruction charts on Sensor Detail with shared absolute-error and alert-bin semantics; Model Evaluation registry cards, primary-bin metric comparison, model selector, selected KPIs, three-scope metrics table, exact confusion matrix data, and notebook/artifact disclosures; adaptive `StatusSnapshot` summary/KPI/evidence/disclosure densities; System Health service-card grid and bounded diagnostics disclosure.
- Variants and states: Full sidebar shows icon plus action label; compact rail shows icons with accessible labels and tooltips. Desktop collapse is animated through the drawer width, uses a `Collapse sidebar`/`Expand sidebar` button with `aria-expanded`, and persists in `adp-sidebar-collapsed`; the mobile rail remains compact without an extra control. `StatusSnapshot` requires `compact` on Overview/Sensor and `detailed` on System Health; both use identical API evidence and retained-snapshot rules. Model selection uses native buttons with `aria-pressed`, defaults to Conv1D for the current mount, and is not persisted. Service cards pair liveness/readiness chips with text: `not_alive` uses error, `not_ready` uses warning, and `unknown` uses neutral styling. Retained cards are explicitly labeled last-known and cannot read as current status.
- Token/component ownership: Standard MUI palette roles own primary/status/text/background/divider colors. `palette.app` owns soft fills, success-on-soft text, strong/sidebar dividers, sidebar text/muted/hover/active roles, and reconstruction-error color. Components must not import scheme-specific raw colors.

## Accessibility

- Target standard: WCAG 2.1 AA for text, controls, and essential visual distinctions.
- Keyboard/focus behavior: Sidebar collapse, theme switching, and model-selection buttons are reachable in logical order; Enter and Space activate them; the existing 3px focus ring remains visible in both schemes; compact targets remain at least 44px. Dialogs trap focus and restore it to their triggers through the existing MUI dialog behavior; accordions are operable from the keyboard.
- Contrast/readability: Palette tests cover key foreground/background pairs. Charts use scheme-specific concrete colors with distinguishable series, fixed zero-to-100-percent domains, and textual/exact-data alternatives.
- Screen-reader semantics: The theme label describes the action—`Switch to light theme` or `Switch to dark theme`—not merely the current state. Charts have an accessible label and description; liveness/readiness never rely on color alone; timestamp groups identify timezone explicitly.
- Reduced motion and sensory considerations: Theme transitions are disabled; color is paired with labels, text, shapes, percentages, or status wording wherever meaning is essential. No animated gauge or ranking treatment is used.

## Responsive behavior

- Supported breakpoints/devices: Existing MUI breakpoints and Chromium Playwright coverage at 390px, 1280px, 1440px, and 1920px.
- Layout adaptations: Sidebar is 264px from `sm` upward until the user collapses it to the 72px compact rail; below `sm` it is always 72px. The footer stays pinned to the bottom by a flex-column Drawer; its text hides on the compact rail while its icon, accessible name, focusability, and tooltip remain. Registry and service cards collapse to one column at 390px; service cards use three desktop columns, two tablet columns, and one mobile column. The model selector wraps, charts stay contained, and dialog/evidence/hash/dataset content breaks safely.
- Touch/hover differences: The full 44px control target works without hover. Tooltip supplements compact-rail discovery but is not the accessible-name source. Theme switching must introduce no horizontal overflow.

## Interaction states

- Loading: Missing or temporarily unresolved scheme state does not block application rendering; only the toggle is disabled until a concrete active scheme exists.
- Empty: System Health uses the shared `EmptyState` when the API returns no services; dynamic and unknown service names remain present through a fallback label.
- Error: Model registry and Step 7 evaluation queries fail independently, preserving the successful evidence section. Initial health-query failure uses the existing error panel on all three consumers; a refetch failure retains the last snapshot, shows `Current reachability: Unknown` with Retry, and labels the compact or detailed card as retained/last known.
- Success: Existing success badges and soft fills use active palette roles.
- Disabled: The unresolved theme toggle retains an accessible action label and visible disabled styling without writing storage.
- Offline/slow network: Existing offline/status presentation uses active info/offline roles. Retained timestamps are evidence only, without arrows or causal claims; status badges in a retained dashboard are explicitly historical.

## Content voice

- Tone: Direct, concise, operational, and unambiguous.
- Terminology: Preserve existing route and domain terminology. Theme actions are exactly `Switch to light theme` and `Switch to dark theme`. `telemetry.classification` is labeled `Live telemetry`, while `overall_observation` is an operational observation and never a synthetic global status. Training registry and `Evaluasi Step 7 (validation-injected berlabel)` are named separately; `non_overlapping_evaluation_bins` is explicitly the primary scope.
- Microcopy rules: Describe the result of an action; do not expose implementation terms such as mode, scheme, or storage. Avoid `best`, `winner`, ranking, readiness scores, or causal wording not present in the API evidence.

## Implementation constraints

- Framework/styling system: React 19, MUI 9, Emotion, Vite, and existing MUI X charts/data grid.
- Design-token constraints: Use MUI `colorSchemes` with `cssVariables.colorSchemeSelector: 'data'`; do not set a competing top-level `palette.mode`. Preserve existing dark values exactly. Add a typed `palette.app` namespace instead of parallel component-local token maps.
- Provider constraints: `defaultMode="system"`; storage keys `adp-theme-mode` and `adp-theme-scheme`; `noSsr`; `disableTransitionOnChange`; `forceThemeRerender`; `CssBaseline enableColorScheme`. `AppProviders` retains its children-only public interface.
- Behavior constraints: Resolve system mode through `useColorScheme().colorScheme`; clicking sets the opposite explicit Light/Dark mode. System preference keeps updating until a manual choice. Clearing the saved preference restores system-following behavior. Never write an unintended value while the scheme is unresolved.
- Performance constraints: Do not add dependencies. Rebuild chart options from the active palette and redraw canvas heatmaps only when their existing data or concrete color arrays change.
- Compatibility constraints: The theme, Model Evaluation, and System Health work described above introduces no public route, shell, query key, dependency, live-threshold, model-weight, database, or inference changes. Authentication is the one deliberate exception recorded in this file: it adds the `/login` route, the `users` and `user_sessions` tables, and a session requirement on every `/api` path except `/health` and `/ready`. It adds no dependency and does not touch live thresholds, model weights, or inference. The `/api/offline-evaluations` schema changes atomically across strict backend Pydantic and frontend Zod contracts. Registry and Step 7 provenance/family/SHA remain distinct. Existing untracked `docs/diagrams/` content remains untouched.
- Test/screenshot expectations: In addition to theme coverage, Sensor Detail tests cover temperature/RH reconstruction order, channel-specific series and units, null-safe absolute-error bands, alert-bin overlays, and accessible chart descriptions. Model Evaluation tests cover fixed primary-bin chart order/domain/series, keyboard selection, threshold and point-AUC KPIs, all three scopes, confusion-count consistency, notebook hashes, quarantined artifact conflicts, exact-data disclosure, independent endpoint failures, and absence of ranking claims. Shared health-card tests cover compact/detailed density, every telemetry classification, unavailable values, retained Retry semantics, keyboard disclosure, and exact evidence; System Health tests add every liveness/readiness state, empty/dynamic services, missing diagnostics, and fallback labels. Sidebar tests cover collapse/expand accessibility and persistence across remounts. E2E covers service cards, retry polling, exact-data dialog, keyboard use, and 390px containment on every changed route. Visual tests refresh and inspect dark/light baselines for Overview, Sensor Detail, Model Evaluation, and System Health individually. Run targeted tests, full unit suite, lint, production build and verification, then Playwright; rebuild only the local nginx frontend service and verify all four routes with real API data in light/dark themes.
- Baseline alignment note (2026-08-04): The tracked dark Overview, Sensor Detail, and Model Evaluation images predated the current route content already present in the repository (live-health/filter panels, expanded history, and current model sections). They were manually compared and realigned alongside the new footer; Alerts, System Health, and EDA changes were limited to current route rendering plus the footer/boundary. Dark palette values remain unchanged, and the rendered sidebar boundary is verified as `#3C4A57`.

## Open questions

- None blocking. The approved theme direction and behavior are fully specified; implementation discoveries that contradict this contract must update this file before changing behavior.
- Recorded limitation, not a question: failed-attempt lockout is tracked per account, so a `429` reveals that a username is registered, and one person can lock another's account for the fifteen-minute window. Accepted for a single-tenant platform and stated rather than claimed away.
- Recorded limitation: the visual baselines tolerate a 1% pixel-ratio difference, which is wide enough that the sidebar sign-out action did not trip any existing snapshot. Baselines other than `/login` therefore still show the sidebar without it.
