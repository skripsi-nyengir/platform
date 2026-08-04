# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-08-04
- Primary product surfaces: Overview, sensor detail, Alerts, EDA, Model Evaluation, Simulation, and System Health.
- Evidence reviewed: `README.md`; `frontend/src/app/AppShell.tsx`; `frontend/src/app/navigation.ts`; `frontend/src/app/router.tsx`; `frontend/src/theme/tokens.ts`; `frontend/src/theme/theme.ts`; chart and EDA components under `frontend/src/components/charts` and `frontend/src/features`; Playwright specifications and baselines under `frontend/tests/e2e`.
- This file is the design contract for the switchable light/dark theme. Existing routes, layouts, backend contracts, and dependencies remain unchanged.

## Brand

- Personality: Technical, operational, calm, precise, and trustworthy.
- Trust signals: Dense but readable telemetry, explicit provenance, stable semantic status colors, visible focus, and predictable controls.
- Avoid: Decorative gradients, novelty motion, low-contrast chrome, a dark-sidebar/light-canvas hybrid, or theme-specific layout changes.

## Product goals

- Goals: Add a complete light theme; retain the current dark appearance; follow the device scheme on first visit; persist the first manual Light/Dark choice across reloads and tabs; keep charts and canvas visualizations synchronized with the active scheme.
- Non-goals: No route, layout, API, schema, backend, dependency, or information-architecture changes; no explicit System menu option; no decorative theme transition.
- Success signals: All seven routes are legible and semantically consistent in both schemes; the sidebar toggle is keyboard and screen-reader accessible at every supported width; dark visual baselines remain backward-compatible; light visual baselines pass review.

## Personas and jobs

- Primary personas: IoT operators, anomaly analysts, and maintainers reviewing telemetry health and model behavior.
- User jobs: Spot anomalous sensors, inspect historical and live evidence, review alerts, understand EDA/model outputs, run simulations, and diagnose system health.
- Key contexts of use: Desktop operational monitoring, direct-linked analytical views, and compact/mobile-width inspection with either device color preference.

## Information architecture

- Primary navigation: Permanent left sidebar with six visible route destinations; EDA remains available by direct URL and is intentionally hidden from the sidebar. Theme control is a footer action outside the `Primary navigation` landmark.
- Core routes/screens: `/`, `/sensors/:sensorId`, `/alerts`, `/eda`, `/model-evaluation`, `/simulation`, and `/system-health`.
- Content hierarchy: Product identity, route navigation, route title/context, summary/status information, detailed panels/tables/charts, and supporting actions.

## Design principles

- Preserve meaning across schemes: semantic roles, not raw dark constants, own status, surface, divider, sidebar, and chart colors.
- Respect the user and device: system preference controls the UI until the user makes an explicit binary choice; that choice then persists and synchronizes.
- Keep operations stable: switching schemes changes color only, never layout, data, route state, or backend behavior.
- Tradeoffs: Immediate scheme changes intentionally disable CSS transitions to avoid distracting flashes; chart consumers force a React theme rerender because they require concrete JavaScript color values.

## Visual language

- Color — dark (unchanged): canvas `#090D12`; paper `#111820`; primary text `#F3F6F8`; secondary text `#9BA8B4`; divider `#26323D`; strong/sidebar boundary `#3C4A57`; primary `#4C8DFF`; success `#4EC7A5`; warning `#F2B84B`; error `#FF6B6B`; info `#9AA7B2`; signal soft `#172A47`; success soft `#123A32`; success text `#A7E8D5`; warning soft `#332716`; offline soft `#202A33`; retained legacy sidebar-rule token `#24303A`; sidebar text `#CBD4DC`; sidebar muted `#81909D`; sidebar hover `#151F29`; sidebar active `#192A3F`; reconstruction error uses the existing MUI pink-300 value `#F06292`.
- Color — light: canvas `#F6F8FA`; paper `#FFFFFF`; primary text `#17202A`; secondary text `#52606D`; divider `#D8E0E7`; strong/sidebar divider `#B8C4CE`; primary `#2563EB`; success `#147D64`; warning `#9A6700`; error `#C9374C`; info `#52606D`; signal soft `#E7EFFF`; success soft `#E2F4ED`; success-chip text reuses primary text `#17202A` for AA contrast; warning soft `#FFF1CC`; offline soft `#E9EEF2`; sidebar text `#334155`; sidebar muted `#64748B`; sidebar hover `#EDF2F7`; sidebar active `#E7EFFF`; reconstruction error `#AD1457`.
- Typography: Preserve Inter for UI, IBM Plex Mono for data, and all existing type sizes, weights, and line heights.
- Spacing/layout rhythm: Preserve the 4px base unit, existing route padding, 1600px maximum content width, and 264px/72px sidebar widths.
- Shape/radius/elevation: Preserve 4px default radius, outlined panels, restrained elevation, and existing border widths.
- Motion: No theme transition; honor reduced-motion expectations and existing chart behavior.
- Imagery/iconography: Reuse current route icons. The theme action uses a familiar sun/moon icon paired with text on the full sidebar.

## Components

- Existing components to reuse: MUI `ThemeProvider`, `CssBaseline`, `Drawer`, `ListItemButton`, `Tooltip`, `SvgIcon`, current application shell, semantic chart helpers, and existing cards/papers/chips.
- New/changed components: A self-contained sidebar theme toggle footer; dual `colorSchemes` theme configuration; typed `palette.app` roles; scheme-aware chart and canvas color inputs.
- Variants and states: Full sidebar shows icon plus action label; compact rail shows the icon with an accessible tooltip. The control has light-target, dark-target, focus-visible, hover, and temporarily unresolved/disabled states.
- Token/component ownership: Standard MUI palette roles own primary/status/text/background/divider colors. `palette.app` owns soft fills, success-on-soft text, strong/sidebar dividers, sidebar text/muted/hover/active roles, and reconstruction-error color. Components must not import scheme-specific raw colors.

## Accessibility

- Target standard: WCAG 2.1 AA for text, controls, and essential visual distinctions.
- Keyboard/focus behavior: Theme switching is a native button action reachable in sidebar order; Enter and Space activate it; the existing 3px focus ring remains visible in both schemes; the compact target remains at least 44px.
- Contrast/readability: Palette tests cover key foreground/background pairs. Charts use scheme-specific concrete colors with distinguishable semantic roles.
- Screen-reader semantics: The label describes the action—`Switch to light theme` or `Switch to dark theme`—not merely the current state. The footer remains outside the primary navigation landmark.
- Reduced motion and sensory considerations: Theme transitions are disabled; color is paired with existing labels, text, shapes, or status wording wherever meaning is essential.

## Responsive behavior

- Supported breakpoints/devices: Existing MUI breakpoints and Chromium Playwright coverage at 390px, 1280px, 1440px, and 1920px.
- Layout adaptations: Sidebar is 264px from `sm` upward and a 72px compact rail below `sm`. The footer stays pinned to the bottom by a flex-column Drawer; its text hides on the compact rail while its icon, accessible name, focusability, and tooltip remain.
- Touch/hover differences: The full 44px control target works without hover. Tooltip supplements compact-rail discovery but is not the accessible-name source. Theme switching must introduce no horizontal overflow.

## Interaction states

- Loading: Missing or temporarily unresolved scheme state does not block application rendering; only the toggle is disabled until a concrete active scheme exists.
- Empty: Existing empty-state components and semantics are preserved in both schemes.
- Error: Existing error text, panels, and alert semantics use active palette roles and retain readable contrast.
- Success: Existing success badges and soft fills use active palette roles.
- Disabled: The unresolved theme toggle retains an accessible action label and visible disabled styling without writing storage.
- Offline/slow network: Existing offline/status presentation uses active info/offline roles; theme behavior has no network dependency.

## Content voice

- Tone: Direct, concise, operational, and unambiguous.
- Terminology: Preserve existing route and domain terminology. Theme actions are exactly `Switch to light theme` and `Switch to dark theme`.
- Microcopy rules: Describe the result of an action; do not expose implementation terms such as mode, scheme, or storage.

## Implementation constraints

- Framework/styling system: React 19, MUI 9, Emotion, Vite, and existing MUI X charts/data grid.
- Design-token constraints: Use MUI `colorSchemes` with `cssVariables.colorSchemeSelector: 'data'`; do not set a competing top-level `palette.mode`. Preserve existing dark values exactly. Add a typed `palette.app` namespace instead of parallel component-local token maps.
- Provider constraints: `defaultMode="system"`; storage keys `adp-theme-mode` and `adp-theme-scheme`; `noSsr`; `disableTransitionOnChange`; `forceThemeRerender`; `CssBaseline enableColorScheme`. `AppProviders` retains its children-only public interface.
- Behavior constraints: Resolve system mode through `useColorScheme().colorScheme`; clicking sets the opposite explicit Light/Dark mode. System preference keeps updating until a manual choice. Clearing the saved preference restores system-following behavior. Never write an unintended value while the scheme is unresolved.
- Performance constraints: Do not add dependencies. Rebuild chart options from the active palette and redraw canvas heatmaps only when their existing data or concrete color arrays change.
- Compatibility constraints: No public route, backend contract, API, or schema changes. Existing untracked `docs/diagrams/` content remains untouched.
- Test/screenshot expectations: Unit tests cover both palettes, unchanged typography/layout tokens, scheme-aware overrides, key AA contrast pairs, system initialization, saved-mode precedence, persistence/remount/storage synchronization, keyboard and tooltip accessibility, unresolved mode, semantic chart colors, and canvas redraw. Visual tests seed dark explicitly for existing baselines, add the missing dark Simulation baseline, and add 1440px light baselines for all seven routes including direct-URL EDA and Simulation. At 390px, verify toggle visibility/focus/name and no horizontal overflow. Run targeted tests, full unit suite, lint, production build and verification, then Playwright; inspect new baselines individually.
- Baseline alignment note (2026-08-04): The tracked dark Overview, Sensor Detail, and Model Evaluation images predated the current route content already present in the repository (live-health/filter panels, expanded history, and current model sections). They were manually compared and realigned alongside the new footer; Alerts, System Health, and EDA changes were limited to current route rendering plus the footer/boundary. Dark palette values remain unchanged, and the rendered sidebar boundary is verified as `#3C4A57`.

## Open questions

- None. The approved theme direction and behavior are fully specified; implementation discoveries that contradict this contract must update this file before changing behavior.
