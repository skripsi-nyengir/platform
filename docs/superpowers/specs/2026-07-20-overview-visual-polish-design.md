# Overview visual polish design

## Purpose

Make the Overview page read as an operational control surface rather than a sparse result list. The page keeps its current triage order, data contracts, routes, and six-card sensor matrix. The change is visual hierarchy and control treatment only.

## Chosen direction: operational control cards

Use compact, data-forward cards with quiet instrument-panel styling:

- The operational summary remains one labeled region with its existing four metrics and tested grid: `repeat(3, minmax(0, 1fr)) minmax(180px, 1.25fr)`, `gap: 2`, and `p: 4`.
- Each summary metric becomes a shallow tile inside that grid. Keep its caption and `h2` value, then add a restrained surface, rule, and layered shadow so the four values scan as controls rather than plain text columns.
- Sensor articles remain outlined cards with a left active rule. Normal cards use the standard rule color. A sensor with an anomalous inference or detected alert retains the `tokens.color.alarm` left rule and the existing priority message.
- Use `tokens.font.data` plus `font-variant-numeric: tabular-nums` for every telemetry, score, threshold, age, timestamp, and summary value. Labels keep the UI font.

The style is deliberate, not decorative: no new icon package, illustration, chart, or dependency.

## Component changes

### `OverviewPage.tsx`

Keep the H1, summary region label, attention queue, and sensor matrix order unchanged. Enrich the four existing summary metric containers with a small label, prominent technical value, and a restrained surface treatment. Do not change summary values, unavailable behavior, query behavior, or the summary grid declaration.

### `SensorMatrix.tsx`

For each existing `article` card:

1. Keep the H3 sensor heading, priority logic, status, action routes, and canonical `n1` through `n6` order.
2. Replace the temperature and RH text lines with two prominent metric tiles. Each tile has an uppercase or caption label and a larger data-font value. Missing values remain `Unavailable`.
3. Replace timestamp, age, and inference key-colon lines with labeled metadata rows. Use a semantic definition list with separate `dt` labels and `dd` values:
   - Telemetry rows: Timestamp and Age.
   - Inference rows: State, Score, and Threshold when available.
   - Preserve `Inference unavailable` and `No score available`; never render a missing score as zero.
4. Replace `Inspect sensor history` with an MUI `Button` using `variant="outlined"`, `component={RouterLink}`, and the existing destination `/sensors/:sensorId?sensor=:sensorId`. It remains a real link in the accessibility tree, with no manually assigned role.
5. Keep `Review active alert` conditional on a detected alert and retain `/alerts?sensor=:sensorId`. It remains visible beside the inspect control only when that alert exists.

### `SensorStatus.tsx`

Keep Fresh telemetry, stale, offline, and unknown status mapping intact. Fresh telemetry remains a non-interactive MUI `Chip`: no click handler, link target, keyboard action, or fake button role. Move timestamp and age display responsibility to the card metadata rows so this component supplies only the live status label and chip semantics.

### `tokens.ts`

Add only reusable Overview visual tokens if the current tokens cannot express the treatment. Limit additions to surface shadow and motion values shared by summary tiles and sensor cards. Preserve existing colors, `tokens.size.control` at 44, and typography tokens.

## Visual and interaction rules

- Resting cards and summary tiles use a subtle two-layer shadow, such as `0 1px 2px rgba(19, 33, 46, 0.06), 0 8px 20px rgba(19, 33, 46, 0.05)`, rather than a heavy border-only treatment.
- Transition only `transform`, `box-shadow`, and `border-color`. Use a 160 ms easing transition. Do not use `transition: all`.
- Under `@media (hover: hover) and (pointer: fine)`, cards and actionable controls may lift by 2 px and receive a slightly stronger shadow on hover. Touch and coarse-pointer devices receive no hover-only change.
- Interactive buttons use `:active { transform: scale(0.96) }`. Inspect controls have a 44 px minimum height through `tokens.size.control`; the review action must also retain a 44 px target.
- Under `prefers-reduced-motion: reduce`, remove transform movement and shorten or remove visual transitions. Focus indication remains visible.
- Keep action rows wrapping. Do not assign fixed widths that can make cards, text, or controls overflow horizontally.

## Data and behavior invariants

- The page still renders exactly six stable sensor articles in canonical ID order, even with incomplete, duplicated, reordered, offline, or failed telemetry.
- Telemetry availability, score availability, active alert count, and highest breach calculations stay unchanged. Unknown values remain explicit as `Unknown` or `Unavailable`.
- Anomalous inference alone still produces the priority treatment but does not create a Review active alert link.
- Alert acknowledgement stays in the existing CurrentAlertCard flow. This polish does not add resolve, dismiss, or bulk actions.
- All current loading, initial-error, refresh-error, and retained-data states remain visible and independent.

## Responsive and accessibility constraints

- Preserve semantic landmarks: summary `section` with `aria-label="Operational summary"`, Attention queue and Sensor matrix H2 headings, and each sensor `article` with its H3 heading and sensor aria-label.
- Keep the tested six-card responsive matrix: `repeat(auto-fit, minmax(min(320px, 100%), 1fr))`. The metric-tile pair may collapse to one column only when needed to prevent overflow.
- Definition-list labels must remain associated with their values. Status remains exposed with `role="status"` and its current accessible name.
- Do not rely on color alone for anomalies, freshness, or action state. The priority and inference text remain visible.
- Keep all text readable at narrow widths with `minWidth: 0`, `overflowWrap: anywhere`, wrapped action rows, and no document horizontal overflow.

## Affected files

- `frontend/src/pages/OverviewPage.tsx`
- `frontend/src/features/overview/SensorMatrix.tsx`
- `frontend/src/components/states/SensorStatus.tsx`
- `frontend/src/theme/tokens.ts`
- `frontend/src/pages/OverviewPage.test.tsx`
- `frontend/tests/e2e/overview.spec.ts`
- `frontend/tests/e2e/layout.spec.ts`
- `frontend/tests/e2e/visual.spec.ts`
- `frontend/tests/e2e/visual.spec.ts-snapshots/overview.png`

`CurrentAlertCard` and all non-Overview routes remain unchanged.

## Verification and baseline expectations

Update focused unit coverage in `OverviewPage.test.tsx` to assert the unchanged four summary metrics and grid, six semantic articles, fresh status chip, metric-tile values, labeled telemetry and inference rows, unavailable fallbacks, red priority rule, and both route destinations. Assert Inspect is a link-styled outlined MUI button with a 44 px target and Review remains conditional on a detected alert.

Keep `overview.spec.ts` exercising the n4 Inspect route. Extend `layout.spec.ts` only where needed to confirm all Overview controls meet the 44 px target, wrap inside their cards, and maintain zero horizontal overflow at every existing viewport. Keep the existing semantic counts and headings.

Run the focused Overview unit test and Overview E2E, layout, and visual suites. The approved visual change requires updating only `frontend/tests/e2e/visual.spec.ts-snapshots/overview.png`; no other route baseline should change. Visual screenshots continue with animations disabled, while runtime behavior still honors fine-pointer and reduced-motion rules.
