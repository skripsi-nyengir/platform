# MUI dashboard reference design

## Purpose

Refresh the application shell and Overview page with patterns from the official MUI v9 Dashboard template. This is an adaptation, not a new design system. The work preserves the existing data contracts, routes, alert acknowledgement flow, keyboard behavior, and accessibility semantics. All other pages inherit the dark theme only; their internal layouts are unchanged.

## Approved scope

Only the application shell and Overview are redesigned.

The shell has a permanent dark sidebar. It contains the product title and subtitle, the six existing navigation routes in their current order, and their matching MUI icons. The active route has a blue selection strip and selected-item treatment. There is no top bar, search, notification area, settings entry, user identity, report download, mobile drawer, custom token system, decorative animation, or new dependency.

Use the existing font stack and a global dark MUI theme with only minimal brand overrides for primary blue, dark surfaces, text contrast, dividers, selected navigation, focus visibility, Cards, Chips, and Buttons. Every interactive element retains a visible keyboard focus indicator. Motion is limited to normal MUI state feedback; no decorative animation is added.

## Overview composition

Keep the existing page heading, operational summary, attention queue, and sensor matrix order and semantics.

### Operational summary

Render the existing four summary values as four MUI Cards. Preserve every current value, label, loading fallback, unavailable state, and accessibility relationship. The responsive grid is four columns at large widths, two at medium widths, and one at narrow widths.

### Attention queue

Keep every current attention-queue state and action exactly as it behaves today, including loading, empty, retained-data, refresh-error, alert detail navigation, and alert acknowledgement. Do not collapse, relabel, remove, or add actions. Alert acknowledgement remains available through the existing flow and retains its current keyboard behavior.

### Sensor matrix

Render the six existing sensors in their canonical order as six MUI Cards. Each card keeps its semantic article and heading structure, current Temperature and RH values, freshness or health status Chip, current metadata, inference and alert information, and existing inspect or alert-review routes and actions. Latest values remain visible whenever chart data is loading, empty, or unavailable.

The grid is three columns at large widths, two at medium widths, and one at narrow widths. Cards must wrap content without document-level horizontal overflow.

## Sensor sparklines

Each sensor card includes one compact 90 px EChart sparkline with both temperature and RH series. A single bounded telemetry-history query per sensor supplies a rolling 30-minute window. It must not replace, duplicate, or alter the existing latest-telemetry query or its fallbacks.

The sparkline uses time on the horizontal axis and compact, accessible series naming for Temperature and RH. It has no decorative legend, toolbar, zoom control, or extra interaction surface. Current numerical values, units, status text, and metadata remain the primary accessible telemetry presentation; the chart is supplementary.

Chart states degrade in place without hiding the card's latest values:

- Loading: reserve the 90 px chart region and show a compact loading state.
- Empty history: reserve the region and state that no recent history is available.
- History error: reserve the region and show a compact unavailable state while retaining the latest telemetry and existing error handling.
- Valid history: render both series from the bounded 30-minute result.

## Data and interaction invariants

- Preserve all existing API contracts, polling or refresh behavior, stale, offline, unknown, unavailable, and inference states.
- Keep exactly six stable sensor cards even when telemetry is incomplete, duplicated, reordered, stale, offline, or failed.
- Preserve current route destinations, link semantics, alert-review conditions, alert acknowledgement, headings, landmarks, labels, and keyboard navigation.
- Do not use color alone for sensor health, anomaly, alert, selected navigation, chart state, or focus state.
- Keep MUI controls and links reachable by keyboard with visible focus and existing accessible names.

## Affected areas

- Application shell and route navigation components.
- Global MUI theme configuration.
- Overview summary, attention queue, and sensor matrix components.
- Existing telemetry-history query integration for the six sensor cards.
- Focused Overview, layout, end-to-end, and visual test coverage.

No other page receives an internal redesign.

## Verification

Run focused unit tests for the shell and Overview, plus end-to-end coverage for navigation, sensor inspection, alert review, and alert acknowledgement. Assert the six sensor cards, four summary Cards, retained queue states, current values, status Chips, routes, chart loading/empty/error degradation, and keyboard focus behavior.

Run lint and the production build. Capture screenshots at the project's existing large, medium, and narrow viewports to verify the 4 to 2 to 1 summary grid, 3 to 2 to 1 sensor grid, dark sidebar, selected route treatment, focus indicators, and absence of horizontal overflow. Complete visual QA against those screenshots with animations disabled for deterministic captures.
