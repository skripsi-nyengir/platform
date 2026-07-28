import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import type { EdaRunSummary, EdaSectionName } from '../contracts/eda'
import {
  edaCacheHitResponse,
  edaCompleteSections,
  edaReadyMonthlyRun,
} from '../mocks/fixtures/eda'
import { server } from '../mocks/node'
import { renderApp } from '../test/renderApp'

const sectionHeadings = [
  'Kualitas Data',
  'Pola Temporal',
  'Hubungan Suhu-RH',
  'Struktur Temporal dan Perubahan Rezim',
  'Metadata Audit dan Akses Data',
] as const

const panelHeadings = [
  'Audit pairing timestamp',
  'Kepadatan gabungan Suhu–RH',
  'Diagnostik univariat',
  'Excerpt kejadian kualitas',
  'Integritas kualitas',
  'Cakupan kalender temporal',
  'Cakupan hari × jam',
  'Distribusi temporal Suhu dan RH',
  'Ringkasan asosiasi Suhu–RH',
  'Korelasi Pearson bergulir',
  'Ketidakpastian bootstrap asosiasi',
  'Kelayakan struktur temporal',
  'Autokorelasi ACF dan PACF',
  'Spektrum frekuensi',
  'Dekomposisi STL',
  'Kandidat perubahan rezim',
] as const

function expectDocumentOrder(names: readonly string[]) {
  const headings = names.map((name) => screen.getByRole('heading', { name }))
  for (let index = 0; index < headings.length - 1; index += 1) {
    expect(headings[index]!.compareDocumentPosition(headings[index + 1]!))
      .toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  }
}

describe('EdaPage', () => {
  it('keeps every research panel open in the fixed responsive section order', async () => {
    renderApp('/eda')

    await screen.findByRole('heading', { name: 'Kualitas Data' })
    expectDocumentOrder(sectionHeadings)

    const index = screen.getByRole('navigation', { name: 'Indeks bagian EDA' })
    for (const heading of sectionHeadings) {
      expect(within(index).getByRole('link', { name: heading })).not.toBeNull()
    }
    for (const heading of panelHeadings) {
      expect(screen.getByRole('heading', { name: heading })).not.toBeNull()
    }

    expect(screen.queryByRole('tablist')).toBeNull()
    for (const testId of [
      'eda-grid-quality',
      'eda-grid-temporal',
      'eda-grid-relationships',
      'eda-grid-structure',
    ]) {
      const grid = screen.getByTestId(testId)
      expect(grid.getAttribute('data-layout')).toBe('curated-spans')
      expect(window.getComputedStyle(grid).display).toBe('grid')
      expect(window.getComputedStyle(grid).minWidth).toBe('0px')
      expect(window.getComputedStyle(grid).gridAutoFlow).toBe('dense')
    }
    expect(window.getComputedStyle(await screen.findByTestId('eda-audit-table-scroll')).overflowX).toBe('auto')
  })

  it('shows source and algorithm provenance plus the global methodology limits', async () => {
    const user = userEvent.setup()
    renderApp('/eda')

    const header = await screen.findByTestId('eda-run-provenance')
    const provenanceTrigger = within(header).getByRole('button', { name: /Detail/ })
    await user.click(provenanceTrigger)
    expect(within(header).getByRole('region').getAttribute('aria-labelledby')).toBe(
      provenanceTrigger.id,
    )
    expect(within(header).getByText('Komputasi rentang setara-algoritme')).not.toBeNull()
    expect(within(header).getByText(/Source SHA-256: a{12}…/)).not.toBeNull()
    expect(within(header).getByText(/Algoritme: b02-v3-live-1/)).not.toBeNull()
    expect(within(header).getByText(/Config: b{12}…/)).not.toBeNull()
    expect(within(header).getAllByText(/2026-02-01T00:00:00 – 2026-03-01T00:00:00/)).toHaveLength(2)
    expect(within(header).getByText(/Jenis periode: monthly/)).not.toBeNull()
    expect(within(header).getByText(/Boundary-censored: tidak/)).not.toBeNull()
    for (const context of ['B02', 'Suhu (°C)', 'RH (%)', 'Asia/Jakarta (WIB)']) {
      expect(within(header).getByText(context)).not.toBeNull()
    }

    const methodology = screen.getByRole('note', { name: 'Batas metodologi EDA' })
    const methodologyTrigger = within(methodology).getByRole('button', { name: /Batas metodologi/ })
    await user.click(methodologyTrigger)
    expect(within(methodology).getByRole('region').getAttribute('aria-labelledby')).toBe(
      methodologyTrigger.id,
    )
    expect(within(methodology).getByText(/kualitas kandidat saja/i)).not.toBeNull()
    expect(within(methodology).getByText(/deskriptif, bukan kausal/i)).not.toBeNull()
    expect(within(methodology).getByText(/tidak memuat bukti model atau deteksi anomali/i)).not.toBeNull()
    expect(within(methodology).getByText(/populasi terpilih yang berbeda/i)).not.toBeNull()
  })

  it('reserves the canonical parity label for a published full-range run', async () => {
    const user = userEvent.setup()
    const canonicalRun: EdaRunSummary = {
      ...edaReadyMonthlyRun,
      run_id: 'run-b02-canonical-v3',
      scope: {
        ...edaReadyMonthlyRun.scope,
        period_kind: 'full_range',
        from: '2025-06-23T00:00:00',
        to: '2026-07-24T09:02:05',
      },
      provenance_label: 'published v3 release',
      canonical_release: true,
      sections: edaReadyMonthlyRun.sections.map((section) => ({
        ...section,
        run_id: 'run-b02-canonical-v3',
      })),
    }
    server.use(
      http.get('/api/eda/runs/:runId', () => (
        HttpResponse.json({ request_id: 'req-canonical-run', run: canonicalRun })
      )),
      http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => {
        const section = edaCompleteSections.find((item) => item.section === params.section)
        return section === undefined
          ? new HttpResponse(null, { status: 404 })
          : HttpResponse.json({ ...section, run_id: canonicalRun.run_id })
      }),
    )

    renderApp(`/eda?mode=precompute&period_kind=monthly&run=${canonicalRun.run_id}`)

    const header = await screen.findByTestId('eda-run-provenance')
    await user.click(within(header).getByRole('button', { name: /Detail/ }))
    expect(within(header).getByText('Rilis v3 terpublikasi (paritas kanonik)')).not.toBeNull()
    expect(within(header).queryByText('Komputasi rentang setara-algoritme')).toBeNull()
    expect(within(header).getByText(/Jenis periode: full_range/)).not.toBeNull()
  })

  it('isolates a section request error and not-eligible diagnostics from sibling panels', async () => {
    const temporalMetadata = edaReadyMonthlyRun.sections.find(
      (section) => section.section === 'temporal_coverage',
    )!
    const auditMetadata = edaReadyMonthlyRun.sections.find(
      (section) => section.section === 'audit_metadata',
    )!
    server.use(
      http.get('/api/eda/runs/:runId/sections/temporal_coverage', () => {
        return HttpResponse.json({
          ...temporalMetadata,
          status: 'failed',
          reason_code: 'section_compute_failed',
          detail: 'Cakupan temporal gagal dimuat untuk uji isolasi.',
          payload_sha256: null,
          payload: null,
        })
      }),
      http.get('/api/eda/runs/:runId/sections/audit_metadata', () => {
        return HttpResponse.json({
          ...auditMetadata,
          status: 'not_eligible',
          reason_code: 'source_identity_unavailable',
          detail: 'Metadata audit belum memenuhi syarat.',
          payload_sha256: null,
          payload: null,
        })
      }),
    )

    renderApp('/eda')

    const temporalPanel = screen.getByRole('heading', { name: 'Cakupan kalender temporal' }).closest('section')
    expect(temporalPanel).not.toBeNull()
    expect((await within(temporalPanel!).findByRole('alert')).textContent).toContain(
      'Cakupan temporal gagal dimuat untuk uji isolasi.',
    )
    expect((await screen.findAllByText(/Perhitungan hubungan gagal/)).length).toBeGreaterThan(0)
    expect(await screen.findByText('Struktur temporal belum memenuhi syarat')).not.toBeNull()
    expect(await screen.findByText(/Identitas sumber tidak tersedia/)).not.toBeNull()
    expect(screen.getByRole('group', { name: 'Kontrol run EDA' })).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Audit pairing timestamp' })).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'Metadata Audit dan Akses Data' })).not.toBeNull()
  })

  it('refreshes provenance and section identities when the selected run changes', async () => {
    const user = userEvent.setup()
    const requestedRuns: string[] = []
    server.use(
      http.post('/api/eda/compute', () => HttpResponse.json(edaCacheHitResponse)),
      http.get('/api/eda/runs/:runId/sections/:section', ({ params }) => {
        requestedRuns.push(String(params.runId))
        const section = edaCompleteSections.find(
          (item) => item.section === (params.section as EdaSectionName),
        )
        return section === undefined
          ? new HttpResponse(null, { status: 404 })
          : HttpResponse.json({ ...section, run_id: String(params.runId) })
      }),
    )
    renderApp('/eda')

    const initialHeader = await screen.findByTestId('eda-run-provenance')
    await user.click(within(initialHeader).getByRole('button', { name: /Detail/ }))
    expect(within(initialHeader).getByText(/Jenis periode: monthly/)).not.toBeNull()
    await user.click(screen.getByLabelText('Mode'))
    await user.click(screen.getByRole('option', { name: 'Rentang kustom' }))
    fireEvent.change(screen.getByLabelText('Dari'), {
      target: { value: edaCacheHitResponse.run.scope.from },
    })
    fireEvent.change(screen.getByLabelText('Sampai'), {
      target: { value: edaCacheHitResponse.run.scope.to },
    })
    await user.click(screen.getByRole('button', { name: 'Hitung EDA' }))

    await waitFor(() => {
      const header = screen.getByTestId('eda-run-provenance')
      expect(within(header).getByText(/Jenis periode: custom/)).not.toBeNull()
      expect(within(header).getAllByText(/2026-02-01T00:00:00 – 2026-02-02T00:00:00/)).toHaveLength(2)
      expect(within(header).getByText(/Run: run-b02-custom-cache/)).not.toBeNull()
    })
    await waitFor(() => expect(requestedRuns).toContain(edaCacheHitResponse.run.run_id))
  })
})
